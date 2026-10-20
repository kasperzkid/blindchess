"""Strategic thinking coach: positional analysis, heuristics, and structured questions."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
import chess

from blindchess.board_state import PIECE_NAMES


@dataclass
class PositionalFeatures:
    """Measurable chess positional and structural features."""
    white_development: int       # Minor pieces developed
    black_development: int
    white_center_control: int    # Number of attacks on d4, d5, e4, e5
    black_center_control: int
    white_open_files: List[str]  # Files with no white pawns
    black_open_files: List[str]
    white_isolated_pawns: List[str] # Square names
    black_isolated_pawns: List[str]
    white_passed_pawns: List[str]
    black_passed_pawns: List[str]
    white_undefended_pieces: List[str]
    black_undefended_pieces: List[str]
    white_king_castled: bool
    black_king_castled: bool


def find_undefended_pieces(board: chess.Board, color: chess.Color) -> List[str]:
    """Find friendly pieces (excluding pawns/kings) not protected by any friendly piece."""
    undefended = []
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece and piece.color == color and piece.piece_type not in (chess.PAWN, chess.KING):
            # Check if attacked/defended by own pieces
            defended = board.is_attacked_by(color, sq)
            if not defended:
                undefended.append(f"{piece.symbol()} on {chess.square_name(sq)}")
    return undefended


def evaluate_positional_features(board: chess.Board) -> PositionalFeatures:
    """Extract concrete deterministic positional metrics from the board."""
    center_squares = [chess.D4, chess.D5, chess.E4, chess.E5]
    w_center = sum(len(board.attackers(chess.WHITE, sq)) for sq in center_squares)
    b_center = sum(len(board.attackers(chess.BLACK, sq)) for sq in center_squares)

    # Minor piece development
    w_dev = 0
    b_dev = 0
    for sq in [chess.B1, chess.C1, chess.F1, chess.G1]:
        p = board.piece_at(sq)
        if not p or p.color != chess.WHITE or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
            w_dev += 1
    for sq in [chess.B8, chess.C8, chess.F8, chess.G8]:
        p = board.piece_at(sq)
        if not p or p.color != chess.BLACK or p.piece_type not in (chess.KNIGHT, chess.BISHOP):
            b_dev += 1

    # Pawn structure
    w_isolated = []
    b_isolated = []
    w_passed = []
    b_passed = []

    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.piece_type != chess.PAWN:
            continue
        file_idx = chess.square_file(sq)
        adj_files = [f for f in (file_idx - 1, file_idx + 1) if 0 <= f <= 7]

        # Isolated pawn check
        has_friendly_neighbor = False
        for f in adj_files:
            for r in range(8):
                neighbor = board.piece_at(chess.square(f, r))
                if neighbor and neighbor.piece_type == chess.PAWN and neighbor.color == p.color:
                    has_friendly_neighbor = True
                    break
            if has_friendly_neighbor:
                break

        if not has_friendly_neighbor:
            if p.color == chess.WHITE:
                w_isolated.append(chess.square_name(sq))
            else:
                b_isolated.append(chess.square_name(sq))

        # Passed pawn check
        enemy_color = not p.color
        is_passed = True
        direction = 1 if p.color == chess.WHITE else -1
        target_ranks = range(chess.square_rank(sq) + direction, 8 if direction == 1 else -1, direction)
        files_to_check = [file_idx] + adj_files

        for r in target_ranks:
            for f in files_to_check:
                blocker = board.piece_at(chess.square(f, r))
                if blocker and blocker.piece_type == chess.PAWN and blocker.color == enemy_color:
                    is_passed = False
                    break
            if not is_passed:
                break

        if is_passed:
            if p.color == chess.WHITE:
                w_passed.append(chess.square_name(sq))
            else:
                b_passed.append(chess.square_name(sq))

    # Undefended pieces
    w_undef = find_undefended_pieces(board, chess.WHITE)
    b_undef = find_undefended_pieces(board, chess.BLACK)

    # King castled status
    w_king_sq = board.king(chess.WHITE)
    b_king_sq = board.king(chess.BLACK)
    w_castled = w_king_sq in (chess.G1, chess.C1)
    b_castled = b_king_sq in (chess.G8, chess.C8)

    return PositionalFeatures(
        white_development=w_dev,
        black_development=b_dev,
        white_center_control=w_center,
        black_center_control=b_center,
        white_open_files=[],
        black_open_files=[],
        white_isolated_pawns=w_isolated,
        black_isolated_pawns=b_isolated,
        white_passed_pawns=w_passed,
        black_passed_pawns=b_passed,
        white_undefended_pieces=w_undef,
        black_undefended_pieces=b_undef,
        white_king_castled=w_castled,
        black_king_castled=b_castled,
    )


def generate_strategic_questions(board: chess.Board) -> List[Dict[str, str]]:
    """Generate 2-4 position-specific strategic questions."""
    features = evaluate_positional_features(board)
    turn_color = board.turn
    turn_name = "White" if turn_color == chess.WHITE else "Black"
    opp_name = "Black" if turn_color == chess.WHITE else "White"

    friendly_undef = features.white_undefended_pieces if turn_color == chess.WHITE else features.black_undefended_pieces
    enemy_undef = features.black_undefended_pieces if turn_color == chess.WHITE else features.white_undefended_pieces

    questions = []

    # 1. Opponent threats and undefended pieces
    if friendly_undef:
        questions.append({
            "category": "Defense / Hanging Pieces",
            "question": f"Which of your pieces is undefended and potentially vulnerable?",
            "hint": "Scan all your minor and major pieces to verify they are guarded.",
            "answer": f"Undefended: {', '.join(friendly_undef)}",
        })
    elif enemy_undef:
        questions.append({
            "category": "Tactical Targets",
            "question": f"Can you identify any undefended {opp_name} pieces that could become tactical targets?",
            "hint": "Check opponent pieces on active squares that lack defenders.",
            "answer": f"Opponent undefended pieces: {', '.join(enemy_undef)}",
        })

    # 2. King Safety
    king_castled = features.white_king_castled if turn_color == chess.WHITE else features.black_king_castled
    if not king_castled and board.fullmove_number >= 5:
        questions.append({
            "category": "King Safety",
            "question": f"Your king is still uncastled. Is castling urgent, or is the center closed enough to allow other plans?",
            "hint": "Assess whether opponent can open lines to your central king quickly.",
            "answer": "Prioritize king safety before launching aggressive flank operations.",
        })

    # 3. Center and development
    friendly_dev = features.white_development if turn_color == chess.WHITE else features.black_development
    if friendly_dev < 3 and board.fullmove_number <= 12:
        questions.append({
            "category": "Piece Activity & Development",
            "question": "Which of your pieces is currently the least active / undeveloped?",
            "hint": "Identify bishops or knights still on their initial squares.",
            "answer": "Bring undeveloped minor pieces toward central activity.",
        })

    # Fallback general question
    if not questions:
        questions.append({
            "category": "Candidate Moves",
            "question": "What is your main positional objective here (center break, piece activity, or defending against opponent's plan)?",
            "hint": "Identify the worst placed piece and consider moves to improve it.",
            "answer": "Evaluate candidate moves based on piece harmony and pawn levers.",
        })

    return questions


def explain_move_rationale(
    board: chess.Board,
    move: chess.Move,
    is_engine_best: bool = False,
) -> str:
    """Generate grounded natural-language explanation for why a move is good."""
    san = board.san(move)
    piece = board.piece_at(move.from_square)
    piece_name = PIECE_NAMES.get(piece.piece_type, "Piece") if piece else "Piece"
    is_capture = board.is_capture(move)

    reasons = []

    if is_capture:
        captured = board.piece_at(move.to_square)
        cap_name = PIECE_NAMES.get(captured.piece_type, "Piece") if captured else "material"
        reasons.append(f"captures enemy {cap_name} on {chess.square_name(move.to_square)}")

    # Center control
    if move.to_square in (chess.D4, chess.D5, chess.E4, chess.E5):
        reasons.append("stakes claim directly in the central squares (d4/d5/e4/e5)")

    # Castling
    if board.is_castling(move):
        reasons.append("safeguards the king and activates the rook toward central files")

    # Minor piece development
    if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        if chess.square_rank(move.from_square) in (0, 7):
            reasons.append(f"develops the {piece_name.lower()} into active play")

    # Check
    board.push(move)
    if board.is_check():
        reasons.append("delivers check, forcing an immediate opponent response")
    board.pop()

    if not reasons:
        reasons.append(f"repositions the {piece_name.lower()} to {chess.square_name(move.to_square)}")

    prefix = "Engine's recommendation" if is_engine_best else "Move"
    return f"{prefix} {san}: " + ", and ".join(reasons) + "."
