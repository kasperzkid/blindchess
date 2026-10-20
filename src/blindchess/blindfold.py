"""Comprehensive progressive blindfold chess training system across 7 stages."""

from collections import deque
from dataclasses import dataclass, field
import random
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import chess

from blindchess.board_state import PIECE_NAMES
from blindchess.notation import square_to_str, str_to_square


@dataclass
class BlindfoldExercise:
    """An interactive progressive blindfold or spatial reasoning drill."""
    id: str
    stage: int
    category: str
    title: str
    prompt: str
    correct_answers: List[str]
    explanation: str
    hint: str
    level: int = 1                          # For backwards-compatibility
    fen: Optional[str] = None
    initial_board_description: Optional[str] = None  # For Stage 5 memorization
    moves_sequence: Optional[List[str]] = None
    is_empty_board: bool = False
    expected_square_set: Optional[Set[chess.Square]] = None


STAGE_METADATA: Dict[int, Dict[str, str]] = {
    1: {
        "title": "Coordinates & Square Colors",
        "subtitle": "Basic geometry, rank/file orientation, and color recognition.",
        "description": "Master square color parity, starting ranks, coordinate intersections, and color complexes.",
    },
    2: {
        "title": "Piece Movement & Legal Targets",
        "subtitle": "Geometric destinations vs legal moves in real positions.",
        "description": "Distinguish unobstructed board trajectories from pins, checks, and en passant rules.",
    },
    3: {
        "title": "Knight Movement & Routes",
        "subtitle": "Shortest-path BFS calculation and 2-hop intermediate routing.",
        "description": "Calculate exact knight leap sequences, 2-move routes, and distance parity.",
    },
    4: {
        "title": "Multi-Piece Spatial Visualization",
        "subtitle": "Mutual attack lines, pins, forks, and checks.",
        "description": "Mentally place 3-5 pieces and determine check status, defenders, and mutual attacks.",
    },
    5: {
        "title": "Position Memory & Reconstruction",
        "subtitle": "Memorize static positions and reconstruct them mentally.",
        "description": "Read a multi-piece position, commit it to memory, and answer targeted recall probes.",
    },
    6: {
        "title": "Move-Sequence Tracking",
        "subtitle": "Follow multi-ply variations and calculate the resulting position.",
        "description": "Mentally step through opening and tactical lines to deduce final piece squares.",
    },
    7: {
        "title": "Blindfold Tactical Calculation",
        "subtitle": "Calculate forcing lines, checks, and mate threats without a board.",
        "description": "Solve forks, pins, skewers, and multi-move tactical combinations purely in your head.",
    },
}


# -----------------------------------------------------------------------------
# Fundamental Board Math & Pathfinding
# -----------------------------------------------------------------------------

def get_square_color(square: chess.Square) -> str:
    """Return 'light' or 'dark' for a given chess square."""
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    return "dark" if (file_idx + rank_idx) % 2 == 0 else "light"


def shortest_knight_path(start: chess.Square, end: chess.Square) -> Tuple[int, List[List[chess.Square]]]:
    """Compute the shortest knight distance and all optimal paths using BFS and python-chess rules."""
    if start == end:
        return 0, [[start]]

    queue: deque = deque([(start, [start])])
    dist_to: Dict[chess.Square, int] = {start: 0}
    all_shortest: List[List[chess.Square]] = []
    min_dist: Optional[int] = None

    while queue:
        curr, path = queue.popleft()
        curr_dist = len(path) - 1

        if min_dist is not None and curr_dist > min_dist:
            break

        if curr == end:
            if min_dist is None:
                min_dist = curr_dist
            all_shortest.append(path)
            continue

        board = chess.Board(None)
        board.set_piece_at(curr, chess.Piece(chess.KNIGHT, chess.WHITE))
        for nxt in board.attacks(curr):
            nxt_dist = curr_dist + 1
            if min_dist is not None and nxt_dist > min_dist:
                continue
            if nxt not in dist_to or dist_to[nxt] == nxt_dist:
                dist_to[nxt] = nxt_dist
                queue.append((nxt, path + [nxt]))

    return min_dist or 0, all_shortest


