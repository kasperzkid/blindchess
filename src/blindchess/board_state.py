"""Authoritative chess board state, move history, and position query subsystem."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import chess

from blindchess.errors import InvalidMoveError, PositionError
from blindchess.notation import format_move_san, parse_move_on_board, square_to_str, str_to_square


UNICODE_PIECE_SYMBOLS = {
    "P": "♙", "N": "♘", "B": "♗", "R": "♖", "Q": "♕", "K": "♔",
    "p": "♟", "n": "♞", "b": "♝", "r": "♜", "q": "♛", "k": "♚",
}

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King",
}

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


@dataclass
class MoveRecord:
    """Historical record of an applied move."""
    ply: int
    move: chess.Move
    san: str
    fen_before: str
    fen_after: str
    is_capture: bool
    captured_piece: Optional[chess.Piece] = None
    is_check: bool = False
    is_checkmate: bool = False


class BoardState:
    """Manages the chess position, move history, undo/redo, and blindfold queries."""

    def __init__(self, fen: Optional[str] = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self.start_fen: str = self.board.fen()
        self.history: List[MoveRecord] = []
        self._redo_stack: List[chess.Move] = []
        self.reveal_count: int = 0

    @classmethod
    def from_fen(cls, fen: str) -> "BoardState":
        """Instantiate board state from FEN string with validation."""
        try:
            board = chess.Board(fen)
            if not board.is_valid():
                raise PositionError(f"Invalid chess position in FEN: '{fen}'")
            state = cls()
            state.board = board
            state.start_fen = fen
            return state
        except ValueError as e:
            raise PositionError(f"Malformed FEN string: {e}") from e

    def push_move(self, move_or_san: str | chess.Move) -> MoveRecord:
        """Parse, validate, and execute a move. Clear redo stack on new branch."""
        if isinstance(move_or_san, str):
            move = parse_move_on_board(self.board, move_or_san)
        else:
            if move_or_san not in self.board.legal_moves:
                raise InvalidMoveError(
                    f"Illegal move {move_or_san.uci()} in current position."
                )
            move = move_or_san

        fen_before = self.board.fen()
        san = self.board.san(move)
        is_capture = self.board.is_capture(move)
        captured_piece = self.board.piece_at(move.to_square)
        if not captured_piece and self.board.is_en_passant(move):
            # En passant capture
            captured_piece = chess.Piece(chess.PAWN, not self.board.turn)

        self.board.push(move)
        fen_after = self.board.fen()
        is_check = self.board.is_check()
        is_checkmate = self.board.is_checkmate()

        record = MoveRecord(
            ply=len(self.history) + 1,
            move=move,
            san=san,
            fen_before=fen_before,
            fen_after=fen_after,
            is_capture=is_capture,
            captured_piece=captured_piece,
            is_check=is_check,
            is_checkmate=is_checkmate,
        )
        self.history.append(record)
        self._redo_stack.clear()
        return record

    def undo_move(self) -> Optional[MoveRecord]:
        """Undo the most recent move and return its record."""
        if not self.history:
            return None
        last_record = self.history.pop()
        self.board.pop()
        self._redo_stack.append(last_record.move)
        return last_record

    def undo_full_turn(self) -> List[MoveRecord]:
        """Undo a full 2-ply turn (e.g. human move + engine reply)."""
        undone: List[MoveRecord] = []
        for _ in range(2):
            rec = self.undo_move()
            if rec:
                undone.append(rec)
        return undone

    def redo_move(self) -> Optional[MoveRecord]:
        """Redo a previously undone move."""
        if not self._redo_stack:
            return None
        move = self._redo_stack.pop()
        return self.push_move(move)

    def reset(self) -> None:
        """Reset the board to initial standard starting position."""
        self.board.reset()
        self.start_fen = self.board.fen()
        self.history.clear()
        self._redo_stack.clear()
        self.reveal_count = 0

    @property
    def turn(self) -> chess.Color:
        """Return chess.WHITE or chess.BLACK."""
        return self.board.turn

    @property
    def turn_name(self) -> str:
        """Return 'White' or 'Black'."""
        return "White" if self.turn == chess.WHITE else "Black"

    @property
    def move_number(self) -> int:
        """Return the current fullmove number."""
        return self.board.fullmove_number

    @property
    def ply_count(self) -> int:
        """Return total number of half-moves (plies) played."""
        return len(self.history)

    def is_game_over(self) -> bool:
        """Check if game has ended by checkmate, stalemate, or rules."""
        return self.board.is_game_over()

    def get_game_status(self) -> Tuple[bool, str, Optional[str]]:
        """Return (is_over, status_description, result_string)."""
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            res = "0-1" if winner == "Black" else "1-0"
            return True, f"Checkmate! {winner} wins.", res
        if self.board.is_stalemate():
            return True, "Draw by stalemate.", "1/2-1/2"
        if self.board.is_insufficient_material():
            return True, "Draw by insufficient material.", "1/2-1/2"
        if self.board.is_seventyfive_moves():
            return True, "Draw by 75-move rule.", "1/2-1/2"
        if self.board.is_fivefold_repetition():
            return True, "Draw by fivefold repetition.", "1/2-1/2"
        if self.board.can_claim_fifty_moves():
            return False, "Fifty-move draw claim available.", None
        if self.board.can_claim_threefold_repetition():
            return False, "Threefold repetition draw claim available.", None
        if self.board.is_check():
            return False, f"Check! {self.turn_name} is in check.", None
        return False, f"{self.turn_name} to move.", None

    def get_captured_pieces(self) -> Dict[str, List[str]]:
        """Return captured pieces separated by White captures and Black captures."""
        white_captured: List[str] = []
        black_captured: List[str] = []
        for rec in self.history:
            if rec.is_capture and rec.captured_piece:
                p_name = PIECE_NAMES.get(rec.captured_piece.piece_type, "Piece")
                # If White made the move, White captured Black's piece
                if rec.captured_piece.color == chess.BLACK:
                    white_captured.append(p_name)
                else:
                    black_captured.append(p_name)
        return {"White": white_captured, "Black": black_captured}

    def get_material_balance(self) -> Dict[str, int]:
        """Calculate material balance for both sides and relative score."""
        white_val = 0
        black_val = 0
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece:
                val = PIECE_VALUES.get(piece.piece_type, 0)
                if piece.color == chess.WHITE:
                    white_val += val
                else:
                    black_val += val
        diff = white_val - black_val
        return {
            "white": white_val,
            "black": black_val,
            "diff": diff,  # Positive: White advantage; Negative: Black advantage
        }

    def get_piece_at_square(self, sq_str: str) -> Optional[Tuple[str, str]]:
        """Return (Color, PieceType) or None if square is empty."""
        sq = str_to_square(sq_str)
        if sq is None:
            return None
        piece = self.board.piece_at(sq)
        if not piece:
            return None
        color_name = "White" if piece.color == chess.WHITE else "Black"
        piece_name = PIECE_NAMES.get(piece.piece_type, "Unknown")
        return color_name, piece_name

    def render_board(self, unicode_pieces: bool = True, perspective: chess.Color = chess.WHITE) -> str:
        """Render board representation as text string with coordinates."""
        lines = []
        ranks = range(7, -1, -1) if perspective == chess.WHITE else range(0, 8)
        files = range(0, 8) if perspective == chess.WHITE else range(7, -1, -1)

        border = "  +-----------------+"
        lines.append(border)

        for rank in ranks:
            row_items = []
            for file_idx in files:
                sq = chess.square(file_idx, rank)
                piece = self.board.piece_at(sq)
                if piece is None:
                    # Alternating dot / space for empty squares
                    char = "."
                else:
                    symbol = piece.symbol()
                    if unicode_pieces:
                        char = UNICODE_PIECE_SYMBOLS.get(symbol, symbol)
                    else:
                        char = symbol
                row_items.append(char)
            rank_label = rank + 1
            lines.append(f"{rank_label} | {' '.join(row_items)} |")

        lines.append(border)
        file_labels = "    " + " ".join(chess.FILE_NAMES if perspective == chess.WHITE else reversed(chess.FILE_NAMES))
        lines.append(file_labels)
        return "\n".join(lines)

    def record_reveal(self) -> None:
        """Increment count of times user peeked at the board."""
        self.reveal_count += 1
