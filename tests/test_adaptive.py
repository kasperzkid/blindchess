"""Unit and integration tests for BlindChess Adaptive Difficulty & Progression Engine."""

import json
from pathlib import Path
import pytest
import sqlite3
import chess

from blindchess.adaptive import (
    CURRICULUM_LEVELS,
    SKILL_DEFINITIONS,
    AdaptiveConfig,
    AdaptiveEngine,
    SkillProfile,
    generate_adaptive_exercise,
    generate_curriculum_exercise,
    shortest_knight_path_with_obstacles,
)
from blindchess.persistence import DatabaseManager


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    """Provide a fresh SQLite database manager for isolated testing."""
    db_file = tmp_path / "test_adaptive.db"
    return DatabaseManager(db_file)


def test_independent_difficulty_for_each_skill(temp_db: DatabaseManager):
    """Test that skills maintain completely separate difficulty levels and proficiency."""
    engine = AdaptiveEngine(temp_db)
    
    # Coordinates start at difficulty 1
    coord_p = engine.get_profile("coordinates")
    knight_p = engine.get_profile("knight_routes")
    assert coord_p.current_difficulty == 1
    assert knight_p.current_difficulty == 1

    # Simulate 10 successful attempts on knight routes
    for idx in range(10):
        engine.record_attempt(
            skill_id="knight_routes",
            exercise_id=f"knight_test_{idx}",
            is_first_attempt=True,
            is_correct=True,
            hints_used=0,
            response_time=2.0,
        )

    # Knight routes should have promoted to difficulty 2
    assert engine.get_profile("knight_routes").current_difficulty == 2
    # Coordinates should remain unaffected at difficulty 1
    assert engine.get_profile("coordinates").current_difficulty == 1


def test_promotion_after_sustained_success(temp_db: DatabaseManager):
    """Test promotion occurs when player has >= 8 of last 10 first attempts correct across variants."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "square_colors"

    # Submit 7 correct attempts (not yet 8)
    for idx in range(7):
        res = engine.record_attempt(
            skill_id=skill_id,
            exercise_id=f"sq_var_{idx}",
            is_first_attempt=True,
            is_correct=True,
            hints_used=0,
            response_time=1.5,
        )
        assert res.action == "maintained"
        assert engine.get_profile(skill_id).current_difficulty == 1

    # 8th correct attempt in window of 8 attempts (window < 10)
    res = engine.record_attempt(
        skill_id=skill_id,
        exercise_id="sq_var_7",
        is_first_attempt=True,
        is_correct=True,
        hints_used=0,
    )
    assert res.action == "maintained"

    # 9th correct attempt
    res = engine.record_attempt(
        skill_id=skill_id,
        exercise_id="sq_var_8",
        is_first_attempt=True,
        is_correct=True,
        hints_used=0,
    )
    assert res.action == "maintained"

    # 10th attempt (8 of 10 correct, 2 errors)
    res = engine.record_attempt(
        skill_id=skill_id,
        exercise_id="sq_var_9",
        is_first_attempt=True,
        is_correct=False,
    )
    # Total: 9 correct, 1 wrong in last 10 -> Qualifies for promotion!
    # Wait, let's trigger the 10th check:
    # 9 of 10 correct >= 80%
    assert res.action == "promoted"
    assert res.new_difficulty == 2
    assert engine.get_profile(skill_id).current_difficulty == 2


def test_no_promotion_based_on_retries_alone(temp_db: DatabaseManager):
    """Test that solving an exercise on retry does not count toward promotion."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "coordinates"

    # 10 attempts where first attempt was wrong, but solved on retry
    for idx in range(12):
        # First attempt failed
        res1 = engine.record_attempt(
            skill_id=skill_id,
            exercise_id=f"coord_retry_{idx}",
            is_first_attempt=True,
            is_correct=False,
        )
        # Retry succeeded
        res2 = engine.record_attempt(
            skill_id=skill_id,
            exercise_id=f"coord_retry_{idx}",
            is_first_attempt=False,
            is_correct=True,
        )

    prof = engine.get_profile(skill_id)
    # Must NOT have promoted based on retries!
    assert prof.current_difficulty == 1
    assert prof.first_attempt_successes == 0
    assert prof.total_solved == 12