def normalize_square_list_input(text: str) -> Set[chess.Square]:
    """Parse comma/space separated square names into a set of chess.Square."""
    tokens = re.split(r"[,;\s]+", text.strip().lower())
    squares = set()
    for t in tokens:
        if len(t) == 2 and t[0] in "abcdefgh" and t[1] in "12345678":
            try:
                squares.add(chess.parse_square(t))
            except ValueError:
                pass
    return squares


# -----------------------------------------------------------------------------
# STAGE 1: Coordinates and Square-Color Recognition
# -----------------------------------------------------------------------------

def generate_square_color_exercise() -> BlindfoldExercise:
    """Identify whether a square is light or dark (e.g. c2, e4, a8)."""
    sq = random.choice(chess.SQUARES)
    name = chess.square_name(sq)
    color = get_square_color(sq)
    f_num = ord(name[0]) - ord('a') + 1
    r_num = int(name[1])

    return BlindfoldExercise(
        id=f"st1_sq_color_{name}",
        stage=1,
        category="square_color",
        title="Square Color Recognition",
        prompt=f"Without looking at a board: What color is the square '{name}'? (light/dark)",
        correct_answers=[color, color[0]],
        explanation=(
            f"Square {name} is {color}. "
            f"File {name[0]} is column #{f_num}, rank is #{r_num}; sum is {f_num + r_num} "
            f"({'even = dark' if color == 'dark' else 'odd = light'})."
        ),
        hint=f"Remember a1 is dark. Calculate parity from {name[0]}1 to rank {name[1]}.",
        level=1,
    )


def generate_starting_rank_exercise() -> BlindfoldExercise:
    """Test awareness of starting ranks and initial piece placement."""
    prompts = [
        ("On which rank do White's pawns start?", ["2", "rank 2", "second"], "White pawns begin on rank 2."),
        ("On which rank do Black's pawns start?", ["7", "rank 7", "seventh"], "Black pawns begin on rank 7."),
        ("Which color's major and minor pieces start on rank 1?", ["white", "w"], "White's pieces start on rank 1."),
        ("Which color's major and minor pieces start on rank 8?", ["black", "b"], "Black's pieces start on rank 8."),
        ("Which ranks are considered the center ranks?", ["4 and 5", "4 5", "4, 5", "4th and 5th"], "Ranks 4 and 5 form the central territory."),
    ]
    p, ans, expl = random.choice(prompts)
    return BlindfoldExercise(
        id=f"st1_rank_{hash(p) % 10000}",
        stage=1,
        category="rank_orientation",
        title="Rank and Side Orientation",
        prompt=p,
        correct_answers=ans,
        explanation=expl,
        hint="Think of the board from White's perspective (ranks 1-2) to Black's (ranks 7-8).",
        level=1,
    )


def generate_coordinate_intersection_exercise() -> BlindfoldExercise:
    """Identify the square at a specific file and rank intersection."""
    file_char = random.choice("abcdefgh")
    rank_num = random.randint(1, 8)
    sq_name = f"{file_char}{rank_num}"
    return BlindfoldExercise(
        id=f"st1_inter_{sq_name}",
        stage=1,
        category="coordinate_intersection",
        title="Coordinate Intersection",
        prompt=f"What square lies at the intersection of the {file_char.upper()}-file and the {rank_num}{'st' if rank_num==1 else ('nd' if rank_num==2 else ('rd' if rank_num==3 else 'th'))} rank?",
        correct_answers=[sq_name],
        explanation=f"The intersection of file '{file_char}' and rank '{rank_num}' is '{sq_name}'.",
        hint="Combine file letter first, then rank digit.",
        level=1,
    )


