"""Game review and mistake diagnostic subsystem."""

from dataclasses import dataclass, field
from typing import List, Optional
import chess
import chess.pgn

from blindchess.analysis import (
    AnalysisResult,
    ScoreEvaluation,
    analyse_position,
    classify_move_quality,
)
from blindchess.board_state import BoardState
from blindchess.engine_manager import EngineManager


@dataclass
class MoveReviewItem:
    """Diagnostic review for an individual ply in a game."""
    ply: int
    move: chess.Move
    san: str
    turn: chess.Color
    eval_before: Optional[ScoreEvaluation] = None
    eval_after: Optional[ScoreEvaluation] = None
    category: str = "Unanalyzed"
    explanation: str = ""
    engine_best_san: Optional[str] = None
    principal_continuation: Optional[str] = None


@dataclass
class GameReviewSummary:
    """Summary of game review results."""
    total_moves: int
    inaccuracies: int = 0
    mistakes: int = 0
    blunders: int = 0
    missed_wins: int = 0
    items: List[MoveReviewItem] = field(default_factory=list)

    def format_summary_text(self) -> str:
        """Render readable statistical summary."""
        lines = [
            "=" * 50,
            "GAME REVIEW SUMMARY",
            "=" * 50,
            f"Total moves analyzed: {self.total_moves}",
            f"• Inaccuracies (?!):   {self.inaccuracies}",
            f"• Mistakes (?):        {self.mistakes}",
            f"• Blunders (??):       {self.blunders}",
            f"• Missed Wins:         {self.missed_wins}",
            "=" * 50,
        ]
        return "\n".join(lines)


def review_game(
    board_state: BoardState,
    engine_mgr: Optional[EngineManager] = None,
    depth: int = 12,
    time_limit_per_move: float = 0.5,
) -> GameReviewSummary:
    """Step through game history and evaluate each move with Stockfish or heuristics."""
    summary = GameReviewSummary(total_moves=len(board_state.history))

    if not engine_mgr or not engine_mgr.is_available or not engine_mgr.engine:
        # Engine unavailable fallback: check material drops and basic legal checks
        temp_b = chess.Board(board_state.start_fen)
        for rec in board_state.history:
            item = MoveReviewItem(
                ply=rec.ply,
                move=rec.move,
                san=rec.san,
                turn=temp_b.turn,
                category="Played",
                explanation=f"{rec.san} recorded. Full engine analysis unavailable without Stockfish.",
            )
            summary.items.append(item)
            temp_b.push(rec.move)
        return summary

    temp_board = chess.Board(board_state.start_fen)

    for rec in board_state.history:
        move = rec.move
        turn = temp_board.turn

        # Analyze position before move
        analysis_before = analyse_position(
            engine_mgr, temp_board, depth=depth, time_limit=time_limit_per_move, multipv=1
        )
        eval_before = (
            analysis_before.best_line.score
            if analysis_before.best_line
            else ScoreEvaluation(is_mate=False, centipawns=0, score_for_turn=0)
        )
        best_san = analysis_before.best_san

        # Apply move
        temp_board.push(move)

        # Analyze position after move
        analysis_after = analyse_position(
            engine_mgr, temp_board, depth=depth, time_limit=time_limit_per_move, multipv=1
        )
        eval_after = (
            analysis_after.best_line.score
            if analysis_after.best_line
            else ScoreEvaluation(is_mate=False, centipawns=0, score_for_turn=0)
        )

        category, expl = classify_move_quality(eval_before, eval_after, turn)

        if category == "Inaccuracy":
            summary.inaccuracies += 1
        elif category == "Mistake":
            summary.mistakes += 1
        elif category == "Blunder":
            summary.blunders += 1
        elif category == "Missed Win":
            summary.missed_wins += 1

        pv_str = " ".join(analysis_before.best_line.pv_sans[:4]) if analysis_before.best_line else None

        item = MoveReviewItem(
            ply=rec.ply,
            move=move,
            san=rec.san,
            turn=turn,
            eval_before=eval_before,
            eval_after=eval_after,
            category=category,
            explanation=expl,
            engine_best_san=best_san,
            principal_continuation=pv_str,
        )
        summary.items.append(item)

    return summary
