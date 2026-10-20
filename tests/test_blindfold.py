"""Automated tests for progressive blindfold calculations and spatial reasoning across 7 stages."""

from pathlib import Path
import pytest
import chess
from blindchess.blindfold import (
    STAGE_METADATA,
    generate_bishop_diagonal_exercise,
    generate_blindfold_tactic_exercise,
    generate_color_complex_exercise,
    generate_coordinate_intersection_exercise,
    generate_empty_board_destinations_exercise,
    generate_knight_path_exercise,
    generate_knight_shortest_distance_exercise,
    generate_move_sequence_tracking_exercise,
    generate_multi_piece_spatial_exercise,
    generate_position_memory_exercise,
    generate_real_position_legal_move_exercise,
    generate_square_color_exercise,
    generate_starting_rank_exercise,
    generate_unobstructed_reachability_exercise,
    get_blindfold_exercise_by_category,
    get_blindfold_exercise_by_level,
    get_blindfold_exercise_by_stage,
    get_square_color,
    get_stage_info,
    normalize_square_list_input,
    shortest_knight_path,
)
from blindchess.persistence import DatabaseManager


def test_square_colors():
    # Corner squares
    assert get_square_color(chess.A1) == "dark"
    assert get_square_color(chess.H1) == "light"
    assert get_square_color(chess.A8) == "light"
    assert get_square_color(chess.H8) == "dark"

    # Common central squares
    assert get_square_color(chess.E4) == "light"
    assert get_square_color(chess.D4) == "dark"
    assert get_square_color(chess.E5) == "dark"
    assert get_square_color(chess.D5) == "light"

    # Prompt specific square c2
    assert get_square_color(chess.C2) == "light"


def test_stage_1_coordinates_and_colors():
    ex_color = generate_square_color_exercise()
    assert ex_color.stage == 1
    assert ex_color.category == "square_color"
    assert len(ex_color.correct_answers) >= 1

    ex_rank = generate_starting_rank_exercise()
    assert ex_rank.stage == 1
    assert ex_rank.category == "rank_orientation"

    ex_inter = generate_coordinate_intersection_exercise()
    assert ex_inter.stage == 1
    assert len(ex_inter.correct_answers[0]) == 2

    ex_complex = generate_color_complex_exercise()
    assert ex_complex.stage == 1
    assert ex_complex.correct_answers[0] in ("yes", "no")


def test_stage_2_movement_and_legality():
    ex_dest = generate_empty_board_destinations_exercise()
    assert ex_dest.stage == 2
    assert ex_dest.is_empty_board is True
    assert ex_dest.expected_square_set is not None

    ex_reach = generate_unobstructed_reachability_exercise()
    assert ex_reach.stage == 2
    assert ex_reach.correct_answers[0] in ("yes", "no")

    ex_legal = generate_real_position_legal_move_exercise()
    assert ex_legal.stage == 2
    assert ex_legal.is_empty_board is False
    assert ex_legal.fen is not None


def test_stage_3_knight_shortest_path_and_routes():
    # g7 to c4 takes 3 moves
    g7 = chess.G7
    c4 = chess.C4
    dist, paths = shortest_knight_path(g7, c4)
    assert dist == 3
    assert len(paths) >= 1

    # a1 to b2 takes 4 moves
    a1 = chess.A1
    b2 = chess.B2
    dist_a1_b2, paths_a1_b2 = shortest_knight_path(a1, b2)
    assert dist_a1_b2 == 4

    ex_dist = generate_knight_shortest_distance_exercise()
    assert ex_dist.stage == 3

    ex_route = generate_knight_path_exercise()
    assert ex_route.stage == 3
    assert len(ex_route.correct_answers) >= 1


def test_stage_4_multi_piece_spatial():
    ex = generate_multi_piece_spatial_exercise()
    assert ex.stage == 4
    assert ex.category == "multi_piece_sight"
    assert ex.fen is not None


def test_stage_5_position_memory():
    ex = generate_position_memory_exercise()
    assert ex.stage == 5
    assert ex.category == "board_reconstruction"
    assert ex.initial_board_description is not None


def test_stage_6_sequence_tracking():
    ex = generate_move_sequence_tracking_exercise()
    assert ex.stage == 6
    assert ex.category == "sequence_tracking"
    assert ex.moves_sequence is not None
    assert len(ex.moves_sequence) >= 3


def test_stage_7_blindfold_tactics():
    ex = generate_blindfold_tactic_exercise()
    assert ex.stage == 7
    assert ex.category == "blindfold_tactic"
    assert ex.fen is not None


def test_normalize_square_list_input():
    parsed = normalize_square_list_input("a3, c3, d2")
    assert parsed == {chess.A3, chess.C3, chess.D2}

    parsed_spaces = normalize_square_list_input("e4 d6 f6")
    assert parsed_spaces == {chess.E4, chess.D6, chess.F6}


def test_stage_dispatchers_and_metadata():
    for st in range(1, 8):
        info = get_stage_info(st)
        assert "title" in info
        assert "subtitle" in info

        ex = get_blindfold_exercise_by_stage(st)
        assert ex.stage == st
        assert ex.prompt is not None

    # Recurring error lookup
    err_ex = get_blindfold_exercise_by_category("square_color")
    assert err_ex is not None
    assert err_ex.category == "square_color"


def test_spatial_drills_persistence(tmp_path: Path):
    db_file = tmp_path / "test_spatial.db"
    db_mgr = DatabaseManager(db_file)
    try:
        sid = db_mgr.record_session_start(mode="spatial", level=1)

        db_mgr.record_spatial_drill(
            session_id=sid,
            stage=1,
            stage_name="Coordinates & Square Colors",
            category="square_color",
            exercise_id="st1_c2",
            solved=True,
            attempts=1,
            hints_used=0,
            response_time_seconds=2.4,
            user_answer="light",
        )

        db_mgr.record_spatial_drill(
            session_id=sid,
            stage=3,
            stage_name="Knight Movement & Routes",
            category="knight_shortest_distance",
            exercise_id="st3_dist",
            solved=False,
            attempts=2,
            hints_used=1,
            response_time_seconds=5.1,
            user_answer="2",
            error_reason="Incorrect distance",
        )

        mastery_list = db_mgr.get_all_spatial_stage_mastery()
        assert len(mastery_list) == 7
        assert mastery_list[0]["stage"] == 1
        assert mastery_list[0]["unlocked"] is True

        db_mgr.update_spatial_stage_mastery(1, "Coordinates & Square Colors", 5, 5, 100.0)
        updated = db_mgr.get_all_spatial_stage_mastery()
        # Stage 1 should now be completed, and Stage 2 should be unlocked
        assert updated[0]["completed"] is True
        assert updated[1]["unlocked"] is True

        errors = db_mgr.get_recurring_spatial_errors(5)
        assert len(errors) == 1
        assert errors[0]["category"] == "knight_shortest_distance"
        assert errors[0]["failed_attempts"] == 1
    finally:
        db_mgr.close()