def generate_color_complex_exercise() -> BlindfoldExercise:
    """Check whether two squares share the same color complex."""
    sq1, sq2 = random.sample(chess.SQUARES, 2)
    n1, n2 = chess.square_name(sq1), chess.square_name(sq2)
    c1, c2 = get_square_color(sq1), get_square_color(sq2)
    same = (c1 == c2)
    ans = "yes" if same else "no"

    return BlindfoldExercise(
        id=f"st1_complex_{n1}_{n2}",
        stage=1,
        category="color_complex",
        title="Color Complex Awareness",
        prompt=f"Are the squares '{n1}' and '{n2}' on the same color complex? (yes/no)",
        correct_answers=[ans, ans[0]],
        explanation=f"{n1} is {c1} and {n2} is {c2}. They are {'on the same' if same else 'on different'} colors.",
        hint=f"Determine whether {n1} is light or dark, then check {n2}.",
        level=1,
    )


# -----------------------------------------------------------------------------
# STAGE 2: Piece Movement and Legal Destination Identification
# -----------------------------------------------------------------------------

def generate_empty_board_destinations_exercise() -> BlindfoldExercise:
    """On an empty board, list all legal destination squares for a piece."""
    # Knight on corners or edges makes a great clean drill
    sq = random.choice([chess.B1, chess.G1, chess.D4, chess.E5, chess.A1, chess.H8, chess.F3, chess.C6])
    sq_name = chess.square_name(sq)

    board = chess.Board(None)
    board.set_piece_at(sq, chess.Piece(chess.KNIGHT, chess.WHITE))
    dest_squares = set(board.attacks(sq))
    dest_names = sorted(chess.square_name(s) for s in dest_squares)
    dest_str = ", ".join(dest_names)

    return BlindfoldExercise(
        id=f"st2_dest_knight_{sq_name}",
        stage=2,
        category="empty_board_movement",
        title="Empty-Board Knight Destinations",
        prompt=(
            f"On an otherwise empty board: List all legal destination squares for a Knight on '{sq_name}'.\n"
            f"(Enter squares separated by commas or spaces, e.g. '{dest_names[0]}, {dest_names[1]}...')"
        ),
        correct_answers=dest_names + [dest_str, " ".join(dest_names)],
        explanation=f"A Knight on {sq_name} controls {len(dest_names)} squares: {dest_str}.",
        hint=f"Calculate the 2+1 L-shapes radiating from {sq_name} within the board bounds.",
        is_empty_board=True,
        expected_square_set=dest_squares,
        level=2,
    )


def generate_unobstructed_reachability_exercise() -> BlindfoldExercise:
    """Can an unobstructed piece reach a destination in exactly one move?"""
    bishop_sq = random.choice([chess.C1, chess.F1, chess.C8, chess.F8, chess.D4])
    target_sq = random.choice(chess.SQUARES)

    b = chess.Board(None)
    b.set_piece_at(bishop_sq, chess.Piece(chess.BISHOP, chess.WHITE))
    can_reach = target_sq in b.attacks(bishop_sq)
    ans = "yes" if can_reach else "no"

    b_name = chess.square_name(bishop_sq)
    t_name = chess.square_name(target_sq)

    return BlindfoldExercise(
        id=f"st2_reach_bishop_{b_name}_{t_name}",
        stage=2,
        category="bishop_diagonal",
        title="Unobstructed Bishop Reachability",
        prompt=f"On an otherwise empty board: Can an unobstructed Bishop on '{b_name}' reach '{t_name}' in a single move? (yes/no)",
        correct_answers=[ans, ans[0]],
        explanation=(
            f"A Bishop on {b_name} {'can' if can_reach else 'cannot'} reach {t_name} in one move. "
            f"{b_name} is {get_square_color(bishop_sq)} and {t_name} is {get_square_color(target_sq)}."
        ),
        hint=f"Bishops travel exclusively along diagonals of the same color.",
        is_empty_board=True,
        level=2,
    )


# Alias for backwards compatibility
generate_bishop_diagonal_exercise = generate_unobstructed_reachability_exercise


