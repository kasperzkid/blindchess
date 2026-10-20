"""Interactive training routines and main loop orchestration for BlindChess."""

from pathlib import Path
import random
import time
from typing import Optional
import chess

from blindchess.adaptive import (
    CURRICULUM_LEVELS,
    SKILL_DEFINITIONS,
    AdaptiveEngine,
    generate_adaptive_exercise,
    generate_curriculum_exercise,
)
from blindchess.analysis import analyse_position
from blindchess.blindfold import (
    STAGE_METADATA,
    get_blindfold_exercise_by_category,
    get_blindfold_exercise_by_level,
    get_blindfold_exercise_by_stage,
    get_stage_info,
    normalize_square_list_input,
)
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
    """Run progressive blindfold chess training system with adaptive engine."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette
    engine = AdaptiveEngine(db_mgr)

    while True:
        ui.print_divider("Spatial Memory & Adaptive Progression System")
        print(f"  {c.muted('Develop flawless internal board representation with an intelligent, self-calibrating engine.')}\n")

        rows = []
        for lvl in range(1, 11):
            curr_info = CURRICULUM_LEVELS[lvl]
            skill_id = curr_info["primary_skill"]
            prof = engine.get_profile(skill_id)
            diff_label = f"Diff {prof.current_difficulty}/10"

            if prof.total_attempts > 0:
                acc_label = f"{prof.recent_accuracy:.0f}% acc"
                status_str = c.accent_bold(f"{diff_label} • {acc_label}")
            else:
                status_str = c.muted(f"{diff_label} • Untrained")

            title_clean = curr_info["title"].split("— ")[1] if "— " in curr_info["title"] else curr_info["title"]
            rows.append([f"[{lvl}]", title_clean, curr_info["subtitle"], status_str])

        ui.print_table(["Level", "Curriculum Focus", "Description", "Adaptive Status"], rows)

        ui.print_shortcut_bar([
            ("a", "Adaptive Training (Auto)"),
            ("1-10", "Train Curriculum Level"),
            ("p", "Skill Ratings (All 9)"),
            ("r", "Mistakes Practice"),
            ("x", "Reset Progress"),
            ("q", "Main Menu"),
        ])
        print()

        choice = ui.prompt("Select option: ").lower().strip()

        if choice in ("q", "quit", "exit"):
            break
        elif choice == "a":
            _run_adaptive_exercise_session(config, ui, db_mgr, engine=engine)
        elif choice == "p":
            _display_skill_ratings(ui, engine)
            ui.prompt("Press Enter to return...")
        elif choice == "r":
            _run_smart_mistakes_practice(config, ui, db_mgr)
        elif choice == "x":
            _handle_reset_adaptive_progress(ui, engine)
        elif choice.isdigit() and 1 <= int(choice) <= 10:
            lvl_num = int(choice)
            _run_adaptive_exercise_session(config, ui, db_mgr, engine=engine, curriculum_level=lvl_num)
        else:
            ui.print_warning("Enter 'a' for adaptive training, 1-10 for curriculum level, 'p' for skill ratings, or 'q' to exit.")


def _display_skill_ratings(ui: TerminalUI, engine: AdaptiveEngine) -> None:
    """Display comprehensive ratings and proficiency breakdown for all 9 independent skills."""
    c = ui.palette
    ui.print_divider("Independent Skill Ratings & Proficiency")

    rows = []
    for skill_id, info in SKILL_DEFINITIONS.items():
        p = engine.get_profile(skill_id)
        solved_str = f"{p.total_solved} / {p.total_attempts}"
        acc_str = f"{p.first_attempt_accuracy:.0f}%" if p.total_attempts > 0 else "N/A"
        speed_str = f"{p.avg_response_time}s" if p.total_attempts > 0 else "N/A"
        diff_str = f"{p.current_difficulty}/10"

        if p.current_difficulty >= 8:
            status_str = c.success_bold("Master")
        elif p.current_difficulty >= 5:
            status_str = c.accent_bold("Advanced")
        elif p.total_attempts > 0:
            status_str = c.highlight("Practicing")
        else:
            status_str = c.muted("Calibrating")

        rows.append([
            p.name,
            diff_str,
            f"{p.proficiency:.1f}%",
            solved_str,
            acc_str,
            speed_str,
            status_str,
        ])

    ui.print_table(
        ["Skill Area", "Difficulty", "Proficiency", "Solved / Att", "First-Att %", "Avg Speed", "Rating Tier"],
        rows,
    )


def _handle_reset_adaptive_progress(ui: TerminalUI, engine: AdaptiveEngine) -> None:
    """Handle explicit, non-automatic reset of adaptive progress."""
    ui.print_warning("Resetting will revert all 9 skills back to Level 1 and wipe adaptation history.")
    ans = ui.prompt("Type 'CONFIRM' to proceed with reset: ").strip()
    if ans == "CONFIRM":
        engine.reset_all_progress()
        ui.print_success("Adaptive progress has been reset to Level 1 across all skills.")
    else:
        ui.print_message("Reset cancelled.")
    ui.prompt("Press Enter to continue...")


def _run_adaptive_exercise_session(
    config: AppConfig,
    ui: TerminalUI,
    db_mgr: Optional[DatabaseManager],
    engine: AdaptiveEngine,
    skill_id: Optional[str] = None,
    curriculum_level: Optional[int] = None,
    target_count: int = 5,
) -> None:
    """Execute an adaptive practice round that automatically calibrates difficulty."""
    c = ui.palette

    # Determine skill to train
    if curriculum_level:
        curr_info = CURRICULUM_LEVELS.get(curriculum_level, CURRICULUM_LEVELS[1])
        target_skill = curr_info["primary_skill"]
        round_title = curr_info["title"]
    elif skill_id:
        target_skill = skill_id
        info = SKILL_DEFINITIONS.get(target_skill, {"name": target_skill})
        round_title = f"Adaptive Drill: {info['name']}"
    else:
        # Auto-pick skill needing practice (lowest proficiency or least attempts)
        sorted_skills = sorted(engine.profiles.values(), key=lambda p: (p.proficiency, p.total_attempts))
        target_skill = sorted_skills[0].skill_id if sorted_skills else "knight_routes"
        info = SKILL_DEFINITIONS.get(target_skill, {"name": target_skill})
        round_title = f"Adaptive Training: {info['name']}"

    profile = engine.get_profile(target_skill)
    session = ActiveSession(mode="spatial", level=profile.current_difficulty, db_mgr=db_mgr)

    ui.print_divider(round_title)

    # Render compact status card requested in Requirement 9
    recent_corr = sum(1 for x in profile.recent_first_attempts[-10:] if x)
    recent_total = len(profile.recent_first_attempts[-10:])
    recent_acc_str = f"{recent_corr}/{recent_total}" if recent_total > 0 else "0/0"
    hints_in_recent = sum(profile.recent_hints[-10:]) if profile.recent_hints else 0

    status_card_lines = [
        f"Skill: {c.accent_bold(profile.name)}",
        f"Difficulty: {c.highlight(f'{profile.current_difficulty}/10')}",
        f"Recent accuracy: {c.highlight(recent_acc_str)}",
        f"First-attempt accuracy: {c.highlight(f'{profile.first_attempt_accuracy:.0f}%')}",
        f"Hints used (recent): {hints_in_recent}",
        f"Next objective: {c.muted(profile.get_next_objective())}",
    ]
    print("\n" + ui.render_panel("Spatial Memory Drills — Status", status_card_lines, width=64, border_style="accent") + "\n")

    recent_seen_ids: Set[str] = set(profile.recent_exercise_ids[-10:])
    solved_in_round = 0
    total_time_round = 0.0

    for idx in range(1, target_count + 1):
        if curriculum_level:
            drill = generate_curriculum_exercise(curriculum_level, exclude_ids=recent_seen_ids)
        else:
            drill = generate_adaptive_exercise(target_skill, difficulty=profile.current_difficulty, exclude_ids=recent_seen_ids)

        recent_seen_ids.add(drill.id)

        print(f" {c.accent_bold(f'--- Exercise {idx}/{target_count} [Difficulty {profile.current_difficulty}/10] ---')}")

        if drill.initial_board_description:
            mem_lines = [
                c.highlight("Mentally commit this position to memory (DO NOT write it down):"),
                "",
                drill.initial_board_description,
            ]
            print(ui.render_panel("Mental Position Memorization", mem_lines, width=74, border_style="accent"))
            ui.prompt("Press Enter once you have visualized and memorized the layout...")
            print("\n" * 3)

        drill_card_lines = [
            f"Skill:    {c.highlight(profile.name)}   [Tier: {profile.current_difficulty}/10]",
            f"Concept:  {c.muted(drill.category.replace('_', ' ').title())}",
            "",
            drill.prompt,
        ]
        card = ui.render_panel(drill.title, drill_card_lines, width=74, border_style="muted")
        print(card + "\n")
        ui.print_shortcut_bar([("hint", "Hint"), ("skip", "Skip/Reveal"), ("quit", "Exit Round")])
        print()

        start_time = time.time()
        hints_used = 0
        attempts = 0
        was_revealed = False

        while True:
            ans = ui.prompt(f"[{c.accent(profile.name)} (L{profile.current_difficulty})] ❯ ").strip().lower()

            if ans in ("q", "quit"):
                session.close(notes=f"Aborted round during exercise {idx}")
                ui.print_message("Round exited.")
                return

            if ans == "hint":
                hints_used += 1
                session.record_hint()
                ui.print_warning(f"Hint: {drill.hint}")
                continue

            resp_time = round(time.time() - start_time, 1)

            if ans in ("skip", "reveal"):
                was_revealed = True
                total_time_round += resp_time
                ui.print_message(f"Solution: {drill.explanation}\n", prefix="Revealed")

                promo_res = engine.record_attempt(
                    skill_id=target_skill,
                    exercise_id=drill.id,
                    is_first_attempt=(attempts == 0),
                    is_correct=False,
                    hints_used=hints_used,
                    response_time=resp_time,
                    was_revealed=True,
                    concept_key=drill.category,
                    session_id=session.session_id,
                )
                if promo_res.action == "demoted":
                    ui.print_warning(f"\n▼ {promo_res.message}\n")
                break

            attempts += 1
            is_first = (attempts == 1)

            # Evaluate answer
            matches = False
            if ans in [corr.lower() for corr in drill.correct_answers]:
                matches = True
            elif drill.expected_square_set:
                user_squares = normalize_square_list_input(ans)
                if user_squares and user_squares == drill.expected_square_set:
                    matches = True

            if matches:
                solved_in_round += 1
                total_time_round += resp_time
                if is_first and hints_used == 0:
                    ui.print_success(f"✓ Correct on first attempt! ({resp_time}s) {drill.explanation}\n")
                elif hints_used > 0:
                    ui.print_success(f"✓ Correct with {hints_used} hint(s)! ({resp_time}s) {drill.explanation}\n")
                else:
                    ui.print_success(f"✓ Correct on retry {attempts}! ({resp_time}s) {drill.explanation}\n")

                promo_res = engine.record_attempt(
                    skill_id=target_skill,
                    exercise_id=drill.id,
                    is_first_attempt=is_first,
                    is_correct=True,
                    hints_used=hints_used,
                    response_time=resp_time,
                    was_revealed=False,
                    concept_key=drill.category,
                    session_id=session.session_id,
                )
                if promo_res.action == "promoted":
                    ui.print_success(f"\n★ {promo_res.message}\n")
                elif promo_res.action == "demoted":
                    ui.print_warning(f"\n▼ {promo_res.message}\n")

                if db_mgr:
                    db_mgr.record_spatial_drill(
                        session_id=session.session_id,
                        stage=curriculum_level or profile.current_difficulty,
                        stage_name=profile.name,
                        category=drill.category,
                        exercise_id=drill.id,
                        solved=True,
                        attempts=attempts,
                        hints_used=hints_used,
                        response_time_seconds=resp_time,
                        user_answer=ans,
                    )
                break
            else:
                if is_first:
                    # Record first-attempt failure into adaptive engine immediately
                    promo_res = engine.record_attempt(
                        skill_id=target_skill,
                        exercise_id=drill.id,
                        is_first_attempt=True,
                        is_correct=False,
                        hints_used=hints_used,
                        response_time=resp_time,
                        was_revealed=False,
                        concept_key=drill.category,
                        session_id=session.session_id,
                    )
                    if promo_res.action == "demoted":
                        ui.print_warning(f"\n▼ {promo_res.message}\n")
                ui.print_warning("Incorrect answer. Re-visualize the geometry and retry, or type 'hint' / 'skip'.")

    # Round Summary
    acc = round((solved_in_round / target_count) * 100.0, 1) if target_count > 0 else 0.0
    avg_t = round(total_time_round / target_count, 1) if target_count > 0 else 0.0

    summary_lines = [
        f"Skill Trained:      {profile.name}",
        f"Round Score:        {solved_in_round} / {target_count} ({acc}%)",
        f"Current Difficulty: Level {profile.current_difficulty}/10",
        f"First-Attempt Acc:  {profile.first_attempt_accuracy:.0f}%",
        f"Avg Response Speed: {avg_t}s",
    ]
    print(ui.render_panel("Adaptive Round Summary", summary_lines, width=64, border_style="accent") + "\n")
    session.close(notes=f"Adaptive round for {target_skill}: {solved_in_round}/{target_count} ({acc}%)")
    ui.prompt("Press Enter to continue...")


def _run_stage_session(
    config: AppConfig,
    ui: TerminalUI,
    db_mgr: Optional[DatabaseManager],
    stage_num: int,
    target_count: int = 5,
) -> None:
    """Execute a focused practice round for a specific stage."""
    c = ui.palette
    info = get_stage_info(stage_num)
    session = ActiveSession(mode="spatial", level=stage_num, db_mgr=db_mgr)

    ui.print_divider(f"Stage {stage_num}: {info['title']}")
    print(f"  {c.muted(info['description'])}\n")
    print(f"  {c.muted('Round target: ')}{c.highlight(str(target_count))}{c.muted(' exercises. Board remains strictly hidden.')}\n")

    solved_count = 0
    total_time = 0.0

    for idx in range(1, target_count + 1):
        drill = get_blindfold_exercise_by_stage(stage_num)
        print(f" {c.accent_bold(f'--- Exercise {idx}/{target_count} ---')}")

        # If Stage 5 (position memory), show memorization step first
        if drill.initial_board_description:
            mem_lines = [
                c.highlight("Mentally commit this position to memory (DO NOT write it down):"),
                "",
                drill.initial_board_description,
            ]
            print(ui.render_panel("Mental Position Memorization", mem_lines, width=74, border_style="accent"))
            ui.prompt("Press Enter once you have visualized and memorized the layout...")
            print("\n" * 3)  # Push memorization card off immediate view

        drill_card_lines = [
            f"Category: {c.highlight(drill.category.replace('_', ' ').title())}",
            "",
            drill.prompt,
        ]
        card = ui.render_panel(drill.title, drill_card_lines, width=74, border_style="muted")
        print(card + "\n")
        ui.print_shortcut_bar([("hint", "Hint"), ("skip", "Skip"), ("quit", "Abort Round")])
        print()

        start_time = time.time()
        hints_used = 0
        attempts = 0
        is_solved = False

        while True:
            attempts += 1
            ans = ui.prompt(f"[{c.accent(f'Stage {stage_num}')}] ❯ ").strip().lower()

            if ans in ("q", "quit"):
                session.close(notes=f"Aborted during exercise {idx}")
                ui.print_message("Round aborted by user.")
                return

            if ans == "hint":
                hints_used += 1
                session.record_hint()
                ui.print_warning(drill.hint)
                continue

            resp_time = round(time.time() - start_time, 1)

            # Evaluate answer
            matches = False
            if ans in [corr.lower() for corr in drill.correct_answers]:
                matches = True
            elif drill.expected_square_set:
                user_squares = normalize_square_list_input(ans)
                if user_squares and user_squares == drill.expected_square_set:
                    matches = True

            if matches:
                is_solved = True
                solved_count += 1
                total_time += resp_time
                ui.print_success(f"Correct! ({resp_time}s) {drill.explanation}\n")
                if db_mgr:
                    db_mgr.record_spatial_drill(
                        session_id=session.session_id,
                        stage=stage_num,
                        stage_name=info["title"],
                        category=drill.category,
                        exercise_id=drill.id,
                        solved=True,
                        attempts=attempts,
                        hints_used=hints_used,
                        response_time_seconds=resp_time,
                        user_answer=ans,
                    )
                break
            else:
                if ans == "skip":
                    total_time += resp_time
                    ui.print_message(f"Solution: {drill.explanation}\n", prefix="Revealed")
                    if db_mgr:
                        db_mgr.record_spatial_drill(
                            session_id=session.session_id,
                            stage=stage_num,
                            stage_name=info["title"],
                            category=drill.category,
                            exercise_id=drill.id,
                            solved=False,
                            attempts=attempts,
                            hints_used=hints_used,
                            response_time_seconds=resp_time,
                            user_answer=ans,
                            error_reason=f"Skipped after incorrect: {ans}",
                        )
                    break
                ui.print_warning("Incorrect answer. Re-visualize the geometry and retry, or type 'hint' / 'skip'.")

    # Round Summary Scorecard
    acc = round((solved_count / target_count) * 100.0, 1) if target_count > 0 else 0.0
    avg_t = round(total_time / target_count, 1) if target_count > 0 else 0.0

    if db_mgr:
        db_mgr.update_spatial_stage_mastery(stage_num, info["title"], solved_count, target_count, acc)

    scorecard_lines = [
        f"Score:         {c.highlight(f'{solved_count} / {target_count}')} ({acc}%)",
        f"Avg Speed:     {avg_t} seconds per exercise",
    ]

    if acc >= 80.0:
        scorecard_lines.append(c.success_bold("★ STAGE MASTERY ACHIEVED! Next stage unlocked."))
    else:
        scorecard_lines.append(c.warning(f"Mastery requires >= 80% accuracy. Continue practicing Stage {stage_num}."))

    print(ui.render_panel(f"Stage {stage_num} Round Scorecard", scorecard_lines, width=64, border_style="success" if acc >= 80 else "accent") + "\n")
    session.close(notes=f"Completed stage {stage_num}: {solved_count}/{target_count} ({acc}%)")
    ui.prompt("Press Enter to continue...")


def _run_smart_mistakes_practice(config: AppConfig, ui: TerminalUI, db_mgr: Optional[DatabaseManager]) -> None:
    """Serve targeted exercises for categories where user has previously erred."""
    c = ui.palette
    if not db_mgr:
        ui.print_warning("Database not available for mistake analysis.")
        return

    errors = db_mgr.get_recurring_spatial_errors(limit=5)
    if not errors:
        ui.print_success("No recurring mistake patterns found in database! Choose any stage to train.")
        ui.prompt("Press Enter to continue...")
        return

    ui.print_divider("Smart Practice: Recurring Mistakes Focus")
    print(f"  {c.muted('Serving targeted exercises based on your recorded error history:')}\n")

    error_cats = [e["category"] for e in errors]
    solved = 0
    total = len(error_cats)

    for idx, cat in enumerate(error_cats, start=1):
        drill = get_blindfold_exercise_by_category(cat)
        if not drill:
            continue

        print(f" {c.accent_bold(f'--- Practice Drill {idx}/{total} [{drill.category}] ---')}")
        card_lines = [
            f"Focus Stage: {c.highlight(f'Stage {drill.stage}')}",
            f"Category:    {c.warning_bold(drill.category.replace('_', ' ').title())}",
            "",
            drill.prompt,
        ]
        print(ui.render_panel("Targeted Error Drill", card_lines, width=74, border_style="warning") + "\n")
        ui.print_shortcut_bar([("hint", "Hint"), ("skip", "Skip"), ("quit", "Exit")])
        print()

        start_time = time.time()
        while True:
            ans = ui.prompt("Your answer: ").strip().lower()
            if ans in ("q", "quit"):
                return
            if ans == "hint":
                ui.print_warning(drill.hint)
                continue
            if ans in [corr.lower() for corr in drill.correct_answers]:
                ui.print_success(f"Excellent! You conquered this motif. {drill.explanation}\n")
                solved += 1
                break
            else:
                if ans == "skip":
                    ui.print_message(f"Solution: {drill.explanation}\n", prefix="Revealed")
                    break
                ui.print_warning("Not quite. Re-visualize carefully, or type 'hint' / 'skip'.")

    ui.print_message(f"Targeted review complete: {solved}/{total} solved.", prefix="Smart Practice")
    ui.prompt("Press Enter to continue...")


def _display_spatial_statistics(ui: TerminalUI, db_mgr: Optional[DatabaseManager]) -> None:
    """Display detailed stage progress, completion metrics, and recurring error categories."""
    c = ui.palette
    if not db_mgr:
        ui.print_warning("Database not available.")
        return

    stages = db_mgr.get_all_spatial_stage_mastery()
    errors = db_mgr.get_recurring_spatial_errors(limit=5)

    ui.print_divider("Blindfold Stage Mastery & Error Analysis")

    rows = []
    for s in stages:
        acc = f"{s['best_accuracy']:.1f}%" if s["total_attempted"] > 0 else "N/A"
        status = c.success_bold("Mastered") if s["completed"] else (c.accent("Unlocked") if s["unlocked"] else c.muted("Locked"))
        rows.append([
            f"Stage {s['stage']}",
            s["stage_name"],
            str(s["total_solved"]),
            str(s["total_attempted"]),
            acc,
            status,
        ])
    ui.print_table(["Stage", "Focus Area", "Solved", "Attempted", "Best Accuracy", "Status"], rows)

    if errors:
        ui.print_divider("Recurring Mistake Categories (Targeted Review Areas)")
        err_rows = []
        for e in errors:
            err_rows.append([
                f"Stage {e['stage']}",
                e["category"].replace("_", " ").title(),
                str(e["failed_attempts"]),
                str(e["total_attempts"]),
                f"{e['avg_time']}s",
            ])
        ui.print_table(["Stage", "Error Category", "Mistakes", "Total Attempts", "Avg Response Time"], err_rows)
    else:
        ui.print_success("No recurring error categories recorded yet.")


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
        print(f" {c.muted('Turn:')} {c.accent_bold(turn_str)} (Move {cur_board.fullmove_number}.)")

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
