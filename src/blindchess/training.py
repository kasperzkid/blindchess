"""Interactive training routines and main loop orchestration for BlindChess."""

from pathlib import Path
import random
import time
from typing import Optional
import chess

from blindchess.analysis import analyse_position
from blindchess.blindfold import get_blindfold_exercise_by_level
from blindchess.board_state import BoardState
from blindchess.calculation import evaluate_calculation_attempt
from blindchess.commands import get_help_text, is_command, parse_command
from blindchess.config import AppConfig
from blindchess.endgames import BUILTIN_ENDGAMES, probe_tablebase
from blindchess.engine_manager import EngineManager
from blindchess.engine_profiles import get_profile
from blindchess.errors import BlindChessError, InvalidMoveError
from blindchess.openings import BUILTIN_REPERTOIRES, OpeningTrainer
from blindchess.persistence import DatabaseManager
from blindchess.pgn_tools import export_game_to_pgn, load_game_from_pgn, load_game_into_board_state, save_pgn_to_file
from blindchess.review import review_game
from blindchess.session import ActiveSession
from blindchess.statistics import compute_training_statistics, evaluate_adaptive_difficulty
from blindchess.strategy import explain_move_rationale, generate_strategic_questions
from blindchess.tactics import BUILTIN_PUZZLES, TacticalSession
from blindchess.terminal_ui import TerminalUI
from blindchess.variations import VariationTree