def generate_real_position_legal_move_exercise() -> BlindfoldExercise:
    """Distinguish actual legal moves in a position from geometric plausibility (pins/checks)."""
    scenarios = [
        (
            "White: King on e1, Bishop on e2. Black: Rook on e8. Can White's Bishop legally move to d3? (yes/no)",
            ["no", "n"],
            "No. The Bishop on e2 is absolutely pinned to the King on e1 by Black's Rook on e8.",
            "Check if moving the Bishop exposes the White King to check.",
            "4r3/8/8/8/8/8/4B3/4K3 w - - 0 1",
        ),
        (
            "White: King on g1, Pawns on f2, g2, h2. Black: Queen on d1. Can White legally play Kh1? (yes/no)",
            ["no", "n"],
            "No. Queen on d1 controls h1 diagonally (d1-h1 is not diagonal, but checks back rank). White King on g1 is in check from d1!",
            "Determine if Black's Queen on d1 directly attacks the back rank.",
            "6k1/8/8/8/8/8/5PPP/3q2K1 w - - 0 1",
        ),
        (
            "White: Pawn on e5. Black: Pawn on d5 (just advanced d7-d5). Can White legally play exd6 en passant? (yes/no)",
            ["yes", "y"],
            "Yes! En passant is legal immediately after an adjacent enemy pawn advances two squares.",
            "Consider the special en passant capture rule for pawns on the 5th rank.",
            "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2",
        ),
        (
            "White: King on e1, Rook on a1. No enemy pieces attack e1, f1, g1. Can White castle Kingside (O-O)? (yes/no)",
            ["no", "n"],
            "No! The rook is on a1 (Queenside), so Kingside castling is impossible without a rook on h1.",
            "Verify which rook is available for castling.",
            "r3k2r/8/8/8/8/8/8/R3K3 w Qkq - 0 1",
        ),
    ]

    p, ans, expl, hnt, fen = random.choice(scenarios)
    return BlindfoldExercise(
        id=f"st2_legal_{hash(p) % 10000}",
        stage=2,
        category="rules_engine_validation",
        title="Position Rule Legality (Pins & Checks)",
        prompt=p,
        correct_answers=ans,
        explanation=expl,
        hint=hnt,
        fen=fen,
        is_empty_board=False,
        level=2,
    )


# -----------------------------------------------------------------------------
# STAGE 3: Knight Movement and Shortest-Route Challenges
# -----------------------------------------------------------------------------

def generate_knight_path_exercise() -> BlindfoldExercise:
    """Find a valid intermediate square for a knight traveling in exactly 2 moves."""
    # Verified pairs with shortest distance == 2
    sample_pairs = [
        (chess.G7, chess.D4),
        (chess.G7, chess.C5),
        (chess.B1, chess.F3),
        (chess.C3, chess.G5),
        (chess.D2, chess.F6),
        (chess.D4, chess.H4),
        (chess.D4, chess.D8),
        (chess.E5, chess.A5),
        (chess.B8, chess.F6),
        (chess.E4, chess.G8),
        (chess.E2, chess.C6),
        (chess.F3, chess.B3),
        (chess.C1, chess.G3),
    ]
    start_sq, dest_sq = random.choice(sample_pairs)
    dist, paths = shortest_knight_path(start_sq, dest_sq)

    valid_intermediates = sorted(set(chess.square_name(p[1]) for p in paths if len(p) == 3))
    s_name = chess.square_name(start_sq)
    d_name = chess.square_name(dest_sq)

    example_str = f" (e.g. '{valid_intermediates[0]}')" if valid_intermediates else ""

    return BlindfoldExercise(
        id=f"st3_knight_2hop_{s_name}_{d_name}",
        stage=3,
        category="knight_2hop_route",
        title="Knight Two-Move Route",
        prompt=(
            f"A knight starts on '{s_name}' and reaches '{d_name}' in exactly 2 moves.\n"
            f"Name a valid intermediate square{example_str}:"
        ),
        correct_answers=valid_intermediates,
        explanation=f"Valid intermediate squares between {s_name} and {d_name} are: {', '.join(valid_intermediates)}.",
        hint="Visualize the L-shapes fanning out from the starting square that can hop to the target.",
        level=3,
    )


