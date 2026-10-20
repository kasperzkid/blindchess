"""Automated tests for safe PGN exporting, saving, and parsing."""

from pathlib import Path
import pytest
from blindchess.board_state import BoardState
from blindchess.pgn_tools import (
    export_game_to_pgn,
    load_game_from_pgn,
    load_game_into_board_state,
    save_pgn_to_file,
)


def test_export_and_load_pgn_roundtrip():
    state = BoardState()
    state.push_move("e4")
    state.push_move("e5")
    state.push_move("Nf3")
    state.push_move("Nc6")
    state.push_move("Bb5")

    pgn_str = export_game_to_pgn(state, white_name="Hero", black_name="Stockfish")
    assert '[White "Hero"]' in pgn_str
    assert '[Black "Stockfish"]' in pgn_str
    assert "1. e4 e5 2. Nf3 Nc6 3. Bb5" in pgn_str

    game = load_game_from_pgn(pgn_str)
    assert game.headers["White"] == "Hero"
    assert game.headers["Black"] == "Stockfish"

    reloaded_state = load_game_into_board_state(game)
    assert reloaded_state.ply_count == 5
    assert reloaded_state.board.fen() == state.board.fen()


def test_save_pgn_file(tmp_path: Path):
    state = BoardState()
    state.push_move("d4")
    state.push_move("d5")
    pgn_str = export_game_to_pgn(state)

    target_file = tmp_path / "game.pgn"
    saved_path = save_pgn_to_file(pgn_str, target_file, overwrite=True)
    assert saved_path.is_file()

    with open(saved_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "1. d4 d5" in content
