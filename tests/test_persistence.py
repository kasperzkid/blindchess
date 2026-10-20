"""Automated tests for SQLite persistence, sessions, backups, and metrics."""

from pathlib import Path
import pytest
from blindchess.persistence import DatabaseManager
from blindchess.statistics import compute_training_statistics, evaluate_adaptive_difficulty


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    db_file = tmp_path / "test_blindchess.db"
    mgr = DatabaseManager(db_file)
    yield mgr
    mgr.close()


def test_session_lifecycle(temp_db: DatabaseManager):
    sid = temp_db.record_session_start(mode="blindfold", level=2)
    assert sid > 0

    temp_db.record_session_end(
        session_id=sid,
        duration_sec=120.5,
        moves_count=15,
        reveals_count=1,
        hints_count=0,
        result="1-0",
        notes="Victory in test game",
    )

    cur = temp_db.conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,))
    row = cur.fetchone()
    assert row["moves_count"] == 15
    assert row["reveals_count"] == 1
    assert row["result"] == "1-0"


def test_tactical_and_calculation_records(temp_db: DatabaseManager):
    sid = temp_db.record_session_start(mode="tactics", level=1)
    temp_db.record_tactical_result(sid, "puz_1", "Fork", True, 1)

    temp_db.record_calculation_drill(
        session_id=sid,
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        candidate_san="e4",
        predicted_replies=["e5"],
        user_eval="equal",
        engine_best_san="e4",
        is_engine_top=True,
        accuracy_score=1.0,
        missed_resources=[],
    )

    stats = compute_training_statistics(temp_db)
    assert stats.tactics_attempted == 1
    assert stats.tactics_solved == 1
    assert stats.calc_drills_count == 1
    assert stats.calc_accuracy_avg == 100.0


def test_backup_database(temp_db: DatabaseManager, tmp_path: Path):
    backup_file = tmp_path / "manual_backup.db"
    res_path = temp_db.backup_database(backup_file)
    assert res_path.is_file()
    assert res_path.stat().st_size > 0


def test_clear_all_history(temp_db: DatabaseManager):
    sid = temp_db.record_session_start(mode="play", level=1)
    temp_db.record_tactical_result(sid, "puz_2", "Pin", True, 0)
    temp_db.clear_all_history()

    stats = compute_training_statistics(temp_db)
    assert stats.total_sessions == 0
    assert stats.tactics_attempted == 0
