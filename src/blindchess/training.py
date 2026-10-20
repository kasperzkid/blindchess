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
    c = ui.palette
    state = BoardState(start_fen) if start_fen else BoardState()
    session = ActiveSession(mode="game", level=config.training_level, db_mgr=db_mgr)

    human_color = chess.WHITE if user_side.lower() == "white" else chess.BLACK
    profile = get_profile(opponent_level)

    eng_label = profile.name if (engine_mgr and engine_mgr.is_available) else "2-Player Local"
    vis_label = "Visible" if (show_board or config.board_visibility == "normal") else "Hidden (Blindfold)"

    game_info_lines = [
        f"Side: {c.accent_bold(user_side.capitalize())}   Opponent: {c.highlight(eng_label)}   Board: {c.muted(vis_label)}",
        f"Input moves in SAN (e.g. {c.highlight('e4')}, {c.highlight('Nf3')}, {c.highlight('O-O')}) or coordinates ({c.highlight('e2e4')}).",
    ]
    print("\n" + ui.render_panel("Match Started", game_info_lines, width=64, border_style="accent") + "\n")

    ui.print_shortcut_bar([
        ("board", "Peek"),
        ("undo", "Takeback"),
        ("moves", "History"),
        ("status", "Balance"),
        ("hint", "Hint"),
        ("quit", "Exit"),
    ])
    print()

    if show_board or config.board_visibility == "normal":
        ui.print_board(state, perspective_white=(human_color == chess.WHITE))

    while not state.is_game_over():
        is_human_turn = (state.turn == human_color)

        if is_human_turn or not (engine_mgr and engine_mgr.is_available and engine_mgr.engine):
            player_badge = c.accent_bold(state.turn_name)
            move_badge = c.muted(f"Move {state.move_number}")
            player_prompt = f"[{player_badge} • {move_badge}] "
            user_input = ui.prompt(player_prompt)

            if not user_input:
                continue

            if is_command(user_input):
                cmd, args = parse_command(user_input)
                if cmd == "quit":
                    ui.print_message("Exiting game to main menu.")
                    break
                elif cmd == "help":
                    print("\n" + get_help_text("game") + "\n")
                elif cmd == "board":
                    if strict_blindfold:
                        ui.print_warning("Strict blindfold mode active: manual board reveals are disabled.")
                    else:
                        session.record_reveal()
                        ui.print_board(state, perspective_white=(human_color == chess.WHITE))
                elif cmd == "moves":
                    moves_str = " ".join(f"{r.san}" for r in state.history)
                    ui.print_message(moves_str or "(None yet)", prefix="Move History")
                elif cmd == "fen":
                    ui.print_message(state.board.fen(), prefix="FEN")
                elif cmd == "status":
                    is_over, status_desc, _ = state.get_game_status()
                    bal = state.get_material_balance()
                    diff_str = f"{bal['diff']:+d}" if bal["diff"] != 0 else "Even"
                    ui.print_message(
                        f"{status_desc} | Material Diff: {diff_str} (White: {bal['white']}, Black: {bal['black']})",
                        prefix="Status",
                    )
                elif cmd == "undo":
                    if engine_mgr and engine_mgr.is_available:
                        undone = state.undo_full_turn()
                        ui.print_success(f"Took back full turn ({len(undone)} plies).")
                    else:
                        undone_rec = state.undo_move()
                        ui.print_success(f"Took back move: {undone_rec.san if undone_rec else 'None'}")
                elif cmd == "redo":
                    redone = state.redo_move()
                    if redone:
                        ui.print_success(f"Replayed move: {redone.san}")
                    else:
                        ui.print_message("No undone moves to replay.")
                elif cmd == "hint":
                    session.record_hint()
                    if engine_mgr and engine_mgr.is_available and engine_mgr.engine:
                        res = analyse_position(engine_mgr, state.board, depth=10, time_limit=1.0, multipv=1)
                        if res.best_san:
                            ui.print_warning(f"Engine candidate hint: Consider focusing on {res.best_san}.")
                    else:
                        ui.print_message("Focus on central piece development and ensuring king safety.", prefix="Hint")
                elif cmd == "save":
                    pgn_txt = export_game_to_pgn(
                        state,
                        white_name="Player" if human_color == chess.WHITE else profile.name,
                        black_name=profile.name if human_color == chess.WHITE else "Player",
                    )
                    if db_mgr:
                        gid = db_mgr.save_game(pgn_txt, "White", "Black", "*", session.session_id)
                        ui.print_success(f"Game saved to local database (Session Game ID: {gid}).")
                continue

            # Regular move entry
            try:
                rec = state.push_move(user_input)
                check_flag = f" {c.warning('[CHECK]')}" if rec.is_check else ""
                mate_flag = f" {c.success_bold('[CHECKMATE]')}" if rec.is_checkmate else ""
                ui.print_message(f"{c.highlight(rec.san)}{check_flag}{mate_flag}", prefix="Recorded")
                if config.board_visibility == "after_move":
                    ui.print_board(state, perspective_white=(human_color == chess.WHITE))
            except BlindChessError as e:
                ui.print_error(str(e.message), hint=e.actionable_hint)
                continue
        else:
            # Engine turn
            print(f" {c.muted('•')} {profile.name} is calculating reply...")
            try:
                eng_move = engine_mgr.play_move(state.board, profile=profile)
                rec = state.push_move(eng_move)
                check_flag = f" {c.warning('[CHECK]')}" if rec.is_check else ""
                mate_flag = f" {c.error_bold('[CHECKMATE]')}" if rec.is_checkmate else ""
                ui.print_message(f"{c.highlight(rec.san)}{check_flag}{mate_flag}", prefix=profile.name)
                if config.board_visibility == "after_move":
                    ui.print_board(state, perspective_white=(human_color == chess.WHITE))
            except Exception as e:
                ui.print_error(f"Engine move error: {e}")
                break

    # Game conclusion
    is_over, status_text, result_str = state.get_game_status()
    conclusion_lines = [
        f"Outcome: {c.highlight(status_text)}",
        f"Result:  {c.accent_bold(result_str or '*')}  |  Total Moves: {state.ply_count} plies",
    ]
    print("\n" + ui.render_panel("Game Concluded", conclusion_lines, width=54, border_style="success") + "\n")
    session.close(result=result_str)

    # Persist game
    if state.history:
        pgn_text = export_game_to_pgn(
            state,
            white_name="Player" if human_color == chess.WHITE else profile.name,
            black_name=profile.name if human_color == chess.WHITE else "Player",
            result=result_str or "*",
        )
        if db_mgr:
            db_mgr.save_game(pgn_text, "White", "Black", result_str or "*", session.session_id)
            ui.print_success("Match recorded into local training history.")


