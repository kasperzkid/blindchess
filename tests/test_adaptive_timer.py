"""Unit and integration tests for Adaptive Timers in BlindChess Spatial Memory Drills."""

from pathlib import Path
import time
import pytest
import chess

from blindchess.adaptive import (
    BASE_TIMERS_BY_LEVEL,
    CURRICULUM_LEVELS,
    LEVEL_TIMER_BOUNDS,
    AdaptiveEngine,
    SkillProfile,
    compute_allowed_time,
    compute_exercise_complexity_multiplier,
    generate_adaptive_exercise,
    generate_curriculum_exercise,
)
from blindchess.blindfold import BlindfoldExercise
from blindchess.persistence import DatabaseManager
from blindchess.terminal_ui import TerminalUI


@pytest.fixture
def temp_db(tmp_path: Path) -> DatabaseManager:
    """Provide a fresh SQLite database manager for isolated testing."""
    db_file = tmp_path / "test_timer.db"
    return DatabaseManager(db_file)


def test_correct_base_times_for_all_levels():
    """Verify that each curriculum level 1-10 has the required starting base time."""
    expected = {
        1: 15.0,
        2: 20.0,
        3: 25.0,
        4: 35.0,
        5: 45.0,
        6: 45.0,
        7: 60.0,
        8: 75.0,
        9: 90.0,
        10: 120.0,
    }
    for lvl, expected_time in expected.items():
        assert BASE_TIMERS_BY_LEVEL[lvl] == expected_time


def test_complexity_based_time_adjustments():
    """Test that exercise complexity adjusts time allowed proportionally."""
    simple_ex = BlindfoldExercise(
        id="test_file_id",
        stage=1,
        category="coordinate_file",
        title="File Test",
        prompt="Identify file",
        correct_answers=["e"],
        explanation="e-file",
        hint="check file",
    )
    complex_ex = BlindfoldExercise(
        id="test_neighbors_id",
        stage=1,
        category="coordinate_neighbors",
        title="Neighbors Test",
        prompt="Identify 4 neighbors",
        correct_answers=["e3 e5 d4 f4"],
        expected_square_set={chess.E3, chess.E5, chess.D4, chess.F4},
        explanation="4 neighbors",
        hint="check neighbors",
    )

    t_simple = compute_allowed_time(level=1, exercise=simple_ex)
    t_complex = compute_allowed_time(level=1, exercise=complex_ex)

    assert t_complex > t_simple
    assert compute_exercise_complexity_multiplier(complex_ex) > compute_exercise_complexity_multiplier(simple_ex)


def test_timer_modes_adjust_allowed_time():
    """Test learning mode grants generous time while challenge mode enforces stricter limits."""
    ex = generate_curriculum_exercise(4)  # Knight routes
    profile = SkillProfile(skill_id="knight_routes", name="Knight Routes", current_difficulty=4)

    t_adaptive = compute_allowed_time(4, ex, profile, timer_mode="adaptive")
    t_learning = compute_allowed_time(4, ex, profile, timer_mode="learning")
    t_challenge = compute_allowed_time(4, ex, profile, timer_mode="challenge")

    # Learning mode must be >= 1.4x base/adaptive time
    assert t_learning > t_adaptive
    # Challenge mode must be strictly less than adaptive base
    assert t_challenge < t_adaptive


def test_performance_based_time_adaptation_faster(temp_db: DatabaseManager):
    """Test that consistently fast & correct answers reduce timer gradually down to 0.80."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "knight_routes"
    prof = engine.get_profile(skill_id)
    assert prof.time_multiplier == 1.0

    # 4 fast correct responses (taking 2.0s out of 35.0s allowed)
    for idx in range(4):
        engine.record_attempt(
            skill_id=skill_id,
            exercise_id=f"fast_{idx}",
            is_first_attempt=True,
            is_correct=True,
            response_time=2.0,
            time_allowed=35.0,
            is_timeout=False,
        )

    # Time multiplier should have decreased (down from 1.0 towards 0.80)
    assert engine.get_profile(skill_id).time_multiplier < 1.0
    assert engine.get_profile(skill_id).time_multiplier >= 0.80


def test_performance_based_time_adaptation_slower(temp_db: DatabaseManager):
    """Test that correct but slow answers approaching deadline increase time allowed."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "spatial_relationships"
    prof = engine.get_profile(skill_id)

    # 3 slow correct responses taking 23.0s of 25.0s allowed (> 85%)
    for idx in range(3):
        engine.record_attempt(
            skill_id=skill_id,
            exercise_id=f"slow_{idx}",
            is_first_attempt=True,
            is_correct=True,
            response_time=23.0,
            time_allowed=25.0,
            is_timeout=False,
        )

    assert engine.get_profile(skill_id).time_multiplier > 1.0


