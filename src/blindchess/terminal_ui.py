"""Lightweight, resilient terminal user interface without bloated dependencies."""

import os
import sys
from typing import List, Optional

from blindchess.board_state import BoardState


class TerminalUI:
    """Manages terminal formatting, board display, and interactive prompts."""

    def __init__(self, ascii_only: bool = False):
        self.ascii_only = ascii_only or not self._supports_unicode()

    @staticmethod
    def _supports_unicode() -> bool:
        """Check if stdout encoding supports UTF-8."""
        encoding = getattr(sys.stdout, "encoding", "") or ""
        return "utf" in encoding.lower()

    def print_banner(self) -> None:
        """Print application header banner."""
        banner = """
============================================================
                        BLINDCHESS
       Local-First Blindfold & Strategic Chess Trainer
============================================================
"""
        print(banner.strip())

    def print_status_bar(
        self,
        engine_name: str,
        engine_ready: bool,
        opponent_level: str,
        visibility: str,
        training_level: int,
    ) -> None:
        """Print high-level status bar."""
        eng_status = "Ready" if engine_ready else "Unavailable (Running in Engine-Free Mode)"
        vis_text = "Hidden (Blindfold)" if visibility == "hidden" else visibility.capitalize()
        lines = [
            f"Engine:          {engine_name}",
            f"Engine Status:   {eng_status}",
            f"Opponent Level:  {opponent_level.capitalize()}",
            f"Board View:      {vis_text}",
            f"Training Level:  Level {training_level} / 6",
            "-" * 60,
        ]
        print("\n".join(lines))

    def print_board(self, board_state: BoardState, perspective_white: bool = True) -> None:
        """Render board to terminal."""
        rendered = board_state.render_board(
            unicode_pieces=not self.ascii_only,
            perspective=chess_color_from_bool(perspective_white),
        )
        print("\n" + rendered + "\n")

    def print_message(self, message: str, prefix: str = "") -> None:
        """Print an informational message."""
        if prefix:
            print(f"[{prefix}] {message}")
        else:
            print(message)

    def print_error(self, message: str, hint: Optional[str] = None) -> None:
        """Print an error message with optional guidance hint."""
        print(f"\nERROR: {message}")
        if hint:
            print(f"HINT:  {hint}\n")

    def prompt(self, prompt_text: str = "blindchess> ") -> str:
        """Prompt user for input, cleanly handling EOF / Ctrl+C."""
        try:
            return input(prompt_text).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            return "quit"


def chess_color_from_bool(is_white: bool):
    import chess
    return chess.WHITE if is_white else chess.BLACK
