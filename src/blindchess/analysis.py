"""Engine position analysis, MultiPV evaluation, and move comparison."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import chess
import chess.engine

from blindchess.engine_manager import EngineManager
from blindchess.errors import EngineCommunicationError


@dataclass
class ScoreEvaluation:
    """Precise evaluation with perspective clarity."""
    is_mate: bool
    mate_plies: Optional[int] = None   # Positive: engine/evaluated side wins in N plies
    centipawns: Optional[int] = None   # Centipawns from White's perspective (+ = White advantage)
    score_for_turn: Optional[int] = None # Centipawns from perspective of side to move

    def format_white_perspective(self) -> str:
        """Format score from White's perspective (standard chess convention)."""
        if self.is_mate and self.mate_plies is not None:
            moves = (abs(self.mate_plies) + 1) // 2
            return f"+M{moves}" if self.mate_plies > 0 else f"-M{moves}"
        if self.centipawns is not None:
            pawns = self.centipawns / 100.0
            return f"+{pawns:.2f}" if pawns > 0 else f"{pawns:.2f}"
        return "0.00"

    def format_turn_perspective(self, turn: chess.Color) -> str:
        """Format score from perspective of the player whose turn it is."""
        if self.is_mate and self.mate_plies is not None:
            moves = (abs(self.mate_plies) + 1) // 2
            return f"Mate in {moves}" if self.mate_plies > 0 else f"Mated in {moves}"
        if self.score_for_turn is not None:
            pawns = self.score_for_turn / 100.0
            return f"+{pawns:.2f}" if pawns > 0 else f"{pawns:.2f}"
        return self.format_white_perspective()


@dataclass
class AnalysisLine:
    """A single candidate move line (one principal variation in MultiPV)."""
    rank: int                    # 1 = best line
    move: chess.Move             # First move in candidate line
    san: str                     # SAN of first move
    score: ScoreEvaluation
    depth: int
    pv_moves: List[chess.Move]
    pv_sans: List[str]
    nodes: Optional[int] = None
    time_taken: Optional[float] = None

    def format_line(self) -> str:
        """Render a readable summary of this candidate line."""
        pv_str = " ".join(self.pv_sans[:6])
        if len(self.pv_sans) > 6:
            pv_str += " ..."
        score_str = self.score.format_white_perspective()
        return f"{self.rank}. {self.san:<7} (Eval: {score_str:>7}, d={self.depth}) -> {pv_str}"


@dataclass
class AnalysisResult:
    """Collection of candidate lines from an analysis session."""
    fen: str
    turn: chess.Color
    lines: List[AnalysisLine]

    @property
    def best_line(self) -> Optional[AnalysisLine]:
        return self.lines[0] if self.lines else None

    @property
    def best_move(self) -> Optional[chess.Move]:
        return self.lines[0].move if self.lines else None

    @property
    def best_san(self) -> Optional[str]:
        return self.lines[0].san if self.lines else None


def evaluate_score(score: chess.engine.Score, turn: chess.Color) -> ScoreEvaluation:
    """Parse chess.engine.Score into a typed ScoreEvaluation with dual perspective."""
    white_score = score.white()
    turn_score = score.pov(turn)

    if white_score.is_mate():
        m_moves = white_score.mate()
        m_plies = (m_moves * 2) if m_moves is not None else None
        return ScoreEvaluation(
            is_mate=True,
            mate_plies=m_plies,
            centipawns=None,
            score_for_turn=None,
        )
    else:
        cp = white_score.score()
        cp_turn = turn_score.score()
        return ScoreEvaluation(
            is_mate=False,
            mate_plies=None,
            centipawns=cp,
            score_for_turn=cp_turn,
        )


def analyse_position(
    engine_mgr: EngineManager,
    board: chess.Board,
    depth: int = 15,
    time_limit: Optional[float] = 2.0,
    multipv: int = 1,
) -> AnalysisResult:
    """Analyze the given board position with MultiPV support."""
    if not engine_mgr.engine:
        raise EngineCommunicationError("Engine is not running for analysis.")

    # Apply MultiPV option if supported
    if "MultiPV" in engine_mgr.supported_options:
        try:
            engine_mgr.engine.configure({"MultiPV": max(1, multipv)})
        except Exception:
            pass

    limit = chess.engine.Limit(depth=depth, time=time_limit)
    try:
        raw_infos = engine_mgr.engine.analyse(board, limit, multipv=multipv)
    except Exception as e:
        raise EngineCommunicationError(f"Engine analysis failed: {e}") from e

    # chess.engine.analyse can return a single dict or list of dicts for multipv
    if isinstance(raw_infos, dict):
        raw_infos = [raw_infos]

    lines: List[AnalysisLine] = []
    # Sort by MultiPV rank
    sorted_infos = sorted(raw_infos, key=lambda x: x.get("multipv", 1))

    for rank_idx, info in enumerate(sorted_infos, start=1):
        pv = info.get("pv", [])
        if not pv:
            continue
        first_move = pv[0]
        san = board.san(first_move)

        # Build SAN sequence for PV
        temp_board = board.copy()
        pv_sans: List[str] = []
        for m in pv:
            if m in temp_board.legal_moves:
                pv_sans.append(temp_board.san(m))
                temp_board.push(m)
            else:
                break

        score_obj = info.get("score")
        if score_obj:
            score_eval = evaluate_score(score_obj, board.turn)
        else:
            score_eval = ScoreEvaluation(is_mate=False, centipawns=0, score_for_turn=0)

        lines.append(
            AnalysisLine(
                rank=info.get("multipv", rank_idx),
                move=first_move,
                san=san,
                score=score_eval,
                depth=info.get("depth", depth),
                pv_moves=pv,
                pv_sans=pv_sans,
                nodes=info.get("nodes"),
                time_taken=info.get("time"),
            )
        )

    return AnalysisResult(fen=board.fen(), turn=board.turn, lines=lines)


def classify_move_quality(
    eval_before: ScoreEvaluation,
    eval_after: ScoreEvaluation,
    turn: chess.Color,
) -> Tuple[str, str]:
    """Classify move quality based on evaluation loss from moving player's perspective.

    Returns:
        (category, explanation)
    """
    # If mate score was changed
    if eval_before.is_mate and eval_before.mate_plies is not None and eval_before.mate_plies > 0:
        if not eval_after.is_mate or (eval_after.mate_plies is not None and eval_after.mate_plies <= 0):
            return "Missed Win", "A forced checkmate continuation was missed."

    # Compare centipawn loss from moving player's perspective
    # Note: score_for_turn is from perspective of side to move in that position
    cp_before = eval_before.score_for_turn or 0
    # After move, it is opponent's turn, so moving player's score is -eval_after.score_for_turn
    cp_after = -(eval_after.score_for_turn or 0)
    cp_loss = cp_before - cp_after

    if cp_loss <= 15:
        return "Best / Excellent", "Maintains optimal evaluation."
    elif cp_loss <= 45:
        return "Good", "Solid move with negligible difference."
    elif cp_loss <= 90:
        return "Inaccuracy", f"Slight positional concession ({cp_loss} cp loss)."
    elif cp_loss <= 200:
        return "Mistake", f"Gives away significant advantage ({cp_loss} cp loss)."
    else:
        return "Blunder", f"Major tactical or material error ({cp_loss} cp loss)."