def generate_knight_shortest_distance_exercise() -> BlindfoldExercise:
    """Calculate the minimum number of knight moves between two squares."""
    pairs = [
        (chess.A1, chess.B2, 4, "A corner square to an adjacent diagonal square takes 4 knight hops (e.g. a1-c2-e1-d3-b2)."),
        (chess.A1, chess.C2, 1, "Direct single knight hop (1 rank up, 2 files right)."),
        (chess.E4, chess.E5, 3, "Moving 1 square vertically requires 3 knight hops (e.g. e4-f6-d5-e5)."),
        (chess.G7, chess.C4, 3, "g7 (dark) to c4 (light) changes color complex, requiring an odd count (3 moves: g7-f5-e3-c4)."),
        (chess.D4, chess.D7, 3, "Traveling 3 ranks straight takes 3 knight moves."),
    ]
    s, e, dist, expl = random.choice(pairs)
    s_n = chess.square_name(s)
    e_n = chess.square_name(e)

    return BlindfoldExercise(
        id=f"st3_dist_{s_n}_{e_n}",
        stage=3,
        category="knight_shortest_distance",
        title="Shortest Knight Distance",
        prompt=f"What is the minimum number of knight moves needed to travel from '{s_n}' to '{e_n}' on an empty board?",
        correct_answers=[str(dist)],
        explanation=expl,
        hint=f"Check the color complex of {s_n} and {e_n}: {'same color requires even moves' if get_square_color(s) == get_square_color(e) else 'different colors require odd moves'}.",
        level=3,
    )


# -----------------------------------------------------------------------------
# STAGE 4: Multi-Piece Spatial Visualization
# -----------------------------------------------------------------------------

def generate_multi_piece_spatial_exercise() -> BlindfoldExercise:
    """Visualize 3-5 pieces mentally and answer tactical relationships."""
    scenarios = [
        (
            "White: King on g1, Pawns on f2, g2, h2. Black: Rook on a1.\nIs the White King currently in check? (yes/no)",
            ["yes", "y"],
            "Yes! The 1st rank is completely open between a1 and g1, delivering back-rank check.",
            "Verify whether any piece or pawn obstructs the 1st rank between a1 and g1.",
            "6k1/8/8/8/8/8/5PPP/r5K1 w - - 0 1",
        ),
        (
            "White: Bishop on c4, Knight on f3. Black: Pawn on d5.\nHow many White pieces directly attack the d5 pawn? (0, 1, or 2)",
            ["2", "two"],
            "Both White pieces attack d5: Bishop on c4 along the a2-g8 diagonal, and Knight on f3 via its L-hop.",
            "Calculate lines of attack from c4 and f3 to d5.",
            "rnbqkbnr/ppp1pppp/8/3p4/2B5/5N2/PPPPPPPP/RNBQK2R w KQkq - 0 1",
        ),
        (
            "White: Queen on d4. Black: King on g7, Rook on d8.\nDoes White's Queen currently attack Black's King? (yes/no)",
            ["no", "n"],
            "No. From d4, a queen attacks the d-file, 4th rank, and diagonals (a1-h8 and a7-g1). g7 is not on a diagonal from d4.",
            "Check if g7 lies along a rank, file, or diagonal through d4.",
            "3r4/6k1/8/8/3Q4/8/8/6K1 w - - 0 1",
        ),
    ]

    p, ans, expl, hnt, fen = random.choice(scenarios)
    return BlindfoldExercise(
        id=f"st4_spatial_{hash(p) % 10000}",
        stage=4,
        category="multi_piece_sight",
        title="Multi-Piece Line of Sight",
        prompt=p,
        correct_answers=ans,
        explanation=expl,
        hint=hnt,
        fen=fen,
        level=4,
    )


# -----------------------------------------------------------------------------
# STAGE 5: Position Memory and Mental Board Reconstruction
# -----------------------------------------------------------------------------