def run_game_loop(
    config: AppConfig,
    engine_mgr: Optional[EngineManager],
    db_mgr: Optional[DatabaseManager],
    opponent_level: str = "intermediate",
    user_side: str = "white",
    show_board: bool = False,
    strict_blindfold: bool = False,
    start_fen: Optional[str] = None,
) -> None:
    """Run an interactive chess game against Stockfish or 2-player local."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    state = BoardState(start_fen) if start_fen else BoardState()
    session = ActiveSession(mode="game", level=config.training_level, db_mgr=db_mgr)

    human_color = chess.WHITE if user_side.lower() == "white" else chess.BLACK
    profile = get_profile(opponent_level)

    print(f"\nStarting Chess Game | Side: {user_side.capitalize()} | Opponent: {profile.name}")
    print("Type a move (e.g. 'e4', 'Nf3') or 'help' for commands.\n")

    if show_board or config.board_visibility == "normal":
        ui.print_board(state, perspective_white=(human_color == chess.WHITE))

    while not state.is_game_over():
        is_human_turn = (state.turn == human_color)

        if is_human_turn or not (engine_mgr and engine_mgr.is_available and engine_mgr.engine):
            player_prompt = f"{state.turn_name} to move ({state.move_number}.): "
            user_input = ui.prompt(player_prompt)

            if not user_input:
                continue

            if is_command(user_input):
                cmd, args = parse_command(user_input)
                if cmd == "quit":
                    print("Exiting game.")
                    break
                elif cmd == "help":
                    print(get_help_text("game"))
                elif cmd == "board":
                    if strict_blindfold:
                        print("Strict blindfold mode is enabled: board reveals are disabled.")
                    else:
                        session.record_reveal()
                        ui.print_board(state, perspective_white=(human_color == chess.WHITE))
                elif cmd == "moves":
                    moves_str = " ".join(f"{r.san}" for r in state.history)
                    print(f"Moves played: {moves_str or '(None)'}")
                elif cmd == "fen":
                    print(f"Current FEN: {state.board.fen()}")
                elif cmd == "status":
                    is_over, status_desc, _ = state.get_game_status()
                    print(f"Status: {status_desc}")
                    bal = state.get_material_balance()
                    print(f"Material balance: White {bal['white']} - Black {bal['black']} (Diff: {bal['diff']:+d})")
                elif cmd == "undo":
                    if engine_mgr and engine_mgr.is_available:
                        undone = state.undo_full_turn()
                        print(f"Undid {len(undone)} moves.")
                    else:
                        undone_rec = state.undo_move()
                        print(f"Undid move: {undone_rec.san if undone_rec else 'None'}")
                elif cmd == "redo":
                    redone = state.redo_move()
                    print(f"Redone move: {redone.san if redone else 'None'}")
                elif cmd == "hint":
                    session.record_hint()
                    if engine_mgr and engine_mgr.is_available and engine_mgr.engine:
                        res = analyse_position(engine_mgr, state.board, depth=10, time_limit=1.0, multipv=1)
                        if res.best_san:
                            print(f"Engine Hint: Consider focusing on candidate move {res.best_san}.")
                    else:
                        print("Hint: Develop pieces toward central control and ensure king safety.")
                elif cmd == "save":
                    pgn_txt = export_game_to_pgn(state, white_name="Player" if human_color == chess.WHITE else profile.name,
                                                  black_name=profile.name if human_color == chess.WHITE else "Player")
                    if db_mgr:
                        gid = db_mgr.save_game(pgn_txt, "White", "Black", "*", session.session_id)
                        print(f"Game saved to database (ID: {gid}).")
                continue

            # Regular move entry
            try:
                rec = state.push_move(user_input)
                print(f"Recorded: {rec.san}")
                if config.board_visibility == "after_move":
                    ui.print_board(state, perspective_white=(human_color == chess.WHITE))
            except BlindChessError as e:
                ui.print_error(str(e))
                continue
        else:
            # Engine turn
            print(f"{profile.name} is thinking...")
            try:
                eng_move = engine_mgr.play_move(state.board, profile=profile)
                rec = state.push_move(eng_move)
                print(f"{profile.name} played: {rec.san}")
                if config.board_visibility == "after_move":
                    ui.print_board(state, perspective_white=(human_color == chess.WHITE))
            except Exception as e:
                ui.print_error(f"Engine move error: {e}")
                break

    # Game conclusion
    is_over, status_text, result_str = state.get_game_status()
    print(f"\nGame Over: {status_text}")
    session.close(result=result_str)

    # Offer to save game
    if state.history:
        pgn_text = export_game_to_pgn(
            state,
            white_name="Player" if human_color == chess.WHITE else profile.name,
            black_name=profile.name if human_color == chess.WHITE else "Player",
            result=result_str or "*",
        )
        if db_mgr:
            db_mgr.save_game(pgn_text, "White", "Black", result_str or "*", session.session_id)
            print("Game successfully saved to training database.")


def run_blindfold_drills(config: AppConfig, db_mgr: Optional[DatabaseManager], level: int = 1) -> None:
    """Run interactive blindfold spatial visualization exercises."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    session = ActiveSession(mode="blindfold_drills", level=level, db_mgr=db_mgr)
    print(f"\n--- BLINDFOLD SPATIAL REASONING DRILLS (Level {level}) ---")
    print("Answer without looking at a chessboard. Type 'quit' to return to menu.\n")

    solved = 0
    total = 0

    while True:
        drill = get_blindfold_exercise_by_level(level)
        print("=" * 55)
        print(f"Exercise: {drill.title}")
        print(f"{drill.prompt}\n")

        hints_used = 0
        while True:
            ans = ui.prompt("Your answer> ").strip().lower()
            if ans == "quit":
                break
            if ans == "hint":
                hints_used += 1
                session.record_hint()
                print(f"Hint: {drill.hint}")
                continue

            if ans in [c.lower() for c in drill.correct_answers]:
                print(f"CORRECT! {drill.explanation}\n")
                solved += 1
                total += 1
                if db_mgr:
                    db_mgr.record_tactical_result(session.session_id, drill.id, drill.category, True, hints_used)
                break
            else:
                print(f"Not quite. Try again, or type 'hint' / 'skip'.")
                if ans == "skip":
                    print(f"Solution: {drill.explanation}\n")
                    total += 1
                    if db_mgr:
                        db_mgr.record_tactical_result(session.session_id, drill.id, drill.category, False, hints_used)
                    break

        if ans == "quit":
            break

    session.close(notes=f"Solved {solved}/{total} drills.")
    print(f"Session finished. Solved: {solved}/{total}.")


