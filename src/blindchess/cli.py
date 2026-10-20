"""Command-line interface entry point for BlindChess."""

import argparse
import logging
from pathlib import Path
import shutil
import signal
import sys
from typing import Optional

from blindchess.config import AppConfig, load_config, save_config
from blindchess.engine_manager import EngineManager
from blindchess.errors import BlindChessError
from blindchess.persistence import DatabaseManager
from blindchess.terminal_ui import TerminalUI, visible_len
from blindchess.training import (
    display_statistics,
    run_blindfold_drills,
    run_calculation_trainer,
    run_endgame_practice,
    run_game_loop,
    run_opening_practice,
    run_review_mode,
    run_strategy_coach,
    run_tactics_trainer,
    run_variation_explorer,
)

logger = logging.getLogger("blindchess")


def _run_settings(config: AppConfig) -> None:
    """Interactive settings editor with categorized, human-readable display."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette
    display = ui.palette.highlight
    dim = ui.palette.muted
    dim_bold = ui.palette.bold
    warn = ui.palette.warning_bold
    succ = ui.palette.success_bold

    # Settings are grouped into logical categories.
    CATEGORIES = [
        ("Engines & Board", [
            ("engine_path", "Stockfish executable (path)", "path"),
            ("default_opponent_level", "Default opponent level", "level"),
            ("board_visibility", "Board visibility", "visibility"),
            ("strict_blindfold", "Strict blindfold mode", "bool"),
            ("ascii_only", "ASCII-only rendering", "bool"),
        ]),
        ("Engine & Analysis", [
            ("engine_threads", "Engine threads", "int"),
            ("engine_hash_mb", "Engine hash memory (MB)", "int"),
            ("analysis_depth", "Analysis depth", "int"),
            ("analysis_time_limit", "Analysis time limit (s)", "float"),
            ("multipv", "MultiPV", "int"),
            ("tablebase_path", "Tablebase path", "path"),
        ]),
        ("Training & Behaviour", [
            ("adaptive_difficulty", "Adaptive difficulty", "bool"),
            ("training_level", "Training level", "int"),
            ("user_side", "User side to play", "side"),
        ]),
    ]

    def fmt_bool(v: bool) -> str:
        return succ("ON") if v else dim("OFF")

    def fmt_visibility(v: str) -> str:
        mapping = {
            "hidden": dim("Hidden"),
            "manual_reveal": warn("Manual Reveal"),
            "after_move": succ("Reveal after move"),
            "normal": succ_bold if False else dim("Normal"),
        }
        return mapping.get(v, v)

    def fmt_side(v: str) -> str:
        return succ_bold if False else dim(v.capitalize())

    def show_settings() -> None:
        ui.print_divider("Active Configuration")
        print()
        for category, fields in CATEGORIES:
            # Section header
            print(f"  {c.highlight(category)}")
            print(f"  {c.muted('─' * 40)}")
            print(f"  {c.muted('Key'):<30} {c.muted('Description'):<38} Current")
            print(f"  {c.muted('─' * 30)}  {c.muted('─' * 38)}  {'─' * 18}")
            for key, desc, kind in fields:
                value = getattr(config, key)
                if kind == "bool":
                    shown = fmt_bool(value)
                elif kind == "visibility":
                    shown = fmt_visibility(value)
                elif kind == "side":
                    shown = fmt_side(value)
                elif kind == "int":
                    shown = str(value)
                elif kind == "path":
                    shown = str(value) if value else dim("(auto)")
                else:
                    shown = str(value)
                print(f"  {c.accent_bold(key):<30} {c.muted(desc):<38} {shown}")
            print()
        print(f"{c.muted('─' * 40)}")
        print(f"  {c.muted('•')} Values are saved to disk automatically (config file).")
        print(f"  {c.muted('•')} Run '12' again, or use '--config <file>' to load a different file.")
        print()

    def edit_settings() -> None:
        """Edit a single setting, then persist back to disk."""
        # Show current settings for context
        show_settings()
        choice = ui.prompt("Choose a setting to edit (or 'back'): ").strip().lower()
        if choice in ("back", "", "b"):
            return

        # Match the choice to a field
        target = None
        for cat_fields in CATEGORIES:
            for key, desc, kind in cat_fields:
                if key.lower() == choice.lower():
                    target = (key, desc, kind)
                    break
            if target:
                break

        if target is None:
            ui.print_warning(f"Unknown setting '{choice}'. Try again.")
            ui.prompt("Press Enter to continue...")
            return

        key, desc, kind = target
        current = getattr(config, key)

        # Build a prompt with the current value
        if kind == "bool":
            prompt = f"{c.accent_bold(key)} [{c.muted('ON')}] {c.muted('or')} [{c.muted('OFF')}] : "
            ans = ui.prompt(prompt).strip().lower()
            if ans.startswith("o"):
                new_val = ans.startswith("on")
            else:
                new_val = False
        elif kind == "visibility":
            opts = [("hidden", dim("Hidden")), ("manual_reveal", warn("Manual Reveal")),
                    ("after_move", succ("Reveal after move")), ("normal", succ("Normal"))]
            print(f"{c.highlight('Board visibility options:')}")
            for opt, label in opts:
                print(f"  {c.muted('-')} {c.accent_bold(opt)}  {label}")
            ans = ui.prompt(f"{c.accent_bold(key)} select (hidden/manual_reveal/after_move/normal): ").strip().lower()
            new_val = next((v for v, _ in opts if v == ans), None)
            if new_val is None:
                ui.print_warning(f"Invalid option '{ans}'. No change made.")
                ui.prompt("Press Enter to continue...")
                return
        elif kind == "side":
            opts = [("white", dim("White")), ("black", dim("Black")), ("random", warn("Random"))]
            print(f"{c.highlight('Player side options:')}")
            for opt, label in opts:
                print(f"  {c.muted('-')} {c.accent_bold(opt)}  {label}")
            ans = ui.prompt(f"{c.accent_bold(key)} select (white/black/random): ").strip().lower()
            new_val = next((v for v, _ in opts if v == ans), None)
            if new_val is None:
                ui.print_warning(f"Invalid option '{ans}'. No change made.")
                ui.prompt("Press Enter to continue...")
                return
        else:
            prompt = f"{c.accent_bold(key)} [{dim(str(current))}]: "
            raw = ui.prompt(prompt).strip()
            if raw == "":
                new_val = current
            else:
                try:
                    if kind == "int":
                        new_val = int(raw)
                    elif kind == "float":
                        new_val = float(raw)
                    else:
                        new_val = raw
                except ValueError:
                    ui.print_warning(f"Invalid value '{raw}'. No change made.")
                    ui.prompt("Press Enter to continue...")
                    return

        # Apply and persist
        setattr(config, key, new_val)
        try:
            save_config(config)
            ui.print_success(f"{key} updated to {new_val}. Configuration saved.")
        except Exception as e:
            ui.print_error(f"Failed to save configuration: {e}")

        ui.prompt("Press Enter to continue...")

    show_settings()
    edit_settings()


def parse_arguments(argv: Optional[list] = None) -> argparse.Namespace:
    """Configure and parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="blindchess",
        description="BlindChess: Local-First Linux Blindfold Chess, Strategic Thinking, and Variation Trainer",
    )

    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version="blindchess 1.0.0",
        help="Show program's version number and exit",
    )

    parser.add_argument(
        "--mode",
        choices=[
            "menu",
            "blindfold",
            "play",
            "spatial",
            "calculate",
            "variations",
            "strategy",
            "tactics",
            "openings",
            "endgames",
            "review",
            "stats",
        ],
        default="menu",
        help="Directly launch a specific training mode (default: menu)",
    )

    parser.add_argument(
        "--level",
        choices=["beginner", "casual", "intermediate", "advanced", "expert", "full_strength"],
        help="Opponent difficulty setting for game play",
    )

    parser.add_argument(
        "--side",
        choices=["white", "black", "random"],
        default="white",
        help="Player side (default: white)",
    )

    parser.add_argument(
        "--engine",
        type=str,
        help="Path to Stockfish executable (overrides discovery)",
    )

    parser.add_argument(
        "--depth",
        type=int,
        help="Engine analysis depth limit",
    )

    parser.add_argument(
        "--time",
        type=float,
        help="Engine thinking time limit per move (seconds)",
    )

    parser.add_argument(
        "--multipv",
        type=int,
        help="Number of principal variations to compute (MultiPV)",
    )

    parser.add_argument(
        "--threads",
        type=int,
        help="Number of engine threads (default: 1)",
    )

    parser.add_argument(
        "--hash",
        type=int,
        help="Engine hash memory size in MB (default: 64)",
    )

    parser.add_argument(
        "--show-board",
        action="store_true",
        help="Display the chessboard visually (disables blindfold hiding)",
    )

    parser.add_argument(
        "--strict-blindfold",
        action="store_true",
        help="Enforce strict blindfold mode: prevent 'board' reveal commands",
    )

    parser.add_argument(
        "--ascii",
        action="store_true",
        help="Use ASCII piece symbols instead of Unicode characters",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to custom configuration JSON file",
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Path to custom persistent data directory",
    )

    parser.add_argument(
        "--pgn",
        type=str,
        help="Path to PGN file for review or loading",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose diagnostic logging",
    )

    return parser.parse_args(argv)


