"""Training statistics aggregation, error pattern tracking, and adaptive difficulty."""

from dataclasses import dataclass, field
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from blindchess.persistence import DatabaseManager


@dataclass
class TrainingSummary:
    """Consolidated summary of local training metrics."""
    total_sessions: int
    total_moves: int
    total_reveals: int
    total_hints: int
    total_training_minutes: float
    tactics_attempted: int
    tactics_solved: int
    tactics_success_rate: float
    calc_drills_count: int
    calc_accuracy_avg: float
    tactics_by_theme: Dict[str, Dict[str, Any]]
    reveal_frequency_per_100_moves: float


@dataclass
class DifficultyRecommendation:
    """Actionable recommendation for adaptive training progression."""
    current_level: int
    recommended_level: int
    action: str              # "maintain", "promote", "demote"
    rationale: str


def compute_training_statistics(db_mgr: DatabaseManager) -> TrainingSummary:
    """Query SQLite database and aggregate all training performance statistics."""
    conn = db_mgr.conn

    # 1. Sessions overview
    cur = conn.execute("""
        SELECT COUNT(*) as count,
               COALESCE(SUM(moves_count), 0) as moves,
               COALESCE(SUM(reveals_count), 0) as reveals,
               COALESCE(SUM(hints_count), 0) as hints,
               COALESCE(SUM(duration_seconds), 0) as duration
        FROM sessions;
    """)
    s_row = cur.fetchone()
    total_sessions = s_row["count"] or 0
    total_moves = s_row["moves"] or 0
    total_reveals = s_row["reveals"] or 0
    total_hints = s_row["hints"] or 0
    total_minutes = round((s_row["duration"] or 0) / 60.0, 1)

    # 2. Tactics stats
    cur = conn.execute("""
        SELECT COUNT(*) as attempted,
               COALESCE(SUM(solved), 0) as solved
        FROM tactical_results;
    """)
    t_row = cur.fetchone()
    tactics_att = t_row["attempted"] or 0
    tactics_sol = t_row["solved"] or 0
    t_rate = round((tactics_sol / tactics_att * 100.0), 1) if tactics_att > 0 else 0.0

    # Tactics theme breakdown
    cur = conn.execute("""
        SELECT theme,
               COUNT(*) as count,
               COALESCE(SUM(solved), 0) as solved,
               COALESCE(SUM(hints_used), 0) as hints
        FROM tactical_results
        GROUP BY theme;
    """)
    tactics_by_theme: Dict[str, Dict[str, Any]] = {}
    for row in cur.fetchall():
        th = row["theme"] or "General"
        c = row["count"]
        s = row["solved"]
        tactics_by_theme[th] = {
            "attempted": c,
            "solved": s,
            "success_rate": round(s / c * 100.0, 1) if c > 0 else 0.0,
            "hints_used": row["hints"],
        }

    # 3. Calculation drills
    cur = conn.execute("""
        SELECT COUNT(*) as count,
               COALESCE(AVG(accuracy_score), 0) as avg_acc
        FROM calculation_drills;
    """)
    c_row = cur.fetchone()
    calc_count = c_row["count"] or 0
    calc_acc = round(float(c_row["avg_acc"] or 0) * 100.0, 1)

    # Reveals per 100 moves
    rev_rate = round((total_reveals / total_moves * 100.0), 2) if total_moves > 0 else 0.0

    return TrainingSummary(
        total_sessions=total_sessions,
        total_moves=total_moves,
        total_reveals=total_reveals,
        total_hints=total_hints,
        total_training_minutes=total_minutes,
        tactics_attempted=tactics_att,
        tactics_solved=tactics_sol,
        tactics_success_rate=t_rate,
        calc_drills_count=calc_count,
        calc_accuracy_avg=calc_acc,
        tactics_by_theme=tactics_by_theme,
        reveal_frequency_per_100_moves=rev_rate,
    )


def evaluate_adaptive_difficulty(db_mgr: DatabaseManager, current_level: int) -> DifficultyRecommendation:
    """Evaluate recent performance and propose an explainable difficulty adjustment."""
    conn = db_mgr.conn

    # Check last 5 tactical drill results
    cur = conn.execute("""
        SELECT solved, hints_used FROM tactical_results
        ORDER BY id DESC LIMIT 10;
    """)
    recent_tactics = cur.fetchall()

    if len(recent_tactics) < 5:
        return DifficultyRecommendation(
            current_level=current_level,
            recommended_level=current_level,
            action="maintain",
            rationale="Need at least 5 completed exercises to evaluate adaptive difficulty.",
        )

    solved_count = sum(r["solved"] for r in recent_tactics)
    total_hints = sum(r["hints_used"] for r in recent_tactics)
    success_rate = solved_count / len(recent_tactics)

    # Check recent reveal frequency
    cur = conn.execute("""
        SELECT reveals_count, moves_count FROM sessions
        ORDER BY id DESC LIMIT 5;
    """)
    recent_sessions = cur.fetchall()
    total_rev = sum(s["reveals_count"] for s in recent_sessions)
    total_mv = sum(s["moves_count"] for s in recent_sessions)
    reveal_ratio = (total_rev / total_mv) if total_mv > 0 else 0.0

    if success_rate >= 0.8 and total_hints <= 2 and reveal_ratio < 0.10:
        if current_level < 6:
            return DifficultyRecommendation(
                current_level=current_level,
                recommended_level=current_level + 1,
                action="promote",
                rationale=(
                    f"Consistently high performance ({int(success_rate*100)}% solve rate, minimal hints, "
                    f"and low board reveals). Ready for Level {current_level + 1}."
                ),
            )

    if success_rate <= 0.4 or reveal_ratio > 0.35:
        if current_level > 1:
            return DifficultyRecommendation(
                current_level=current_level,
                recommended_level=current_level - 1,
                action="demote",
                rationale=(
                    f"Performance indicates high cognitive strain ({int(success_rate*100)}% solve rate, "
                    f"{int(reveal_ratio*100)}% reveal frequency). Recommend consolidating skills at Level {current_level - 1}."
                ),
            )

    return DifficultyRecommendation(
        current_level=current_level,
        recommended_level=current_level,
        action="maintain",
        rationale=f"Performance is balanced at current level ({int(success_rate*100)}% solve rate). Continue practicing.",
    )
