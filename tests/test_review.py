"""Automated tests for move classification and game review."""

import chess
from blindchess.analysis import ScoreEvaluation, classify_move_quality
from blindchess.board_state import BoardState
from blindchess.review import review_game


def test_classify_move_quality():
    # Equal move: before 0 cp, after 0 cp
    eval_before = ScoreEvaluation(is_mate=False, centipawns=20, score_for_turn=20)
    eval_after = ScoreEvaluation(is_mate=False, centipawns=15, score_for_turn=-15)
    cat, _ = classify_move_quality(eval_before, eval_after, chess.WHITE)
    assert cat in ("Best / Excellent", "Good")

    # Inaccuracy: 60 cp loss
    eval_inacc = ScoreEvaluation(is_mate=False, centipawns=-40, score_for_turn=40)
    cat_inacc, _ = classify_move_quality(eval_before, eval_inacc, chess.WHITE)
    assert cat_inacc == "Inaccuracy"

    # Blunder: 300 cp loss
    eval_blunder = ScoreEvaluation(is_mate=False, centipawns=-300, score_for_turn=300)
    cat_blunder, _ = classify_move_quality(eval_before, eval_blunder, chess.WHITE)
    assert cat_blunder == "Blunder"


def test_review_game_engine_free_mode():
    state = BoardState()
    state.push_move("e4")
    state.push_move("e5")
    state.push_move("Nf3")

    # Review without engine should not crash
    summary = review_game(state, engine_mgr=None)
    assert summary.total_moves == 3
    assert len(summary.items) == 3
    assert "e4" in summary.items[0].san
