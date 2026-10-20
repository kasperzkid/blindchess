"""Automated tests for BoardState, undo/redo, status checks, and rendering."""

import pytest
import chess
from blindchess.board_state import BoardState
from blindchess.errors import InvalidMoveError, PositionError


def test_board_initialization():
    state = BoardState()
    assert state.turn == chess.WHITE
    assert state.turn_name == "White"
    assert state.move_number == 1
    assert state.ply_count == 0
    assert state.reveal_count == 0
    assert not state.is_game_over()


def test_custom_fen_initialization():
    # Scholar's mate test position
    fen = "r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/2P2N2/PPP2PPP/R1BQK2R w KQkq - 0 6"
    state = BoardState.from_fen(fen)
    assert state.start_fen == fen
    assert state.board.turn == chess.WHITE


def test_invalid_fen_raises():
    with pytest.raises(PositionError):
        BoardState.from_fen("invalid fen string")


def test_push_and_undo_moves():
    state = BoardState()
    rec1 = state.push_move("e4")
    assert rec1.san == "e4"
    assert state.ply_count == 1
    assert state.turn == chess.BLACK

    rec2 = state.push_move("e5")
    assert rec2.san == "e5"
    assert state.ply_count == 2
    assert state.turn == chess.WHITE

    # Undo single move
    undone = state.undo_move()
    assert undone is not None
    assert undone.san == "e5"
    assert state.ply_count == 1
    assert state.turn == chess.BLACK

    # Redo move
    redone = state.redo_move()
    assert redone is not None
    assert redone.san == "e5"
    assert state.ply_count == 2
    assert state.turn == chess.WHITE


def test_undo_full_turn():
    state = BoardState()
    state.push_move("e4")
    state.push_move("e5")
    assert state.ply_count == 2

    undone_turn = state.undo_full_turn()
    assert len(undone_turn) == 2
    assert state.ply_count == 0
    assert state.turn == chess.WHITE


def test_captures_and_material_balance():
    state = BoardState()
    state.push_move("e4")
    state.push_move("d5")
    rec = state.push_move("exd5")
    assert rec.is_capture is True
    assert rec.captured_piece is not None
    assert rec.captured_piece.piece_type == chess.PAWN

    caps = state.get_captured_pieces()
    assert "Pawn" in caps["White"]

    bal = state.get_material_balance()
    assert bal["white"] > bal["black"]
    assert bal["diff"] == 1


def test_game_status_checkmate():
    # Fool's mate
    state = BoardState()
    state.push_move("f3")
    state.push_move("e5")
    state.push_move("g4")
    state.push_move("Qh4#")
    is_over, status, res = state.get_game_status()
    assert is_over is True
    assert "Checkmate" in status
    assert res == "0-1"


def test_board_rendering():
    state = BoardState()
    ascii_board = state.render_board(unicode_pieces=False)
    assert "+-----------------+" in ascii_board
    assert "r n b q k b n r" in ascii_board

    unicode_board = state.render_board(unicode_pieces=True)
    assert "♜" in unicode_board
    assert "♖" in unicode_board


def test_reveal_counter():
    state = BoardState()
    assert state.reveal_count == 0
    state.record_reveal()
    state.record_reveal()
    assert state.reveal_count == 2