def run_tactics_trainer(config: AppConfig, db_mgr: Optional[DatabaseManager]) -> None:
    """Run curated tactical training drills."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    session = ActiveSession(mode="tactics", level=config.training_level, db_mgr=db_mgr)
    tactical_sess = TacticalSession(BUILTIN_PUZZLES)

    print("\n--- TACTICAL TRAINING SUBSYSTEM ---")
    print("Solve tactical puzzles with standard move notation. Type 'hint' or 'board' anytime.\n")

    while True:
        puz = tactical_sess.start_puzzle()
        print("=" * 55)
        print(f"Puzzle: {puz.title} (Theme: {puz.theme}, Difficulty: {puz.difficulty}/5)")
        print(f"Position FEN: {puz.fen}")
        turn_str = "White" if tactical_sess.current_board.turn == chess.WHITE else "Black"
        print(f"{turn_str} to move.")

        if config.board_visibility == "normal":
            ui.print_board(BoardState(puz.fen))

        while not tactical_sess.solved:
            user_in = ui.prompt(f"{turn_str}> ")
            if user_in == "quit":
                session.close()
                return
            if user_in == "hint":
                session.record_hint()
                print(tactical_sess.get_hint())
                continue
            if user_in == "board":
                session.record_reveal()
                ui.print_board(BoardState(tactical_sess.current_board.fen()))
                continue

            success, msg = tactical_sess.submit_move(user_in)
            print(msg)

        if db_mgr:
            db_mgr.record_tactical_result(
                session.session_id,
                puz.id,
                puz.theme,
                tactical_sess.solved,
                tactical_sess.hints_used,
            )

        cont = ui.prompt("Next puzzle? (y/n): ")
        if cont.lower().startswith("n"):
            break

    session.close()


def run_calculation_trainer(
    config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]
) -> None:
    """Run structured candidate calculation training session."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    session = ActiveSession(mode="calculation", level=config.training_level, db_mgr=db_mgr)

    sample_positions = [
        ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4", "White to move (Italian Game)"),
        ("rnbqkb1r/pp2pppp/3p1n2/8/3NP3/8/PPP2PPP/RNBQKB1R w KQkq - 1 5", "White to move (Open Sicilian)"),
        ("r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1B3/PPP2PPP/R2Q1RK1 w - - 4 9", "White to move (Dragon Sicilian)"),
    ]

    fen, label = random.choice(sample_positions)
    board = chess.Board(fen)

    print("\n--- CALCULATION & CANDIDATE MOVE TRAINING ---")
    print(f"Position: {label}")
    turn_str = "White" if board.turn == chess.WHITE else "Black"
    print(f"{turn_str} to move.")
    print("Think first: identify candidate moves and opponent replies before consulting the engine.\n")

    candidate_san = ui.prompt("1. Enter your candidate move (e.g. 'd4' or 'O-O'): ")
    if candidate_san == "quit":
        session.close()
        return

    predicted_opp = ui.prompt("2. Predict opponent's strongest reply (e.g. 'Nf6'): ")
    user_eval = ui.prompt("3. Your estimated evaluation (e.g. 'equal', 'slight white edge', '+0.5'): ")

    print("\nAnalyzing position with Stockfish...")
    try:
        attempt = evaluate_calculation_attempt(
            board=board,
            user_san=candidate_san,
            predicted_replies=[predicted_opp] if predicted_opp else [],
            user_eval=user_eval,
            engine_mgr=engine_mgr,
            depth=config.analysis_depth,
        )

        print("\n" + "=" * 50)
        print("CALCULATION ASSESSMENT")
        print("=" * 50)
        print(f"Your Move:           {attempt.candidate_san}")
        print(f"Engine's Best Move:  {attempt.engine_best_san or 'N/A'}")
        print(f"Top Choice Match:    {'YES' if attempt.is_engine_top_choice else 'NO'}")
        if attempt.engine_eval_before:
            print(f"Eval Before:         {attempt.engine_eval_before}")
        if attempt.engine_eval_after:
            print(f"Eval After:          {attempt.engine_eval_after}")

        if attempt.missed_resources:
            print("\nTactical Observations:")
            for note in attempt.missed_resources:
                print(f" • {note}")
        else:
            print("\nNo immediate blunders detected in candidate line.")

        if db_mgr:
            db_mgr.record_calculation_drill(
                session_id=session.session_id,
                fen=fen,
                candidate_san=attempt.candidate_san,
                predicted_replies=attempt.predicted_replies,
                user_eval=attempt.user_eval_estimate,
                engine_best_san=attempt.engine_best_san,
                is_engine_top=attempt.is_engine_top_choice,
                accuracy_score=attempt.accuracy_score,
                missed_resources=attempt.missed_resources,
            )
    except Exception as e:
        ui.print_error(f"Calculation analysis error: {e}")

    session.close()