def generate_position_memory_exercise() -> BlindfoldExercise:
    """Memorize a position mentally and answer targeted reconstruction probes."""
    positions = [
        {
            "desc": "White: King on h1, Queen on e2, Knight on d4, Pawns on e4, f2\nBlack: King on g8, Queen on d7, Knight on e6, Pawns on d6, g7",
            "q": "Which square is White's Knight on?",
            "ans": ["d4"],
            "expl": "White's Knight is centrally placed on d4.",
            "hint": "Recall the central White minor piece.",
            "fen": "6k1/3q2p1/3pn3/8/3NP3/8/4QP2/7K w - - 0 1",
        },
        {
            "desc": "White: King on g1, Rook on d1, Bishop on g5, Pawn on d4\nBlack: King on g8, Queen on a5, Knight on f6, Pawn on e6",
            "q": "Which Black piece is on a5?",
            "ans": ["queen", "black queen"],
            "expl": "Black's Queen is on a5, creating an active pin or x-ray along the 5th rank.",
            "hint": "Recall the major Black piece located on the queenside a-file.",
            "fen": "5rk1/8/4pn2/q5B1/3P4/8/8/3R2K1 w - - 0 1",
        },
        {
            "desc": "White: King on e1, Pawns on c2, d3, e4\nBlack: King on e8, Pawns on c7, d6, e5",
            "q": "How many total pawns are on the board?",
            "ans": ["6", "six"],
            "expl": "There are 6 total pawns (3 White: c2, d3, e4; 3 Black: c7, d6, e5).",
            "hint": "Count White's pawn chain, then Black's opposing pawn chain.",
            "fen": "4k3/2p5/3p4/4p3/4P3/3P4/2P5/4K3 w - - 0 1",
        },
    ]

    sel = random.choice(positions)
    return BlindfoldExercise(
        id=f"st5_mem_{hash(sel['q']) % 10000}",
        stage=5,
        category="board_reconstruction",
        title="Mental Board Reconstruction",
        prompt=sel["q"],
        correct_answers=sel["ans"],
        explanation=sel["expl"],
        hint=sel["hint"],
        initial_board_description=sel["desc"],
        fen=sel["fen"],
        level=5,
    )


# -----------------------------------------------------------------------------
# STAGE 6: Move-Sequence Tracking & Resulting-Position Calculation
# -----------------------------------------------------------------------------

def generate_move_sequence_tracking_exercise() -> BlindfoldExercise:
    """Step through an opening or tactical line mentally and report resulting piece locations."""
    sequences = [
        (
            ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6"],
            "Where is White's light-squared bishop currently located?",
            ["a4"],
            "The bishop moved: f1 -> b5 -> a4.",
            "Track White's King's bishop through moves 3 and 4.",
        ),
        (
            ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "cxd5", "exd5", "Bg5"],
            "Which piece occupies the d5 square?",
            ["pawn", "black pawn"],
            "Black recaptured on d5 with the e-pawn (exd5).",
            "Consider Black's recapture on move 4.",
        ),
        (
            ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"],
            "Which square is White's king's knight currently on?",
            ["d4"],
            "White's knight moved g1 -> f3 -> d4 (recapturing the pawn).",
            "Recall White's recapture on move 4 in the Open Sicilian.",
        ),
        (
            ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d4", "exd4", "cxd4", "Bb4+"],
            "Which piece delivers check on move 6?",
            ["bishop", "black bishop", "bb4"],
            "Black's dark-squared bishop delivers check from b4 (6... Bb4+).",
            "Identify Black's 6th move in the Italian Game Giuoco Piano.",
        ),
    ]

    seq, prompt, answers, expl, hnt = random.choice(sequences)
    moves_str = " ".join(seq)

    return BlindfoldExercise(
        id=f"st6_seq_{seq[0]}_{seq[-1]}",
        stage=6,
        category="sequence_tracking",
        title="Mental Move-Sequence Tracking",
        prompt=(
            f"Mentally visualize this move sequence from the starting position:\n"
            f"Moves: {moves_str}\n\n"
            f"Question: {prompt}"
        ),
        correct_answers=answers,
        explanation=expl,
        hint=hnt,
        moves_sequence=seq,
        level=6,
    )


# -----------------------------------------------------------------------------
# STAGE 7: Blindfold Tactical Calculation & Short Variations
# -----------------------------------------------------------------------------