def test_correct_handling_of_hints_and_revealed_answers(temp_db: DatabaseManager):
    """Test that hints and revealed answers do not qualify as clean first-attempt successes."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "move_sequences"

    # 10 attempts with excessive hints (hints_used > 0)
    for idx in range(10):
        res = engine.record_attempt(
            skill_id=skill_id,
            exercise_id=f"seq_{idx}",
            is_first_attempt=True,
            is_correct=True,
            hints_used=1,  # Used hint!
        )

    prof = engine.get_profile(skill_id)
    assert prof.current_difficulty == 1
    assert prof.first_attempt_successes == 0  # not a clean first attempt

    # Revealed answers should receive zero credit
    res = engine.record_attempt(
        skill_id=skill_id,
        exercise_id="seq_skip",
        is_first_attempt=True,
        is_correct=False,
        was_revealed=True,
    )
    assert res.action != "promoted"


def test_demotion_after_repeated_failures(temp_db: DatabaseManager):
    """Test that difficulty is reduced when player gets 4 of the last 5 answers wrong."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "tactical_calc"
    prof = engine.get_profile(skill_id)
    prof.current_difficulty = 3  # Start at difficulty 3

    # 1 correct, then 4 wrong in last 5
    engine.record_attempt(skill_id, "tac_1", is_first_attempt=True, is_correct=True)
    engine.record_attempt(skill_id, "tac_2", is_first_attempt=True, is_correct=False)
    engine.record_attempt(skill_id, "tac_3", is_first_attempt=True, is_correct=False)
    engine.record_attempt(skill_id, "tac_4", is_first_attempt=True, is_correct=False)
    demote_res = engine.record_attempt(skill_id, "tac_5", is_first_attempt=True, is_correct=False)

    assert demote_res.action == "demoted"
    assert demote_res.new_difficulty == 2
    assert engine.get_profile(skill_id).current_difficulty == 2


def test_no_demotion_after_single_mistake(temp_db: DatabaseManager):
    """Test that a single mistake does not trigger demotion."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "spatial_relationships"
    prof = engine.get_profile(skill_id)
    prof.current_difficulty = 4

    # 4 correct, 1 mistake
    engine.record_attempt(skill_id, "sp_1", is_first_attempt=True, is_correct=True)
    engine.record_attempt(skill_id, "sp_2", is_first_attempt=True, is_correct=True)
    engine.record_attempt(skill_id, "sp_3", is_first_attempt=True, is_correct=True)
    engine.record_attempt(skill_id, "sp_4", is_first_attempt=True, is_correct=True)
    res = engine.record_attempt(skill_id, "sp_5", is_first_attempt=True, is_correct=False)

    assert res.action == "maintained"
    assert engine.get_profile(skill_id).current_difficulty == 4


def test_stable_behavior_at_difficulty_boundaries(temp_db: DatabaseManager):
    """Test that difficulty is clamped between Level 1 and Level 10."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "position_memory"
    prof = engine.get_profile(skill_id)

    # Demoting at Level 1 should not go below 1
    prof.current_difficulty = 1
    for idx in range(5):
        res = engine.record_attempt(skill_id, f"pos_fail_{idx}", is_first_attempt=True, is_correct=False)
    assert engine.get_profile(skill_id).current_difficulty == 1

    # Promoting at Level 10 should not exceed 10
    prof.current_difficulty = 10
    prof.recent_first_attempts = []
    prof.recent_hints = []
    prof.recent_exercise_ids = []
    for idx in range(10):
        res = engine.record_attempt(skill_id, f"pos_win_{idx}", is_first_attempt=True, is_correct=True)
    assert engine.get_profile(skill_id).current_difficulty == 10


