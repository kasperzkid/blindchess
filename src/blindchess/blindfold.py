"""Blindfold chess training exercises, spatial visualization, and session management."""

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import chess

from blindchess.board_state import BoardState, PIECE_NAMES
from blindchess.notation import square_to_str, str_to_square


@dataclass
class BlindfoldExercise:
    """An interactive blindfold or spatial reasoning drill."""
    id: str
    level: int
    category: str
    title: str
    prompt: str
    correct_answers: List[str]
    explanation: str
    hint: str
    fen: Optional[str] = None
    moves_sequence: Optional[List[str]] = None


def get_square_color(square: chess.Square) -> str:
    """Return 'light' or 'dark' for a given chess square."""
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    # White on a1 is dark (0+0 is even -> dark in standard chess)
    return "dark" if (file_idx + rank_idx) % 2 == 0 else "light"


def generate_square_color_exercise() -> BlindfoldExercise:
    """Generate exercise asking for the color of a randomly chosen square."""
    sq = random.choice(chess.SQUARES)
    name = chess.square_name(sq)
    color = get_square_color(sq)

    file_letter = name[0]
    rank_digit = name[1]

    return BlindfoldExercise(
        id=f"sq_color_{name}",
        level=1,
        category="square_color",
        title="Square Color Identification",
        prompt=f"Without looking at a board: What color is the square '{name}'? (Enter 'light' or 'dark')",
        correct_answers=[color, color[0]],  # allow "dark", "light", "d", "l"
        explanation=f"Square {name} is {color}. (File {file_letter} is #{ord(file_letter)-96}, rank {rank_digit}; sum is {'even (dark)' if color == 'dark' else 'odd (light)'}).",
        hint=f"Consider whether {file_letter}1 is dark or light, then count ranks to {rank_digit}.",
    )


def generate_color_complex_exercise() -> BlindfoldExercise:
    """Generate exercise asking whether two squares share the same color complex."""
    sq1, sq2 = random.sample(chess.SQUARES, 2)
    name1, name2 = chess.square_name(sq1), chess.square_name(sq2)
    c1, c2 = get_square_color(sq1), get_square_color(sq2)
    same = (c1 == c2)
    ans = "yes" if same else "no"

    return BlindfoldExercise(
        id=f"color_complex_{name1}_{name2}",
        level=1,
        category="color_complex",
        title="Color Complex Awareness",
        prompt=f"Are the squares '{name1}' and '{name2}' on the same color complex? (yes/no)",
        correct_answers=[ans, ans[0]],
        explanation=f"{name1} is {c1} and {name2} is {c2}. They are {'on the same' if same else 'on different'} colors.",
        hint=f"Identify the color of {name1} first, then {name2}.",
    )


def generate_knight_path_exercise() -> BlindfoldExercise:
    """Ask for the intermediate square for a knight to travel between two squares in 2 hops."""
    # Pick a starting square
    start_sq = random.choice(chess.SQUARES)
    # Get 1-hop destinations
    board = chess.Board(None)  # empty board
    board.set_piece_at(start_sq, chess.Piece(chess.KNIGHT, chess.WHITE))
    one_hops = list(board.attacks(start_sq))

    if not one_hops:
        return generate_square_color_exercise()

    intermediate = random.choice(one_hops)
    board.set_piece_at(start_sq, None)
    board.set_piece_at(intermediate, chess.Piece(chess.KNIGHT, chess.WHITE))
    two_hops = [sq for sq in board.attacks(intermediate) if sq != start_sq]

    if not two_hops:
        return generate_square_color_exercise()

    dest_sq = random.choice(two_hops)

    # Find ALL valid intermediate squares between start and dest
    valid_intermediates = []
    for mid in chess.SQUARES:
        b1 = chess.Board(None)
        b1.set_piece_at(start_sq, chess.Piece(chess.KNIGHT, chess.WHITE))
        if mid in b1.attacks(start_sq):
            b2 = chess.Board(None)
            b2.set_piece_at(mid, chess.Piece(chess.KNIGHT, chess.WHITE))
            if dest_sq in b2.attacks(mid):
                valid_intermediates.append(chess.square_name(mid))

    s_name = chess.square_name(start_sq)
    d_name = chess.square_name(dest_sq)

    return BlindfoldExercise(
        id=f"knight_path_{s_name}_{d_name}",
        level=2,
        category="knight_trajectory",
        title="Knight Route Calculation",
        prompt=(
            f"A knight starts on {s_name} and reaches {d_name} in exactly 2 moves. "
            f"Name a valid intermediate square (e.g. '{valid_intermediates[0]}'):"
        ),
        correct_answers=valid_intermediates,
        explanation=f"Valid intermediate squares between {s_name} and {d_name} are: {', '.join(sorted(valid_intermediates))}.",
        hint="Visualize the L-shaped leaps fanning out from the starting square.",
    )


