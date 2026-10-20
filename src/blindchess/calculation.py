"""Calculation training subsystem: candidate moves, variation depth, and engine comparison."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import chess

from blindchess.analysis import AnalysisResult, ScoreEvaluation, analyse_position
from blindchess.engine_manager import EngineManager


@dataclass
class CalculationAttempt:
    """A user's calculation attempt for a specific position."""
    fen: str
    turn: chess.Color
    candidate_move: chess.Move
    candidate_san: str
    predicted_replies: List[str]  # e.g. ["Nf6", "c4"]
    user_eval_estimate: Optional[str] = None
    engine_best_san: Optional[str] = None
    engine_eval_before: Optional[str] = None
    engine_eval_after: Optional[str] = None
    is_engine_top_choice: bool = False
    missed_resources: List[str] = field(default_factory=list)
    accuracy_score: float = 0.0  # 0.0 to 1.0


def check_tactical_resources_missed(
    board: chess.Board,
    user_move: chess.Move,
    engine_best_move: Optional[chess.Move],
) -> List[str]:
    """Identify concrete tactical features present in the position that may have been missed."""
    missed: List[str] = []

    # 1. Did user miss a forced checkmate?
    for m in board.legal_moves:
        board.push(m)
        if board.is_checkmate() and m != user_move:
            board.pop()
            missed.append(f"Forced checkmate in 1 was available ({board.san(m)}).")
            break
        board.pop()

    # 2. Did user miss a free hanging capture?
    for m in board.legal_moves:
        if board.is_capture(m) and m != user_move:
            to_piece = board.piece_at(m.to_square)
            if to_piece and not board.is_attacked_by(not board.turn, m.to_square):
                # Captured piece is completely undefended
                missed.append(f"Hanging piece capture on {chess.square_name(m.to_square)} was available ({board.san(m)}).")
                break

    # 3. Did user walk into an immediate blunder / hanging piece?
    board.push(user_move)
    for opp_move in board.legal_moves:
        if board.is_capture(opp_move) and opp_move.to_square == user_move.to_square:
            # The piece just moved is immediately recaptured or hanging
            attacker = board.piece_at(opp_move.from_square)
            missed.append(f"The piece moved to {chess.square_name(user_move.to_square)} can be captured immediately by {board.san(opp_move)}.")
            break
    board.pop()

    return missed


def evaluate_calculation_attempt(
    board: chess.Board,
    user_san: str,
    predicted_replies: List[str],
    user_eval: Optional[str],
    engine_mgr: Optional[EngineManager] = None,
    depth: int = 12,
) -> CalculationAttempt:
    """Evaluate candidate move against engine analysis and diagnose missed resources."""
    user_move = board.parse_san(user_san)
    fen = board.fen()
    turn = board.turn

    attempt = CalculationAttempt(
        fen=fen,
        turn=turn,
        candidate_move=user_move,
        candidate_san=user_san,
        predicted_replies=predicted_replies,
        user_eval_estimate=user_eval,
    )

    if engine_mgr and engine_mgr.is_available and engine_mgr.engine:
        # Analyze position before move
        analysis_before = analyse_position(engine_mgr, board, depth=depth, time_limit=1.5, multipv=3)
        if analysis_before.best_line:
            attempt.engine_best_san = analysis_before.best_line.san
            attempt.engine_eval_before = analysis_before.best_line.score.format_white_perspective()
            attempt.is_engine_top_choice = (analysis_before.best_line.move == user_move)

        # Check missed tactical motifs
        attempt.missed_resources = check_tactical_resources_missed(board, user_move, analysis_before.best_move)

        # Push user move to see evaluation after
        board.push(user_move)
        analysis_after = analyse_position(engine_mgr, board, depth=depth, time_limit=1.0, multipv=1)
        if analysis_after.best_line:
            attempt.engine_eval_after = analysis_after.best_line.score.format_white_perspective()
        board.pop()

        # Score accuracy
        if attempt.is_engine_top_choice:
            attempt.accuracy_score = 1.0
        elif not attempt.missed_resources:
            attempt.accuracy_score = 0.7
        else:
            attempt.accuracy_score = 0.3
    else:
        # Engine unavailable fallback: basic heuristic checks
        attempt.missed_resources = check_tactical_resources_missed(board, user_move, None)
        attempt.accuracy_score = 0.5 if not attempt.missed_resources else 0.2

    return attempt