def test_persistence_after_application_restart(temp_db: DatabaseManager):
    """Test that training progress, difficulty levels, and metrics survive restart."""
    engine1 = AdaptiveEngine(temp_db)
    # Promote knight_routes to level 2
    for idx in range(10):
        engine1.record_attempt("knight_routes", f"kn_save_{idx}", is_first_attempt=True, is_correct=True)

    p1 = engine1.get_profile("knight_routes")
    assert p1.current_difficulty == 2
    assert p1.total_attempts == 10
    assert p1.first_attempt_successes == 10

    # Simulate restart by creating a new engine instance with the same DB
    engine2 = AdaptiveEngine(temp_db)
    p2 = engine2.get_profile("knight_routes")
    assert p2.current_difficulty == 2
    assert p2.total_attempts == 10
    assert p2.first_attempt_successes == 10
    assert p2.name == "Knight-Route Calculation"


def test_recovery_from_missing_or_malformed_progress_data(temp_db: DatabaseManager):
    """Test graceful recovery when database rows contain malformed JSON or corrupted strings."""
    # Insert corrupted JSON directly into adaptive_skill_profiles table
    with temp_db.conn:
        temp_db.conn.execute("""
            INSERT OR REPLACE INTO adaptive_skill_profiles
            (skill_id, name, current_difficulty, proficiency, recent_history_json, mastered_concepts_json)
            VALUES ('coordinates', 'Corrupted Skill', 3, 25.0, '{NOT_VALID_JSON}', 'MALFORMED')
        """)

    # AdaptiveEngine should load without raising exceptions, falling back to safe defaults
    engine = AdaptiveEngine(temp_db)
    p = engine.get_profile("coordinates")
    assert p.current_difficulty == 3
    assert p.recent_first_attempts == []
    assert p.mastered_concepts == set()


def test_exercise_repetition_limits_and_anti_repetition():
    """Test that generate_adaptive_exercise respects exclude_ids."""
    exclude = {"coord_file_e4", "coord_inter_e4"}
    for _ in range(5):
        drill = generate_adaptive_exercise("coordinates", difficulty=1, exclude_ids=exclude)
        assert drill.id not in exclude


def test_all_10_curriculum_levels_generate_valid_drills():
    """Verify that every curriculum level from 1 to 10 generates valid exercises."""
    assert len(CURRICULUM_LEVELS) == 10
    for lvl in range(1, 11):
        drill = generate_curriculum_exercise(lvl)
        assert drill is not None
        assert drill.id is not None
        assert drill.prompt is not None
        assert len(drill.correct_answers) > 0


def test_knight_shortest_path_with_obstacles():
    """Verify BFS knight path calculation with blocked obstacle squares."""
    start = chess.B1
    end = chess.F3
    # Empty board: shortest path is b1 -> d2 -> f3 (length 2)
    dist, paths = shortest_knight_path_with_obstacles(start, end)
    assert dist == 2
    assert any(chess.D2 in p for p in paths)

    # Block d2: intermediate d2 is forbidden!
    # Knight must take alternate route: b1 -> c3 -> e4 -> f3 (or similar 3 hops)
    dist_blocked, paths_blocked = shortest_knight_path_with_obstacles(start, end, blocked={chess.D2})
    assert dist_blocked > 2 or chess.D2 not in [p[1] for p in paths_blocked if len(p) == 3]


def test_reset_adaptive_progress(temp_db: DatabaseManager):
    """Test explicit reset option reverts all skills to Level 1 and clears history."""
    engine = AdaptiveEngine(temp_db)
    # Train coordinates and knight_routes
    for idx in range(10):
        engine.record_attempt("coordinates", f"c_{idx}", is_first_attempt=True, is_correct=True)
    assert engine.get_profile("coordinates").current_difficulty == 2

    # Reset
    engine.reset_all_progress()
    for skill_id in SKILL_DEFINITIONS:
        prof = engine.get_profile(skill_id)
        assert prof.current_difficulty == 1
        assert prof.total_attempts == 0
        assert prof.proficiency == 0.0
