"""Automated tests for blindfold calculations and spatial reasoning."""

import chess
from blindchess.blindfold import (
    generate_bishop_diagonal_exercise,
    generate_color_complex_exercise,
    generate_knight_path_exercise,
    generate_square_color_exercise,
    get_blindfold_exercise_by_level,
    get_square_color,
)


def test_square_colors():
    # Standard board: a1 is dark, h1 is light, a8 is light, h8 is dark
    assert get_square_color(chess.A1) == "dark"
    assert get_square_color(chess.H1) == "light"
    assert get_square_color(chess.A8) == "light"
    assert get_square_color(chess.H8) == "dark"
    # e4 is light (file 4 + rank 3 = 7 -> odd -> light)
    assert get_square_color(chess.E4) == "light"
    # d4 is dark (file 3 + rank 3 = 6 -> even -> dark)
    assert get_square_color(chess.D4) == "dark"


def test_square_color_exercise_generation():
    ex = generate_square_color_exercise()
    assert ex.level == 1
    assert ex.category == "square_color"
    assert len(ex.correct_answers) > 0


def test_color_complex_exercise_generation():
    ex = generate_color_complex_exercise()
    assert ex.level == 1
    assert ex.category == "color_complex"
    assert ex.correct_answers[0] in ("yes", "no")


def test_knight_path_exercise_generation():
    ex = generate_knight_path_exercise()
    assert ex.level == 2
    assert ex.category in ("knight_trajectory", "square_color")
    assert len(ex.correct_answers) > 0


def test_bishop_diagonal_exercise_generation():
    ex = generate_bishop_diagonal_exercise()
    assert ex.level == 2
    assert ex.category == "bishop_diagonal"
    assert ex.correct_answers[0] in ("yes", "no")


def test_exercise_by_level():
    for lvl in range(1, 5):
        ex = get_blindfold_exercise_by_level(lvl)
        assert ex.prompt is not None
        assert len(ex.correct_answers) > 0