def run_blindfold_drills(config: AppConfig, db_mgr: Optional[DatabaseManager], level: int = 1) -> None:
    """Run interactive blindfold spatial visualization exercises."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette
    session = ActiveSession(mode="blindfold_drills", level=level, db_mgr=db_mgr)

    ui.print_divider(f"Spatial Visualization Drills (Level {level})")
    print(f"  {c.muted('Visualize the 64 squares internally. Type')} {c.accent_bold('quit')} {c.muted('to return to menu.')}\n")

    solved = 0
    total = 0

    while True:
        drill = get_blindfold_exercise_by_level(level)
        drill_lines = [
            f"Category: {c.accent_bold(drill.category.replace('_', ' ').title())}",
            "",
            drill.prompt,
        ]
        card = ui.render_panel(f"Exercise: {drill.title}", drill_lines, width=72, border_style="accent")
        print("\n" + card + "\n")
        ui.print_shortcut_bar([("hint", "Hint"), ("skip", "Skip"), ("quit", "Menu")])
        print()

        hints_used = 0
        while True:
            ans = ui.prompt("Your answer: ").strip().lower()
            if ans == "quit":
                break
            if ans == "hint":
                hints_used += 1
                session.record_hint()
                ui.print_warning(drill.hint)
                continue

            if ans in [corr.lower() for corr in drill.correct_answers]:
                ui.print_success(f"Correct! {drill.explanation}")
                solved += 1
                total += 1
                if db_mgr:
                    db_mgr.record_tactical_result(session.session_id, drill.id, drill.category, True, hints_used)
                break
            else:
                if ans == "skip":
                    ui.print_message(f"Solution: {drill.explanation}", prefix="Revealed")
                    total += 1
                    if db_mgr:
                        db_mgr.record_tactical_result(session.session_id, drill.id, drill.category, False, hints_used)
                    break
                ui.print_warning("Incorrect attempt. Re-visualize and try again, or type 'hint' / 'skip'.")

        if ans == "quit":
            break

    session.close(notes=f"Solved {solved}/{total} drills.")
    ui.print_message(f"Drill session complete. Accuracy: {solved}/{total} solved.", prefix="Summary")


def run_tactics_trainer(config: AppConfig, db_mgr: Optional[DatabaseManager]) -> None:
    """Run curated tactical training drills."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette
    session = ActiveSession(mode="tactics", level=config.training_level, db_mgr=db_mgr)
    tactical_sess = TacticalSession(BUILTIN_PUZZLES)

    ui.print_divider("Tactical Puzzle Training")
    print(f"  {c.muted('Solve tactical motifs without visual hints. Type')} {c.accent_bold('hint')} {c.muted('for graduated clues.')}\n")

    while True:
        puz = tactical_sess.start_puzzle()
        turn_str = "White" if tactical_sess.current_board.turn == chess.WHITE else "Black"
        diff_stars = "★" * puz.difficulty + "☆" * (5 - puz.difficulty)

        card_lines = [
            f"Theme: {c.accent_bold(puz.theme)}    Difficulty: {c.warning(diff_stars)} ({puz.difficulty}/5)",
            f"Turn:  {c.highlight(turn_str + ' to move')}",
            f"FEN:   {c.muted(puz.fen)}",
        ]
        card = ui.render_panel(puz.title, card_lines, width=72, border_style="accent")
        print("\n" + card + "\n")
        ui.print_shortcut_bar([("board", "Peek"), ("hint", "Graduated Hint"), ("quit", "Menu")])
        print()

        if config.board_visibility == "normal":
            ui.print_board(BoardState(puz.fen))

        while not tactical_sess.solved:
            user_in = ui.prompt(f"[{c.accent(turn_str)}] ❯ ")
            if user_in == "quit":
                session.close()
                return
            if user_in == "hint":
                session.record_hint()
                ui.print_warning(tactical_sess.get_hint())
                continue
            if user_in == "board":
                session.record_reveal()
                ui.print_board(BoardState(tactical_sess.current_board.fen()))
                continue

            success, msg = tactical_sess.submit_move(user_in)
            if success:
                ui.print_success(msg)
            else:
                ui.print_error(msg)

        if db_mgr:
            db_mgr.record_tactical_result(
                session.session_id,
                puz.id,
                puz.theme,
                tactical_sess.solved,
                tactical_sess.hints_used,
            )

        cont = ui.prompt("Continue to next puzzle? (Y/n): ")
        if cont.lower().startswith("n"):
            break

    session.close()