def generate_bishop_diagonal_exercise() -> BlindfoldExercise:
    """Ask whether a bishop on square A can reach square B along a single diagonal."""
    sq1, sq2 = random.sample(chess.SQUARES, 2)
    name1, name2 = chess.square_name(sq1), chess.square_name(sq2)

    c1, c2 = get_square_color(sq1), get_square_color(sq2)
    b = chess.Board(None)
    b.set_piece_at(sq1, chess.Piece(chess.BISHOP, chess.WHITE))
    can_reach = sq2 in b.attacks(sq1)

    ans = "yes" if can_reach else "no"

    return BlindfoldExercise(
        id=f"bishop_diag_{name1}_{name2}",
        level=2,
        category="bishop_diagonal",
        title="Bishop Diagonal Alignment",
        prompt=f"Can an unobstructed bishop on '{name1}' reach '{name2}' in a single move? (yes/no)",
        correct_answers=[ans, ans[0]],
        explanation=(
            f"A bishop on {name1} ({c1}) {'can' if can_reach else 'cannot'} reach {name2} ({c2}) directly. "
            f"File distance: {abs(chess.square_file(sq1) - chess.square_file(sq2))}, "
            f"Rank distance: {abs(chess.square_rank(sq1) - chess.square_rank(sq2))}."
        ),
        hint=f"Check if {name1} and {name2} share the same color complex and have equal rank/file deltas.",
    )


def generate_move_sequence_tracking_exercise() -> BlindfoldExercise:
    """Replay a short opening sequence mentally and ask where a piece ended up."""
    sequences = [
        (
            ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6"],
            "Where is White's light-squared bishop currently located?",
            ["a4"],
            "The bishop moved: f1 -> b5 -> a4.",
        ),
        (
            ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5", "exd5", "Bg5"],
            "Which piece occupies the d5 square?",
            ["pawn", "black pawn"],
            "Black recaptured on d5 with the e-pawn (exd5).",
        ),
        (
            ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
            "Which square is White's king's knight currently on?",
            ["d4"],
            "White's knight moved g1 -> f3 -> d4 (recapturing the pawn).",
        ),
        (
            ["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6"],
            "Which black piece has moved to the b6 square?",
            ["queen", "black queen"],
            "Black played 5... Qb6 targeting d4 and b2.",
        ),
    ]

    seq, prompt, answers, expl = random.choice(sequences)
    moves_str = " ".join(seq)

    return BlindfoldExercise(
        id=f"seq_track_{seq[0]}_{seq[-1]}",
        level=3,
        category="piece_tracking",
        title="Mental Piece Tracking",
        prompt=(
            f"Mentally visualize this opening sequence from the start:\n"
            f"Moves: {moves_str}\n\n"
            f"Question: {prompt}"
        ),
        correct_answers=answers,
        explanation=expl,
        hint="Mentally step through the moves one by one, watching only the piece in question.",
        moves_sequence=seq,
    )


def get_blindfold_exercise_by_level(level: int) -> BlindfoldExercise:
    """Return a generated exercise matching requested difficulty level (1 to 6)."""
    if level <= 1:
        return random.choice([generate_square_color_exercise, generate_color_complex_exercise])()
    elif level == 2:
        return random.choice([generate_bishop_diagonal_exercise, generate_knight_path_exercise])()
    elif level >= 3:
        return generate_move_sequence_tracking_exercise()
    return generate_square_color_exercise()