def generate_blindfold_tactic_exercise() -> BlindfoldExercise:
    """Calculate forcing variations, checkmates, and tactics completely in the mind."""
    tactics = [
        (
            "White: King on h1, Queen on f3, Knight on e5.\n"
            "Black: King on h8, Queen on e7, Pawn on f7.\n"
            "White plays 1. Qxf7! If Black replies 1... Qxf7, what is White's winning checkmate move?",
            ["ng6#", "ng6", "nxf7#"],
            "1... Qxf7 is answered by 2. Ng6# (or Nxf7#) delivering checkmate with the knight!",
            "Look for a knight leap delivering check to Black's cornered king.",
            "7k/4qp2/8/4N3/8/5Q2/8/7K w - - 0 1",
        ),
        (
            "White: King on g1, Queen on d4.\n"
            "Black: King on g8, Rook on e8, Pawn on e6.\n"
            "White to move. Which Queen move simultaneously forks Black's King and Rook?",
            ["qe4", "qd5+"],
            "Qe4 (or Qd5+) creates a double attack against the King on g8 and the undefended Rook on e8.",
            "Find a central square where White's Queen attacks along both a rank/file and diagonal.",
            "4r1k1/8/4p3/8/3Q4/8/8/6K1 w - - 0 1",
        ),
        (
            "White: King on e1, Bishop on c4, Knight on g5.\n"
            "Black: King on e8, Pawn on f7.\n"
            "White plays 1. Bxf7+! If Black replies 1... Ke7, which square does the White Knight hop to in order to fork King and Queen?",
            ["ne6", "d5"],
            "The knight jumps to e6, attacking the king and controlling critical central avenues.",
            "Calculate forcing knight leaps from g5 toward the Black king.",
            "rnbqkbnr/pppp1p2/8/6N1/2B5/8/PPPPPPPP/RNBQK2R w KQkq - 0 1",
        ),
    ]

    p, ans, expl, hnt, fen = random.choice(tactics)
    return BlindfoldExercise(
        id=f"st7_tactic_{hash(p) % 10000}",
        stage=7,
        category="blindfold_tactic",
        title="Blindfold Tactical Calculation",
        prompt=p,
        correct_answers=ans,
        explanation=expl,
        hint=hnt,
        fen=fen,
        level=7,
    )


# -----------------------------------------------------------------------------
# Stage Dispatcher & Backwards Compatibility
# -----------------------------------------------------------------------------

STAGE_GENERATORS: Dict[int, List[Callable[[], BlindfoldExercise]]] = {
    1: [
        generate_square_color_exercise,
        generate_starting_rank_exercise,
        generate_coordinate_intersection_exercise,
        generate_color_complex_exercise,
    ],
    2: [
        generate_empty_board_destinations_exercise,
        generate_unobstructed_reachability_exercise,
        generate_real_position_legal_move_exercise,
    ],
    3: [
        generate_knight_path_exercise,
        generate_knight_shortest_distance_exercise,
    ],
    4: [
        generate_multi_piece_spatial_exercise,
    ],
    5: [
        generate_position_memory_exercise,
    ],
    6: [
        generate_move_sequence_tracking_exercise,
    ],
    7: [
        generate_blindfold_tactic_exercise,
    ],
}


def get_stage_info(stage: int) -> Dict[str, str]:
    """Return title, subtitle, and description for a given stage (1 to 7)."""
    return STAGE_METADATA.get(stage, STAGE_METADATA[1])


def get_blindfold_exercise_by_stage(stage: int) -> BlindfoldExercise:
    """Generate an exercise strictly belonging to the requested stage (1 to 7)."""
    st = max(1, min(7, stage))
    generators = STAGE_GENERATORS.get(st, STAGE_GENERATORS[1])
    gen = random.choice(generators)
    return gen()


def get_blindfold_exercise_by_category(category: str) -> Optional[BlindfoldExercise]:
    """Generate an exercise matching a specific recurring mistake category."""
    for stage_gens in STAGE_GENERATORS.values():
        for gen in stage_gens:
            ex = gen()
            if ex.category == category:
                return ex
    return get_blindfold_exercise_by_stage(1)


def get_blindfold_exercise_by_level(level: int) -> BlindfoldExercise:
    """Backwards-compatible interface dispatching levels to stages."""
    st = max(1, min(7, level))
    return get_blindfold_exercise_by_stage(st)