def run_calculation_trainer(
    config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]
) -> None:
    """Run structured candidate calculation training session."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette
    session = ActiveSession(mode="calculation", level=config.training_level, db_mgr=db_mgr)

    sample_positions = [
        ("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4", "Italian Game (Two Knights)"),
        ("rnbqkb1r/pp2pppp/3p1n2/8/3NP3/8/PPP2PPP/RNBQKB1R w KQkq - 1 5", "Open Sicilian Defense"),
        ("r1bq1rk1/pp2ppbp/2np1np1/8/2BNP3/2N1B3/PPP2PPP/R2Q1RK1 w - - 4 9", "Sicilian Dragon (Yugoslav Setup)"),
    ]

    fen, label = random.choice(sample_positions)
    board = chess.Board(fen)
    turn_str = "White" if board.turn == chess.WHITE else "Black"

    ui.print_divider("Candidate Calculation Training")
    card_lines = [
        f"Position: {c.highlight(label)}",
        f"Turn:     {c.accent_bold(turn_str + ' to move')}",
        "",
        c.muted("Formulate your candidate move and anticipate the opponent's reply before consulting the engine."),
    ]
    print("\n" + ui.render_panel("Calculation Drill", card_lines, width=72, border_style="accent") + "\n")

    candidate_san = ui.prompt("Step 1: Enter your candidate move (e.g. 'd4', 'O-O'): ")
    if candidate_san == "quit":
        session.close()
        return

    predicted_opp = ui.prompt("Step 2: Predict opponent's strongest reply (e.g. 'Nf6'): ")
    user_eval = ui.prompt("Step 3: Your estimated evaluation ('equal', 'slight white edge', '+0.5'): ")

    print(f"\n {c.muted('•')} Analyzing position with Stockfish MultiPV...")
    try:
        attempt = evaluate_calculation_attempt(
            board=board,
            user_san=candidate_san,
            predicted_replies=[predicted_opp] if predicted_opp else [],
            user_eval=user_eval,
            engine_mgr=engine_mgr,
            depth=config.analysis_depth,
        )

        match_badge = c.success_bold("YES (Optimal Move)") if attempt.is_engine_top_choice else c.warning("NO (Alternative Preferred)")
        scorecard_rows = [
            ["Candidate Move", attempt.candidate_san],
            ["Stockfish Top Choice", attempt.engine_best_san or "N/A"],
            ["Optimal Match", match_badge],
            ["Evaluation Before", attempt.engine_eval_before or "N/A"],
            ["Evaluation After", attempt.engine_eval_after or "N/A"],
            ["Your Estimate", attempt.user_eval_estimate or "(None)"],
        ]

        ui.print_table(["Metric", "Assessment"], scorecard_rows)

        if attempt.missed_resources:
            ui.print_divider("Tactical Observations")
            for note in attempt.missed_resources:
                ui.print_warning(note)
        else:
            ui.print_success("No immediate blunders or missed forced checkmates detected.")

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
        ui.print_error(f"Calculation evaluation error: {e}")

    session.close()


def run_variation_explorer(config: AppConfig, engine_mgr: Optional[EngineManager], start_fen: Optional[str] = None) -> None:
    """Run interactive variation explorer with independent branches and MultiPV."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette
    tree = VariationTree(start_fen)

    ui.print_divider("Variation Explorer")
    ui.print_shortcut_bar([
        ("analyze", "MultiPV"),
        ("back", "Back"),
        ("forward", "Forward"),
        ("board", "Peek"),
        ("pgn", "Export"),
        ("quit", "Exit"),
    ])
    print()

    while True:
        cur_board = tree.current_board()
        line_str = tree.format_current_line()
        turn_str = "White" if cur_board.turn == chess.WHITE else "Black"

        print(f" {c.muted('Line:')} {c.highlight(line_str)}")
        print(f" {c.muted('Turn:')} {c.accent_bold(turn_str)} (Move {cur_board.move_number}.)")

        cmd_in = ui.prompt("var-explorer ❯ ")
        if cmd_in in ("quit", "exit"):
            break
        elif cmd_in in ("back", "undo"):
            tree.step_back()
        elif cmd_in in ("forward", "redo"):
            tree.step_forward()
        elif cmd_in == "root":
            tree.jump_to_root()
            ui.print_message("Jumped to root position.")
        elif cmd_in == "delete":
            tree.delete_current_branch()
            ui.print_warning("Deleted active branch.")
        elif cmd_in == "board":
            ui.print_board(BoardState(cur_board.fen()))
        elif cmd_in == "pgn":
            print("\n" + tree.export_to_pgn_string() + "\n")
        elif cmd_in == "analyze":
            if engine_mgr and engine_mgr.is_available and engine_mgr.engine:
                print(f" {c.muted('•')} Computing {config.multipv} principal variations (depth={config.analysis_depth})...")
                res = analyse_position(
                    engine_mgr, cur_board, depth=config.analysis_depth, time_limit=config.analysis_time_limit, multipv=config.multipv
                )
                rows = []
                for line in res.lines:
                    pv_short = " ".join(line.pv_sans[:5])
                    rows.append([f"#{line.rank}", line.san, line.score.format_white_perspective(), str(line.depth), pv_short])
                ui.print_table(["Rank", "Move", "Score", "Depth", "Continuation"], rows)
            else:
                ui.print_warning("Stockfish engine not available for MultiPV analysis.")
        else:
            try:
                tree.add_move(cmd_in)
                ui.print_message(f"Added move: {cmd_in}")
            except Exception as e:
                ui.print_error(f"Cannot add move: {e}")


