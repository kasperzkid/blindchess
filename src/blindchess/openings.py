"""Opening training subsystem: repertoire recall, branching, and deviation analysis."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import chess

from blindchess.board_state import BoardState
from blindchess.notation import parse_move_on_board


@dataclass
class OpeningRepertoire:
    """A structured opening repertoire line."""
    name: str
    eco: str
    user_side: chess.Color
    moves: List[str]  # SAN sequence, e.g. ["e4", "e5", "Nf3", "Nc6", "Bc4"]
    description: str


BUILTIN_REPERTOIRES: List[OpeningRepertoire] = [
    OpeningRepertoire(
        name="Italian Game (Giuoco Piano)",
        eco="C50",
        user_side=chess.WHITE,
        moves=["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d3"],
        description="Classical king's pawn opening developing toward central control and d3/c3 solidity.",
    ),
    OpeningRepertoire(
        name="Ruy Lopez (Closed Morphy)",
        eco="C84",
        user_side=chess.WHITE,
        moves=["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7", "Re1"],
        description="The Spanish Game applying long-term pressure against Black's e5 pawn anchor.",
    ),
    OpeningRepertoire(
        name="Queen's Gambit Declined",
        eco="D35",
        user_side=chess.WHITE,
        moves=["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5", "exd5", "Bg5"],
        description="Fundamental queen's pawn strategy fighting for the central dark squares.",
    ),
    OpeningRepertoire(
        name="Sicilian Defense (Najdorf)",
        eco="B90",
        user_side=chess.BLACK,
        moves=["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
        description="Sharp counter-attacking system creating asymmetry and Queenside counterplay.",
    ),
    OpeningRepertoire(
        name="Caro-Kann Defense (Classical)",
        eco="B18",
        user_side=chess.BLACK,
        moves=["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"],
        description="Solid pawn structure allowing early development of Black's light-squared bishop.",
    ),
]


class OpeningTrainer:
    """Interactively drills opening repertoires against mental recall."""

    def __init__(self, repertoire: OpeningRepertoire):
        self.repertoire = repertoire
        self.board = chess.Board()
        self.step_idx: int = 0
        self.completed: bool = False
        self.deviated: bool = False

    def is_user_turn(self) -> bool:
        """Return True if current turn matches the repertoire user_side."""
        return self.board.turn == self.repertoire.user_side

    def current_expected_move(self) -> Optional[str]:
        """Return the next expected SAN move in the repertoire."""
        if self.step_idx < len(self.repertoire.moves):
            return self.repertoire.moves[self.step_idx]
        return None

    def play_repertoire_opponent_move(self) -> Optional[str]:
        """If it is opponent's turn, advance the repertoire move automatically."""
        if not self.is_user_turn() and self.step_idx < len(self.repertoire.moves):
            opp_san = self.repertoire.moves[self.step_idx]
            move = self.board.parse_san(opp_san)
            self.board.push(move)
            self.step_idx += 1
            if self.step_idx >= len(self.repertoire.moves):
                self.completed = True
            return opp_san
        return None

    def submit_user_move(self, move_str: str) -> Tuple[bool, str]:
        """Verify user move against repertoire. Return (is_match, message)."""
        expected_san = self.current_expected_move()
        if not expected_san:
            self.completed = True
            return True, "Repertoire line finished!"

        try:
            move = parse_move_on_board(self.board, move_str)
        except Exception as e:
            return False, f"Invalid move notation: {e}"

        san = self.board.san(move)
        if san != expected_san:
            self.deviated = True
            return False, f"Move '{san}' departs from your repertoire (expected '{expected_san}')."

        self.board.push(move)
        self.step_idx += 1

        if self.step_idx >= len(self.repertoire.moves):
            self.completed = True
            return True, f"Repertoire line complete! Excellent recall."

        # Automatically make opponent response
        opp_move = self.play_repertoire_opponent_move()
        if opp_move:
            if self.completed:
                return True, f"Correct: {san}. Opponent plays {opp_move}. Repertoire line complete!"
            return True, f"Correct: {san}. Opponent responds: {opp_move}. Your turn:"
        return True, f"Correct: {san}. Your turn:"