def interactive_main_menu(
    config: AppConfig, engine_mgr: Optional[EngineManager], db_mgr: Optional[DatabaseManager]
) -> None:
    """Display interactive main menu for BlindChess."""
    ui = TerminalUI(ascii_only=config.ascii_only)
    c = ui.palette

    while True:
        ui.print_banner()
        eng_name = engine_mgr.engine_name if (engine_mgr and engine_mgr.is_available) else "None"
        eng_ready = bool(engine_mgr and engine_mgr.is_available and engine_mgr.engine)
        ui.print_status_bar(
            engine_name=eng_name,
            engine_ready=eng_ready,
            opponent_level=config.default_opponent_level,
            visibility="normal" if config.board_visibility == "normal" else "hidden",
            training_level=config.training_level,
        )

        cols = shutil.get_terminal_size(fallback=(80, 24)).columns

        # 3 columns x 4 rows when terminal width >= 90; 2 columns x 6 rows for narrower terminals
        if cols >= 90:
            item_rows = [
                [(1, "Blindfold Game"), (2, "Play vs Stockfish"), (3, "Spatial Memory Drills")],
                [(4, "Candidate Calculation"), (5, "Variation Explorer"), (6, "Strategic Position Coach")],
                [(7, "Tactical Training (Puzzles)"), (8, "Opening Repertoires"), (9, "Endgame Fundamentals")],
                [(10, "Game Diagnostic Review"), (11, "Training Statistics"), (12, "System Configuration")],
            ]
        else:
            item_rows = [
                [(1, "Blindfold Game"), (2, "Play vs Stockfish")],
                [(3, "Spatial Memory Drills"), (4, "Candidate Calculation")],
                [(5, "Variation Explorer"), (6, "Strategic Position Coach")],
                [(7, "Tactical Training (Puzzles)"), (8, "Opening Repertoires")],
                [(9, "Endgame Fundamentals"), (10, "Game Diagnostic Review")],
                [(11, "Training Statistics"), (12, "System Configuration")],
            ]

        # Calculate max visible width for each column to guarantee razor-sharp alignment
        num_cols = len(item_rows[0])
        col_widths = [0] * num_cols
        for row in item_rows:
            for col_idx, (num, label) in enumerate(row):
                vis = visible_len(f"[{num}] {label}")
                if vis > col_widths[col_idx]:
                    col_widths[col_idx] = vis

        row_strs = []
        for row in item_rows:
            cells = []
            for col_idx, (num, label) in enumerate(row):
                tag = f"{c.muted('[')}{c.accent_bold(str(num))}{c.muted(']')}"
                cell_text = f"{tag} {label}"
                vis = visible_len(cell_text)
                pad_len = col_widths[col_idx] - vis
                if col_idx < num_cols - 1:
                    cells.append(cell_text + (" " * pad_len))
                else:
                    cells.append(cell_text)
            row_strs.append("  " + "   ".join(cells))
        print("\n".join(row_strs) + "\n")
        ui.print_shortcut_bar([
            ("1-12", "Select Mode"),
            ("q", "Quit"),
        ])
        print()

        choice = ui.prompt("Select option: ").lower().strip()

        if choice in ("1", "blindfold"):
            run_game_loop(config, engine_mgr, db_mgr, user_side=config.user_side, show_board=False)
        elif choice in ("2", "play"):
            run_game_loop(
                config,
                engine_mgr,
                db_mgr,
                opponent_level=config.default_opponent_level,
                user_side=config.user_side,
                show_board=(config.board_visibility == "normal"),
            )
        elif choice in ("3", "spatial"):
            run_blindfold_drills(config, db_mgr, level=config.training_level)
        elif choice in ("4", "calculate"):
            run_calculation_trainer(config, engine_mgr, db_mgr)
        elif choice in ("5", "variations"):
            run_variation_explorer(config, engine_mgr)
        elif choice in ("6", "strategy"):
            run_strategy_coach(config, engine_mgr, db_mgr)
        elif choice in ("7", "tactics"):
            run_tactics_trainer(config, db_mgr)
        elif choice in ("8", "openings"):
            run_opening_practice(config, engine_mgr, db_mgr)
        elif choice in ("9", "endgames"):
            run_endgame_practice(config, engine_mgr, db_mgr)
        elif choice in ("10", "review"):
            run_review_mode(config, engine_mgr, db_mgr)
        elif choice in ("11", "stats"):
            display_statistics(db_mgr, config)
        elif choice in ("12", "settings"):
            _run_settings(config)
        elif choice in ("13", "quit", "exit", "q"):
            ui.print_success("Thank you for training with BlindChess.")
            break
        else:
            ui.print_warning("Invalid selection. Enter a number (1-12) or 'q' to quit.")