def run_variation_explorer(config: AppConfig, engine_mgr: Optional[EngineManager], start_fen: Optional[str] = None) -> None:
    """Run interactive variation explorer with independent branches and MultiPV."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    tree = VariationTree(start_fen)

    print("\n--- VARIATION EXPLORER ---")
    print("Commands: 'back', 'forward', 'root', 'analyze', 'delete', 'pgn', 'board', 'quit'\n")

    while True:
        cur_board = tree.current_board()
        line_str = tree.format_current_line()
        turn_str = "White" if cur_board.turn == chess.WHITE else "Black"
        print(f"Active line: {line_str}")
        print(f"{turn_str} to move ({cur_board.move_number}.)")

        cmd_in = ui.prompt("var-explorer> ")
        if cmd_in in ("quit", "exit"):
            break
        elif cmd_in in ("back", "undo"):
            tree.step_back()
        elif cmd_in in ("forward", "redo"):
            tree.step_forward()
        elif cmd_in == "root":
            tree.jump_to_root()
        elif cmd_in == "delete":
            tree.delete_current_branch()
            print("Deleted active branch.")
        elif cmd_in == "board":
            ui.print_board(BoardState(cur_board.fen()))
        elif cmd_in == "pgn":
            print("\n" + tree.export_to_pgn_string() + "\n")
        elif cmd_in == "analyze":
            if engine_mgr and engine_mgr.is_available and engine_mgr.engine:
                print(f"Analyzing position (MultiPV: {config.multipv})...")
                res = analyse_position(
                    engine_mgr, cur_board, depth=config.analysis_depth, time_limit=config.analysis_time_limit, multipv=config.multipv
                )
                for line in res.lines:
                    print(line.format_line())
            else:
                print("Engine not available.")
        else:
            try:
                tree.add_move(cmd_in)
                print(f"Added move: {cmd_in}")
            except Exception as e:
                ui.print_error(f"Cannot add move: {e}")


def run_strategy_coach(
    config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]
) -> None:
    """Run strategic position training with structured questioning."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    fen = "r1b2rk1/pp1nqppp/2p1pn2/3p4/2PP4/2N1PN2/PP2BPPP/R2Q1RK1 w - - 2 9"
    board = chess.Board(fen)

    print("\n--- STRATEGIC THINKING COACH ---")
    print("Reason before calculating: answer structured positional questions.")
    questions = generate_strategic_questions(board)

    for idx, q in enumerate(questions, start=1):
        print(f"\nQuestion {idx} [{q['category']}]:")
        print(f"{q['question']}")
        ans = ui.prompt("Your reasoning> ")
        if ans == "quit":
            return
        print(f"Insight: {q['answer']}\n")

    if engine_mgr and engine_mgr.is_available and engine_mgr.engine:
        res = analyse_position(engine_mgr, board, depth=config.analysis_depth, time_limit=1.5, multipv=1)
        if res.best_move:
            rationale = explain_move_rationale(board, res.best_move, is_engine_best=True)
            print("=" * 50)
            print("ENGINE STRATEGIC ALIGNMENT")
            print("=" * 50)
            print(rationale)


