"""Chess notation parser, validator, and formatter."""

import re
from typing import Optional, Tuple
import chess

from blindchess.errors import AmbiguousMoveError, InvalidMoveError


def normalize_notation_input(text: str) -> str:
    """Normalize user notation input: trim, normalize castling and punctuation."""
    cleaned = text.strip()
    # Normalize 0-0 or o-o to O-O
    if re.fullmatch(r"0-0|o-o", cleaned, re.IGNORECASE):
        return "O-O"
    if re.fullmatch(r"0-0-0|o-o-o", cleaned, re.IGNORECASE):
        return "O-O-O"
    # Normalize O-O+ or O-O#
    if re.fullmatch(r"(?:0-0|o-o)\+", cleaned, re.IGNORECASE):
        return "O-O+"
    if re.fullmatch(r"(?:0-0|o-o)#", cleaned, re.IGNORECASE):
        return "O-O#"
    if re.fullmatch(r"(?:0-0-0|o-o-o)\+", cleaned, re.IGNORECASE):
        return "O-O-O+"
    if re.fullmatch(r"(?:0-0-0|o-o-o)#", cleaned, re.IGNORECASE):
        return "O-O-O#"
    return cleaned


def parse_move_on_board(board: chess.Board, move_str: str) -> chess.Move:
    """Parse user move string (SAN or coordinate UCI) without mutating the board.

    Raises:
        InvalidMoveError if the move is syntactically invalid or illegal.
        AmbiguousMoveError if the move is ambiguous.
    """
    cleaned = normalize_notation_input(move_str)
    if not cleaned:
        raise InvalidMoveError("Empty move string provided.", "Enter a move like 'e4', 'Nf3', or 'e2e4'.")

    # 1. Try parsing as Standard Algebraic Notation (SAN)
    try:
        move = board.parse_san(cleaned)
        return move
    except chess.AmbiguousMoveError as e:
        raise AmbiguousMoveError(
            f"Move '{cleaned}' is ambiguous.",
            f"Specify the starting file or rank, for example 'Nbd2' instead of 'Nd2'. {e}"
        ) from e
    except chess.IllegalMoveError as e:
        if "missing promotion" in str(e).lower():
            raise InvalidMoveError(
                f"Pawn promotion requires a piece type, e.g. '{cleaned}=Q' or '{cleaned}q'.",
                "Append =Q, =R, =B, or =N (for example: e8=Q or e7e8q)."
            ) from e
        raise InvalidMoveError(
            f"Move '{cleaned}' is illegal in this position.",
            "Verify whose turn it is, piece constraints, and that the king is not in check."
        ) from e
    except chess.InvalidMoveError:
        # Not a valid SAN string; could be UCI / coordinate notation or invalid syntax
        pass

    # 2. Try parsing as coordinate / UCI notation (e.g. e2e4, e7e8q)
    try:
        uci_candidate = cleaned.lower()
        move = chess.Move.from_uci(uci_candidate)
        if move in board.legal_moves:
            return move
        # Check if user forgot promotion piece (e.g. e7e8 when pawn needs promotion)
        if len(uci_candidate) == 4:
            promo_move = chess.Move.from_uci(uci_candidate + "q")
            if promo_move in board.legal_moves:
                raise InvalidMoveError(
                    f"Pawn promotion requires a piece type, e.g. '{uci_candidate}q' for Queen.",
                    "Append q, r, b, or n (for example: e8=Q or e7e8q)."
                )
        raise InvalidMoveError(
            f"Move '{cleaned}' is illegal in this position.",
            "Check that the piece can move to that square and the king is not left in check."
        )
    except ValueError:
        pass

    # 3. If neither worked, give a clear syntax message
    raise InvalidMoveError(
        f"Could not parse '{cleaned}' as a valid chess move.",
        "Use standard algebraic notation (e.g. 'e4', 'Nf3', 'Bxb5+', 'O-O') "
        "or UCI coordinate notation (e.g. 'e2e4', 'g1f3')."
    )


def format_move_san(board: chess.Board, move: chess.Move) -> str:
    """Format a chess.Move object as authoritative SAN string for the given board position."""
    return board.san(move)


def square_to_str(square: chess.Square) -> str:
    """Convert integer square index to square name like 'e4'."""
    return chess.square_name(square)


def str_to_square(name: str) -> Optional[chess.Square]:
    """Parse square string like 'e4' to chess.Square, or None if invalid."""
    try:
        sq = chess.parse_square(name.strip().lower())
        return sq
    except ValueError:
        return None
