"""Contextual command parser and handlers for BlindChess."""

from typing import List, Optional, Tuple

COMMAND_DESCRIPTIONS = {
    "help": "Display this help menu.",
    "board": "Reveal current board position (records a reveal in blindfold mode).",
    "moves": "Show move history for the current game.",
    "fen": "Display the current FEN string.",
    "status": "Check current game status, whose turn it is, and check/checkmate.",
    "undo": "Take back the last move (or full turn in game mode).",
    "redo": "Replay an undone move.",
    "hint": "Request a contextual hint.",
    "analyze": "Request engine analysis for the current position.",
    "variations": "Open the variation explorer from the current position.",
    "save": "Save the current game / training session to PGN or database.",
    "load": "Load a game or position from PGN / FEN.",
    "review": "Review the game and highlight inaccuracies and mistakes.",
    "settings": "Display current configuration settings.",
    "quit": "Exit current mode or application.",
}


def is_command(text: str) -> bool:
    """Return True if text begins with a recognized command keyword."""
    first_word = text.strip().split()[0].lower() if text.strip() else ""
    return first_word in COMMAND_DESCRIPTIONS


def parse_command(text: str) -> Tuple[str, List[str]]:
    """Parse text into (command_name, args_list)."""
    parts = text.strip().split()
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def get_help_text(context: str = "game") -> str:
    """Return contextual help instructions."""
    lines = [
        "Available Commands:",
        "-" * 45,
    ]
    for cmd, desc in sorted(COMMAND_DESCRIPTIONS.items()):
        lines.append(f"  {cmd:<12} : {desc}")

    lines.extend([
        "-" * 45,
        "Move Entry:",
        "  • Enter standard algebraic notation: e4, Nf3, Bxc6+, O-O, e8=Q",
        "  • Or coordinate notation: e2e4, g1f3, e7e8q",
        "  • Board is hidden by default. Use 'board' to request a peek.",
    ])
    return "\n".join(lines)