def test_timeout_increases_timer_and_records_stats(temp_db: DatabaseManager):
    """Test that timeouts increment timeout counts and expand timer multiplier."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "piece_movement"
    prof = engine.get_profile(skill_id)
    assert prof.total_timeouts == 0

    engine.record_attempt(
        skill_id=skill_id,
        exercise_id="timeout_1",
        is_first_attempt=True,
        is_correct=False,
        response_time=20.0,
        time_allowed=20.0,
        is_timeout=True,
    )

    prof = engine.get_profile(skill_id)
    assert prof.total_timeouts == 1
    assert prof.time_multiplier > 1.0  # Given 15% more time


def test_slow_accurate_users_not_unfairly_demoted(temp_db: DatabaseManager):
    """Test that knowledge mastery and speed are kept separate: slow users with correct answers or timeouts are not demoted."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "tactical_calc"
    prof = engine.get_profile(skill_id)
    prof.current_difficulty = 3

    # User answers slowly (or times out twice), but does not make conceptual blunders
    engine.record_attempt(skill_id, "tac_1", is_first_attempt=True, is_correct=False, is_timeout=True, time_allowed=90.0, response_time=90.0)
    engine.record_attempt(skill_id, "tac_2", is_first_attempt=True, is_correct=True, is_timeout=False, time_allowed=90.0, response_time=80.0)
    engine.record_attempt(skill_id, "tac_3", is_first_attempt=True, is_correct=False, is_timeout=True, time_allowed=90.0, response_time=90.0)
    engine.record_attempt(skill_id, "tac_4", is_first_attempt=True, is_correct=True, is_timeout=False, time_allowed=90.0, response_time=85.0)
    res = engine.record_attempt(skill_id, "tac_5", is_first_attempt=True, is_correct=False, is_timeout=True, time_allowed=90.0, response_time=90.0)

    # Must NOT have demoted!
    assert res.action == "maintained"
    assert engine.get_profile(skill_id).current_difficulty == 3


def test_level_promotion_and_demotion_resets_timer_multiplier(temp_db: DatabaseManager):
    """Test that level promotions and demotions reset timer multiplier to 1.0 for the new level."""
    engine = AdaptiveEngine(temp_db)
    skill_id = "coordinates"
    prof = engine.get_profile(skill_id)
    prof.time_multiplier = 0.85  # Fast on level 1

    # Promote to level 2
    for idx in range(10):
        engine.record_attempt(
            skill_id=skill_id,
            exercise_id=f"coord_{idx}",
            is_first_attempt=True,
            is_correct=True,
            time_allowed=15.0,
            response_time=5.0,
        )

    prof = engine.get_profile(skill_id)
    assert prof.current_difficulty == 2
    # Multiplier resets to 1.0 for the new difficulty tier!
    assert prof.time_multiplier == 1.0


def test_timer_boundary_clamping():
    """Verify that computed time never falls below minimum or exceeds maximum bounds."""
    ex = generate_curriculum_exercise(1)
    prof = SkillProfile(skill_id="coordinates", name="Coordinates", current_difficulty=1, time_multiplier=0.1)
    t_min = compute_allowed_time(1, ex, prof)
    min_b, max_b = LEVEL_TIMER_BOUNDS[1]
    assert t_min >= min_b

    prof.time_multiplier = 10.0
    t_max = compute_allowed_time(1, ex, prof)
    assert t_max <= max_b


def test_timer_persistence_across_sessions(temp_db: DatabaseManager):
    """Verify that timer multiplier, total timeouts, and fastest solve persist in SQLite across restarts."""
    engine1 = AdaptiveEngine(temp_db)
    engine1.record_attempt(
        skill_id="knight_routes",
        exercise_id="pb_test",
        is_first_attempt=True,
        is_correct=True,
        response_time=4.25,
        time_allowed=35.0,
    )
    engine1.record_attempt(
        skill_id="knight_routes",
        exercise_id="to_test",
        is_first_attempt=True,
        is_correct=False,
        response_time=35.0,
        time_allowed=35.0,
        is_timeout=True,
    )
    engine1.set_timer_mode("challenge")

    # Simulate fresh application startup with the same database
    engine2 = AdaptiveEngine(temp_db)
    p2 = engine2.get_profile("knight_routes")
    assert p2.total_timeouts == 1
    assert p2.fastest_solve_seconds == 4.25
    assert p2.timer_mode == "challenge"
    assert engine2.get_timer_mode() == "challenge"


def test_render_timer_bar():
    """Test progress bar rendering in Unicode and ASCII modes."""
    ui_unicode = TerminalUI(ascii_only=False)
    ui_ascii = TerminalUI(ascii_only=True)

    bar_u = ui_unicode.render_timer_bar(remaining_sec=15.0, total_sec=30.0)
    bar_a = ui_ascii.render_timer_bar(remaining_sec=15.0, total_sec=30.0)

    assert len(bar_u) > 0
    assert "█" in bar_u or "░" in bar_u
    assert "=" in bar_a or "." in bar_a
