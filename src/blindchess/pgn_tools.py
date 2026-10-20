"""Safe PGN export, import, parsing, and streaming utilities."""

import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import chess
import chess.pgn

from blindchess.board_state import BoardState
from blindchess.errors import PGNError

MAX_PGN_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit for defense in depth


def export_game_to_pgn(
    board_state: BoardState,
    white_name: str = "Player",
    black_name: str = "Stockfish",
    event: str = "BlindChess Session",
    round_num: str = "1",
    result: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> str:
    """Export a BoardState to a valid standard PGN string."""
    game = chess.pgn.Game()
    game.headers["Event"] = event
    game.headers["Site"] = "Local Machine"
    game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = round_num
    game.headers["White"] = white_name
    game.headers["Black"] = black_name

    if result is None:
        if board_state.board.is_checkmate():
            result = "0-1" if board_state.board.turn == chess.WHITE else "1-0"
        elif board_state.board.is_game_over():
            result = "1/2-1/2"
        else:
            result = "*"
    game.headers["Result"] = result

    # Custom headers
    if headers:
        for k, v in headers.items():
            game.headers[k] = str(v)

    if board_state.start_fen != chess.STARTING_FEN:
        game.setup(chess.Board(board_state.start_fen))

    node = game
    for rec in board_state.history:
        node = node.add_variation(rec.move)

    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    return game.accept(exporter)


def save_pgn_to_file(pgn_text: str, file_path: Path, overwrite: bool = False) -> Path:
    """Save PGN text to a file with directory creation and overwrite safety."""
    path = Path(file_path).expanduser().resolve()
    if path.exists() and not overwrite:
        # Generate alternate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = path.with_stem(f"{path.stem}_{timestamp}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(pgn_text)
    return path


def load_game_from_pgn(pgn_text_or_path: str | Path) -> chess.pgn.Game:
    """Safely parse a PGN string or file path into a chess.pgn.Game object."""
    if isinstance(pgn_text_or_path, Path) or (
        isinstance(pgn_text_or_path, str) and not "\n" in pgn_text_or_path and Path(pgn_text_or_path).is_file()
    ):
        file_path = Path(pgn_text_or_path)
        if file_path.stat().st_size > MAX_PGN_FILE_SIZE:
            raise PGNError(f"PGN file exceeds maximum supported size of {MAX_PGN_FILE_SIZE} bytes.")
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                game = chess.pgn.read_game(f)
        except Exception as e:
            raise PGNError(f"Error reading PGN file {file_path}: {e}") from e
    else:
        text_stream = io.StringIO(pgn_text_or_path)
        try:
            game = chess.pgn.read_game(text_stream)
        except Exception as e:
            raise PGNError(f"Error parsing PGN string: {e}") from e

    if game is None:
        raise PGNError("No valid chess game found in PGN content.")
    return game


def load_game_into_board_state(game: chess.pgn.Game) -> BoardState:
    """Replay game from chess.pgn.Game into a BoardState."""
    start_board = game.board()
    state = BoardState(start_board.fen())
    for move in game.mainline_moves():
        state.push_move(move)
    return state
