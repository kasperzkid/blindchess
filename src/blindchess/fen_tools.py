"""FEN parsing, validation, and position utility functions."""

from typing import Dict, Optional
import chess

from blindchess.errors import PositionError


STARTING_FEN = chess.STARTING_FEN


def validate_fen(fen: str) -> bool:
    """Check whether a FEN string represents a valid, legal chess position."""
    try:
        board = chess.Board(fen.strip())
        return board.is_valid()
    except Exception:
        return False


def parse_fen(fen: str) -> chess.Board:
    """Parse and validate FEN string into a chess.Board instance."""
    cleaned = fen.strip()
    try:
        board = chess.Board(cleaned)
        if not board.is_valid():
            status = board.status()
            raise PositionError(
                f"Position is invalid according to chess rules (status={status})."
            )
        return board
    except ValueError as e:
        raise PositionError(f"Malformed FEN syntax: {e}") from e


def export_fen(board: chess.Board) -> str:
    """Export the current board position as standard FEN."""
    return board.fen()


def summarize_fen(fen: str) -> Dict[str, str]:
    """Provide a structured summary of turn, castling, and en passant from FEN."""
    board = parse_fen(fen)
    turn = "White" if board.turn == chess.WHITE else "Black"
    castling = board.castling_xfen()
    ep = chess.square_name(board.ep_square) if board.ep_square is not None else "None"
    return {
        "turn": turn,
        "castling": castling if castling else "None",
        "en_passant": ep,
        "halfmove_clock": str(board.halfmove_clock),
        "fullmove_number": str(board.fullmove_number),
        "check": "Yes" if board.is_check() else "No",
    }