def run_strategy_coach(
    config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]
) -> None:
    """Run strategic position training with structured questioning."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette
    fen = "r1b2rk1/pp1nqppp/2p1pn2/3p4/2PP4/2N1PN2/PP2BPPP/R2Q1RK1 w - - 2 9"
    board = chess.Board(fen)

    ui.print_divider("Strategic Position Coach")
    print(f"  {c.muted('Formulate positional plans before calculating tactical lines.')}\n")
    questions = generate_strategic_questions(board)

    for idx, q in enumerate(questions, start=1):
        q_lines = [
            f"Concept: {c.accent_bold(q['category'])}",
            "",
            q["question"],
        ]
        card = ui.render_panel(f"Strategic Question {idx}/{len(questions)}", q_lines, width=72, border_style="accent")
        print("\n" + card + "\n")

        ans = ui.prompt("Your reasoning: ")
        if ans == "quit":
            return
        ui.print_message(q["answer"], prefix="Strategic Insight")

    if engine_mgr and engine_mgr.is_available and engine_mgr.engine:
        res = analyse_position(engine_mgr, board, depth=config.analysis_depth, time_limit=1.5, multipv=1)
        if res.best_move:
            rationale = explain_move_rationale(board, res.best_move, is_engine_best=True)
            print("\n" + ui.render_panel("Engine Positional Alignment", [rationale], width=72, border_style="success") + "\n")


def run_opening_practice(config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]) -> None:
    """Drill opening repertoire recall."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette

    ui.print_divider("Opening Repertoire Practice")
    rows = []
    for idx, rep in enumerate(BUILTIN_REPERTOIRES, start=1):
        side = "White" if rep.user_side == chess.WHITE else "Black"
        rows.append([str(idx), rep.name, rep.eco, side])
    ui.print_table(["#", "Repertoire", "ECO", "Player Side"], rows)

    choice = ui.prompt("Select repertoire (1-5): ")
    try:
        sel_idx = int(choice) - 1
        rep = BUILTIN_REPERTOIRES[sel_idx]
    except Exception:
        rep = BUILTIN_REPERTOIRES[0]

    trainer = OpeningTrainer(rep)
    card_lines = [
        f"Opening: {c.highlight(rep.name)} ({rep.eco})",
        rep.description,
        c.muted("Recall the sequence without looking at the board. Type 'board' to peek."),
    ]
    print("\n" + ui.render_panel("Repertoire Line", card_lines, width=72, border_style="accent") + "\n")

    first_opp = trainer.play_repertoire_opponent_move()
    if first_opp:
        ui.print_message(f"Opponent opens: {first_opp}")

    while not trainer.completed:
        user_mv = ui.prompt("Your move: ")
        if user_mv == "quit":
            break
        if user_mv == "board":
            ui.print_board(BoardState(trainer.board.fen()))
            continue

        ok, msg = trainer.submit_user_move(user_mv)
        if ok:
            ui.print_success(msg)
        else:
            ui.print_warning(msg)


