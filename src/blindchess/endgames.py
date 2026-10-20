"""Endgame training subsystem: classic theoretical positions and optional Syzygy tablebase integration."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
import chess
try:
    import chess.syzygy
except ImportError:
    chess.syzygy = None  # type: ignore

from blindchess.errors import PositionError
from blindchess.notation import parse_move_on_board


@dataclass
class EndgamePosition:
    """A fundamental theoretical endgame position."""
    id: str
    name: str
    category: str  # "Pawn", "Rook", "Checkmate", "Queen"
    fen: str
    objective: str
    key_concept: str
    target_moves: List[str]


BUILTIN_ENDGAMES: List[EndgamePosition] = [
    EndgamePosition(
        id="endgame_001",
        name="Key Squares & Opposition (King + Pawn vs King)",
        category="Pawn",
        fen="8/8/8/4k3/8/4P3/4K3/8 w - - 0 1",
        objective="Advance your pawn and seize the opposition to promote.",
        key_concept="Do not push the pawn prematurely. Keep your king in front of the pawn to control key squares.",
        target_moves=["Kd3", "Kd5", "e4+"],
    ),
    EndgamePosition(
        id="endgame_002",
        name="Lucena Position (Bridge Building)",
        category="Rook",
        fen="1K1k4/1P1r4/8/8/8/8/8/2R5 w - - 0 1",
        objective="Build a bridge with your rook to shield your king from checks and promote the pawn.",
        key_concept="Place the rook on the 4th rank (Rc4), step king out, and use the rook to block vertical checks.",
        target_moves=["Rc4"],
    ),
    EndgamePosition(
        id="endgame_003",
        name="Philidor Position (Third Rank Defense)",
        category="Rook",
        fen="4k3/8/8/4r3/8/8/4PP2/4K3 b - - 0 1",
        objective="Draw against the enemy rook and pawn by controlling the 6th/3rd rank.",
        key_concept="Hold the 3rd rank with your rook until the enemy pawn pushes, then swing behind for rear checks.",
        target_moves=["Re6"],
    ),
    EndgamePosition(
        id="endgame_004",
        name="Basic Checkmate: King and Rook vs King",
        category="Checkmate",
        fen="8/8/8/4k3/8/8/8/R3K3 w - - 0 1",
        objective="Drive the opponent's lone king to the edge of the board and deliver checkmate.",
        key_concept="Use your rook as a fence to restrict king ranks, and march your king to establish opposition.",
        target_moves=["Ra4"],
    ),
]


def probe_tablebase(board: chess.Board, tablebase_path: Optional[str | Path]) -> Optional[str]:
    """Probe local Syzygy tablebases if installed and configured.

    Returns exact theoretical outcome or None if unavailable.
    """
    if not tablebase_path or not chess.syzygy:
        return None

    tb_p = Path(tablebase_path).expanduser().resolve()
    if not tb_p.is_dir():
        return None

    # Syzygy typically covers 3 to 7 pieces
    piece_count = len(board.piece_map())
    if piece_count > 7:
        return None

    try:
        with chess.syzygy.open_tablebase(str(tb_p)) as tablebase:
            wdl = tablebase.probe_wdl(board)
            dtz = tablebase.probe_dtz(board)
            if wdl is not None:
                if wdl > 0:
                    status = f"Theoretical WIN (DTZ: {dtz})"
                elif wdl < 0:
                    status = f"Theoretical LOSS (DTZ: {dtz})"
                else:
                    status = "Theoretical DRAW"
                return status
    except Exception:
        return None

    return None