def run_opening_practice(config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]) -> None:
    """Drill opening repertoire recall."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    print("\nAvailable Opening Repertoires:")
    for idx, rep in enumerate(BUILTIN_REPERTOIRES, start=1):
        side = "White" if rep.user_side == chess.WHITE else "Black"
        print(f"  {idx}. {rep.name} ({rep.eco}) - Playing as {side}")

    choice = ui.prompt("\nSelect repertoire (1-5): ")
    try:
        sel_idx = int(choice) - 1
        rep = BUILTIN_REPERTOIRES[sel_idx]
    except Exception:
        rep = BUILTIN_REPERTOIRES[0]

    trainer = OpeningTrainer(rep)
    print(f"\nDrilling: {rep.name}")
    print(f"{rep.description}")
    print("Enter the repertoire moves in order. Type 'board' to peek.\n")

    # If Black, play White's first move
    first_opp = trainer.play_repertoire_opponent_move()
    if first_opp:
        print(f"Opponent opens: {first_opp}")

    while not trainer.completed:
        user_mv = ui.prompt("Your move> ")
        if user_mv == "quit":
            break
        if user_mv == "board":
            ui.print_board(BoardState(trainer.board.fen()))
            continue

        ok, msg = trainer.submit_user_move(user_mv)
        print(msg)


def run_endgame_practice(config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]) -> None:
    """Drill fundamental endgame positions."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    print("\nFundamental Endgame Positions:")
    for idx, eg in enumerate(BUILTIN_ENDGAMES, start=1):
        print(f"  {idx}. {eg.name} ({eg.category})")

    choice = ui.prompt("\nSelect position (1-4): ")
    try:
        sel_idx = int(choice) - 1
        eg = BUILTIN_ENDGAMES[sel_idx]
    except Exception:
        eg = BUILTIN_ENDGAMES[0]

    print(f"\n{eg.name}")
    print(f"Objective: {eg.objective}")
    print(f"Key Concept: {eg.key_concept}\n")

    board = chess.Board(eg.fen)
    tb_status = probe_tablebase(board, config.tablebase_path)
    if tb_status:
        print(f"Tablebase Result: {tb_status}\n")

    run_game_loop(config, engine_mgr, db_mgr, user_side="white", start_fen=eg.fen)


def run_review_mode(config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager], pgn_path: Optional[str] = None) -> None:
    """Review a completed game or imported PGN file."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    if pgn_path:
        p = Path(pgn_path)
        if not p.is_file():
            ui.print_error(f"PGN file not found: {pgn_path}")
            return
        game = load_game_from_pgn(p)
        state = load_game_into_board_state(game)
    else:
        # Check last saved game in DB
        if not db_mgr:
            print("No database connection.")
            return
        cur = db_mgr.conn.execute("SELECT pgn_content FROM saved_games ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        if not row:
            print("No saved games found to review.")
            return
        game = load_game_from_pgn(row["pgn_content"])
        state = load_game_into_board_state(game)

    print(f"\nReviewing game ({len(state.history)} moves)...")
    summary = review_game(state, engine_mgr, depth=config.analysis_depth, time_limit_per_move=0.4)
    print(summary.format_summary_text())

    for item in summary.items:
        if item.category in ("Mistake", "Blunder", "Missed Win"):
            print(f"Ply {item.ply}: Played {item.san} -> [{item.category}] {item.explanation}")
            if item.engine_best_san:
                print(f"       Engine preferred: {item.engine_best_san} ({item.principal_continuation or ''})")


def display_statistics(db_mgr: Optional[DatabaseManager], config: AppConfig) -> None:
    """Display comprehensive training statistics and adaptive recommendations."""
    if not db_mgr:
        print("Database not available.")
        return

    stats = compute_training_statistics(db_mgr)
    rec = evaluate_adaptive_difficulty(db_mgr, config.training_level)

    print("\n" + "=" * 55)
    print("BLINDCHESS TRAINING METRICS & PROGRESS")
    print("=" * 55)
    print(f"Total Sessions:             {stats.total_sessions}")
    print(f"Total Moves Played:         {stats.total_moves}")
    print(f"Total Training Time:        {stats.total_training_minutes} minutes")
    print(f"Tactical Puzzles Solved:    {stats.tactics_solved} / {stats.tactics_attempted} ({stats.tactics_success_rate}%)")
    print(f"Calculation Drills:         {stats.calc_drills_count} (Avg Accuracy: {stats.calc_accuracy_avg}%)")
    print(f"Board Reveals per 100 moves:{stats.reveal_frequency_per_100_moves}")
    print(f"Hints Requested:            {stats.total_hints}")

    if stats.tactics_by_theme:
        print("\nPerformance by Tactical Theme:")
        for theme, th_data in stats.tactics_by_theme.items():
            print(f"  • {theme:<24}: {th_data['solved']}/{th_data['attempted']} ({th_data['success_rate']}%)")

    print("\n" + "-" * 55)
    print(f"Adaptive Training System: [Action: {rec.action.upper()}]")
    print(f"Current Level: Level {rec.current_level} -> Recommended: Level {rec.recommended_level}")
    print(f"Rationale: {rec.rationale}")
    print("=" * 55 + "\n")