def run_endgame_practice(config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]) -> None:
    """Drill fundamental endgame positions."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette

    ui.print_divider("Endgame Fundamentals Practice")
    rows = []
    for idx, eg in enumerate(BUILTIN_ENDGAMES, start=1):
        rows.append([str(idx), eg.name, eg.category])
    ui.print_table(["#", "Endgame Concept", "Category"], rows)

    choice = ui.prompt("Select position (1-4): ")
    try:
        sel_idx = int(choice) - 1
        eg = BUILTIN_ENDGAMES[sel_idx]
    except Exception:
        eg = BUILTIN_ENDGAMES[0]

    eg_lines = [
        f"Objective: {c.highlight(eg.objective)}",
        f"Key Principle: {c.muted(eg.key_concept)}",
    ]
    print("\n" + ui.render_panel(eg.name, eg_lines, width=72, border_style="accent") + "\n")

    board = chess.Board(eg.fen)
    tb_status = probe_tablebase(board, config.tablebase_path)
    if tb_status:
        ui.print_message(f"Tablebase Result: {tb_status}", prefix="Syzygy")

    run_game_loop(config, engine_mgr, db_mgr, user_side="white", start_fen=eg.fen)


def run_review_mode(config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager], pgn_path: Optional[str] = None) -> None:
    """Review a completed game or imported PGN file."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette

    if pgn_path:
        p = Path(pgn_path)
        if not p.is_file():
            ui.print_error(f"PGN file not found: {pgn_path}")
            return
        game = load_game_from_pgn(p)
        state = load_game_into_board_state(game)
    else:
        if not db_mgr:
            ui.print_warning("No database connection available.")
            return
        cur = db_mgr.conn.execute("SELECT pgn_content FROM saved_games ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        if not row:
            ui.print_message("No saved games found to review in training database.")
            return
        game = load_game_from_pgn(row["pgn_content"])
        state = load_game_into_board_state(game)

    print(f"\n {c.muted('•')} Reviewing game moves ({len(state.history)} plies)...")
    summary = review_game(state, engine_mgr, depth=config.analysis_depth, time_limit_per_move=0.4)

    summary_rows = [
        ["Total Moves Analyzed", str(summary.total_moves)],
        ["Inaccuracies (?!)", str(summary.inaccuracies)],
        ["Mistakes (?)", str(summary.mistakes)],
        ["Blunders (??)", str(summary.blunders)],
        ["Missed Checkmates", str(summary.missed_wins)],
    ]
    ui.print_table(["Metric", "Count"], summary_rows)

    mistake_items = [it for it in summary.items if it.category in ("Mistake", "Blunder", "Missed Win")]
    if mistake_items:
        ui.print_divider("Key Diagnostic Moments")
        for item in mistake_items:
            cat_color = c.error_bold if item.category in ("Blunder", "Missed Win") else c.warning_bold
            print(f"  {cat_color(f'Ply {item.ply}')}: {c.highlight(item.san)} -> [{cat_color(item.category)}] {item.explanation}")
            if item.engine_best_san:
                print(f"         {c.muted('Engine line:')} {c.accent_bold(item.engine_best_san)} ({item.principal_continuation or ''})")
        print()


def display_statistics(db_mgr: Optional[DatabaseManager], config: AppConfig) -> None:
    """Display comprehensive training statistics and adaptive recommendations."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette

    if not db_mgr:
        ui.print_warning("Database not available.")
        return

    stats = compute_training_statistics(db_mgr)
    rec = evaluate_adaptive_difficulty(db_mgr, config.training_level)

    ui.print_divider("Training Metrics & Performance")

    overview_rows = [
        ["Total Training Sessions", str(stats.total_sessions)],
        ["Total Moves Played", str(stats.total_moves)],
        ["Total Training Duration", f"{stats.total_training_minutes} minutes"],
        ["Tactical Solve Rate", f"{stats.tactics_solved} / {stats.tactics_attempted} ({stats.tactics_success_rate}%)"],
        ["Candidate Calculation Accuracy", f"{stats.calc_accuracy_avg}% ({stats.calc_drills_count} drills)"],
        ["Board Reveals per 100 Moves", f"{stats.reveal_frequency_per_100_moves}"],
        ["Hints Requested", str(stats.total_hints)],
    ]
    ui.print_table(["Metric", "Recorded Value"], overview_rows)

    if stats.tactics_by_theme:
        theme_rows = []
        for theme, th_data in stats.tactics_by_theme.items():
            theme_rows.append([theme, str(th_data["solved"]), str(th_data["attempted"]), f"{th_data['success_rate']}%"])
        ui.print_table(["Tactical Theme", "Solved", "Attempted", "Accuracy"], theme_rows)

    # Adaptive recommendation card
    action_color = c.success_bold if rec.action == "promote" else (c.warning_bold if rec.action == "demote" else c.accent_bold)
    card_lines = [
        f"Current Level: Level {rec.current_level}   Recommended: Level {rec.recommended_level}   Action: {action_color(rec.action.upper())}",
        f"Rationale: {c.muted(rec.rationale)}",
    ]
    print(ui.render_panel("Adaptive Difficulty Assessment", card_lines, width=76, border_style="accent") + "\n")