def main(argv: Optional[list] = None) -> int:
    """Application main CLI entry point."""
    args = parse_arguments(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config(args.config)

    # CLI flag overrides
    if args.level:
        config.default_opponent_level = args.level
    if args.depth:
        config.analysis_depth = args.depth
    if args.time:
        config.analysis_time_limit = args.time
    if args.multipv:
        config.multipv = args.multipv
    if args.threads:
        config.engine_threads = args.threads
    if args.hash:
        config.engine_hash_mb = args.hash
    if args.show_board:
        config.board_visibility = "normal"
    if args.strict_blindfold:
        config.strict_blindfold = True
    if args.ascii:
        config.ascii_only = True
    if args.side:
        config.user_side = args.side

    # Initialize persistence
    db_path = None
    if args.data_dir:
        db_path = Path(args.data_dir) / "blindchess.db"
    db_mgr = DatabaseManager(db_path)

    # Initialize Engine Manager
    engine_mgr = EngineManager(
        engine_path=args.engine or config.engine_path,
        config=config,
        threads=config.engine_threads,
        hash_mb=config.engine_hash_mb,
    )

    if engine_mgr.is_available:
        try:
            engine_mgr.start()
        except Exception as e:
            logger.warning(f"Could not initialize engine at startup: {e}. Running in engine-free mode.")

    # Graceful exit signal handler
    def handle_signal(sig, frame):
        print("\nInterrupt received. Shutting down cleanly...")
        if engine_mgr:
            engine_mgr.close()
        if db_mgr:
            db_mgr.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        if args.mode == "menu":
            interactive_main_menu(config, engine_mgr, db_mgr)
        elif args.mode == "blindfold":
            run_game_loop(config, engine_mgr, db_mgr, user_side=config.user_side, show_board=False, strict_blindfold=config.strict_blindfold)
        elif args.mode == "play":
            run_game_loop(
                config,
                engine_mgr,
                db_mgr,
                opponent_level=args.level or config.default_opponent_level,
                user_side=config.user_side,
                show_board=(config.board_visibility == "normal"),
                strict_blindfold=config.strict_blindfold,
            )
        elif args.mode == "spatial":
            run_blindfold_drills(config, db_mgr, level=config.training_level)
        elif args.mode == "calculate":
            run_calculation_trainer(config, engine_mgr, db_mgr)
        elif args.mode == "variations":
            run_variation_explorer(config, engine_mgr)
        elif args.mode == "strategy":
            run_strategy_coach(config, engine_mgr, db_mgr)
        elif args.mode == "tactics":
            run_tactics_trainer(config, db_mgr)
        elif args.mode == "openings":
            run_opening_practice(config, engine_mgr, db_mgr)
        elif args.mode == "endgames":
            run_endgame_practice(config, engine_mgr, db_mgr)
        elif args.mode == "review":
            run_review_mode(config, engine_mgr, db_mgr, pgn_path=args.pgn)
        elif args.mode == "stats":
            display_statistics(db_mgr, config)
        return 0
    except BlindChessError as e:
        print(f"\n[Error] {e}")
        return 1
    except Exception as e:
        logger.exception("Unexpected error occurred during execution.")
        print(f"\nUnexpected error: {e}")
        return 1
    finally:
        if engine_mgr:
            engine_mgr.close()
        if db_mgr:
            db_mgr.close()


if __name__ == "__main__":
    sys.exit(main())
