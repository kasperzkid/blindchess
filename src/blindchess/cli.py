"""Command-line interface entry point for BlindChess."""

import argparse
import logging
from pathlib import Path
import signal
import sys
from typing import Optional

from blindchess.config import AppConfig, load_config, save_config
from blindchess.engine_manager import EngineManager
from blindchess.errors import BlindChessError
from blindchess.persistence import DatabaseManager
from blindchess.terminal_ui import TerminalUI
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

        # Structured, numeric-ordered menu list
        items = [
            ("1", "Blindfold Game"),
            ("2", "Play vs Stockfish"),
            ("3", "Spatial Memory Drills"),
            ("4", "Candidate Calculation"),
            ("5", "Variation Explorer"),
            ("6", "Strategic Position Coach"),
            ("7", "Tactical Training (Puzzles)"),
            ("8", "Opening Repertoires"),
            ("9", "Endgame Fundamentals"),
            ("10", "Game Diagnostic Review"),
            ("11", "Training Statistics"),
            ("12", "System Configuration"),
        ]

        lines = []
        for num, label in items:
            lines.append(f"  {c.muted('[')}{c.accent_bold(num)}{c.muted(']')} {label}")
        print("\n".join(lines) + "\n")
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
            ui.print_divider("Active Configuration")
            rows = []
            for k, v in sorted(config.to_dict().items()):
                rows.append([k, str(v) if v is not None else "(auto)"])
            ui.print_table(["Setting Key", "Current Value"], rows)
            ui.prompt("Press Enter to return...")
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
