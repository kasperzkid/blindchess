"""Automated tests for calculation training and missed resource detection."""

import chess
from blindchess.calculation import check_tactical_resources_missed, evaluate_calculation_attempt


def test_missed_mate_in_one():
    # Scholar's mate setup: Qxf7# is mate in 1
    board = chess.Board("r1bqkb1r/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 0 1")
    user_move = board.parse_san("Nf3")  # misses Qxf7#
    missed = check_tactical_resources_missed(board, user_move, None)
    assert any("checkmate" in m.lower() for m in missed)


def test_missed_hanging_piece():
    # White queen on d5 attacks undefended knight on e4
    board = chess.Board("r1bqk2r/pppp1ppp/2n5/3Q4/4n3/5N2/PPP2PPP/RNB1KB1R w KQkq - 0 1")
    # Qxe4+ captures hanging knight
    user_move = board.parse_san("Be2")
    missed = check_tactical_resources_missed(board, user_move, None)
    assert any("hanging piece" in m.lower() for m in missed)


def test_calculation_attempt_evaluation():
    board = chess.Board()
    attempt = evaluate_calculation_attempt(
        board=board,
        user_san="e4",
        predicted_replies=["e5"],
        user_eval="equal",
        engine_mgr=None,
    )
    assert attempt.candidate_san == "e4"
    assert attempt.accuracy_score > 0
