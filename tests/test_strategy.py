"""Automated tests for strategic coach, positional heuristics, and question generation."""

import chess
from blindchess.strategy import (
    evaluate_positional_features,
    explain_move_rationale,
    find_undefended_pieces,
    generate_strategic_questions,
)


def test_find_undefended_pieces():
    # Initial position: rooks on a1 and h1 have no friendly piece defending them
    board = chess.Board()
    w_undef = find_undefended_pieces(board, chess.WHITE)
    assert any("a1" in item for item in w_undef)
    assert any("h1" in item for item in w_undef)

    # Place an undefended knight on e4
    board.set_piece_at(chess.E4, chess.Piece(chess.KNIGHT, chess.WHITE))
    w_undef2 = find_undefended_pieces(board, chess.WHITE)
    assert any("e4" in item for item in w_undef2)


def test_evaluate_positional_features():
    board = chess.Board()
    features = evaluate_positional_features(board)
    assert features.white_development == 0
    assert features.black_development == 0
    assert features.white_king_castled is False


def test_generate_strategic_questions():
    board = chess.Board()
    questions = generate_strategic_questions(board)
    assert len(questions) > 0
    assert "question" in questions[0]
    assert "answer" in questions[0]


def test_explain_move_rationale():
    board = chess.Board()
    move = board.parse_san("e4")
    rationale = explain_move_rationale(board, move)
    assert "central" in rationale.lower() or "e4" in rationale.lower()

    # Knight development
    board.push(move)
    board.push(board.parse_san("e5"))
    nf3_move = board.parse_san("Nf3")
    rationale_nf3 = explain_move_rationale(board, nf3_move)
    assert "develops" in rationale_nf3.lower() or "knight" in rationale_nf3.lower()
