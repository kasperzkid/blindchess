"""Automated tests for chess notation parsing and validation."""

import pytest
import chess
from blindchess.errors import AmbiguousMoveError, InvalidMoveError
from blindchess.notation import (
    format_move_san,
    normalize_notation_input,
    parse_move_on_board,
    square_to_str,
    str_to_square,
)


def test_normalize_castling():
    assert normalize_notation_input("o-o") == "O-O"
    assert normalize_notation_input("0-0") == "O-O"
    assert normalize_notation_input("O-O") == "O-O"
    assert normalize_notation_input("o-o-o") == "O-O-O"
    assert normalize_notation_input("0-0-0") == "O-O-O"
    assert normalize_notation_input("0-0+") == "O-O+"
    assert normalize_notation_input("o-o#") == "O-O#"


def test_parse_standard_san_opening_moves():
    board = chess.Board()
    move = parse_move_on_board(board, "e4")
    assert move == chess.Move.from_uci("e2e4")
    # Verify board was NOT mutated
    assert board.fen() == chess.STARTING_FEN

    board.push(move)
    move_black = parse_move_on_board(board, "e5")
    assert move_black == chess.Move.from_uci("e7e5")


def test_parse_coordinate_uci_moves():
    board = chess.Board()
    move = parse_move_on_board(board, "e2e4")
    assert move == chess.Move.from_uci("e2e4")
    assert board.san(move) == "e4"

    move_knight = parse_move_on_board(board, "g1f3")
    assert move_knight == chess.Move.from_uci("g1f3")


def test_illegal_move_rejection():
    board = chess.Board()
    with pytest.raises(InvalidMoveError) as exc_info:
        parse_move_on_board(board, "e5")  # White cannot play e5 on move 1
    assert "illegal" in str(exc_info.value).lower()


def test_invalid_syntax_rejection():
    board = chess.Board()
    with pytest.raises(InvalidMoveError):
        parse_move_on_board(board, "invalid_chess_move")
    with pytest.raises(InvalidMoveError):
        parse_move_on_board(board, "")


def test_pawn_promotion_parsing():
    # Position where White can promote on e8 (d8 king, e7 pawn)
    board = chess.Board("3k4/4P3/8/8/8/8/8/4K3 w - - 0 1")
    # SAN promotion
    move_q = parse_move_on_board(board, "e8=Q+")
    assert move_q.promotion == chess.QUEEN

    # UCI promotion
    move_uci = parse_move_on_board(board, "e7e8q")
    assert move_uci.promotion == chess.QUEEN

    # UCI missing promotion piece raises helpful error
    with pytest.raises(InvalidMoveError) as exc_info:
        parse_move_on_board(board, "e7e8")
    assert "promotion" in str(exc_info.value).lower()


def test_ambiguous_move_handling():
    # Two knights on b3 and f3 can both reach empty d2 square
    board = chess.Board("r1bqkbnr/pppppppp/8/8/8/1N3N2/PP2PPPP/R1BQKB1R w KQkq - 0 1")
    with pytest.raises(AmbiguousMoveError):
        parse_move_on_board(board, "Nd2")


def test_square_helpers():
    assert square_to_str(chess.E4) == "e4"
    assert square_to_str(chess.A1) == "a1"
    assert str_to_square("e4") == chess.E4
    assert str_to_square("h8") == chess.H8
    assert str_to_square("invalid") is None
