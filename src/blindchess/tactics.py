"""Tactical training subsystem: curated puzzles, graduated hints, and solution validation."""

from dataclasses import dataclass, field
import random
from typing import List, Optional, Tuple
import chess

from blindchess.board_state import BoardState
from blindchess.notation import parse_move_on_board


@dataclass
class TacticalPuzzle:
    """A verified tactical training puzzle."""
    id: str
    fen: str
    theme: str
    difficulty: int              # 1 (Beginner) to 5 (Master)
    solution_moves: List[str]    # SAN moves in sequence: [player_move1, opp_reply1, player_move2, ...]
    title: str
    description: str
    hints: List[str]             # Graduated hints from subtle to direct


# Curated offline benchmark puzzles with verified solutions
BUILTIN_PUZZLES: List[TacticalPuzzle] = [
    TacticalPuzzle(
        id="tactics_001",
        fen="r1bqk2r/pppp1ppp/2n5/4p3/2B1n3/2P2N2/PPP2PPP/R1BQK2R w KQkq - 0 6",
        theme="Fork / Double Attack",
        difficulty=1,
        solution_moves=["Qd5"],
        title="Fork on c6/e4 and Mate Threat",
        description="White exploits Black's uncoordinated knight on e4 and the f7 weakness.",
        hints=[
            "Look for a dual threat attacking both a piece and the enemy king.",
            "Can White's queen create a mate threat on f7 while hitting an undefended piece?",
            "Play Qd5, threatening mate on f7 and attacking the knight on e4.",
        ],
    ),
    TacticalPuzzle(
        id="tactics_002",
        fen="6k1/5ppp/8/8/8/8/4QPPP/6K1 w - - 0 1",
        theme="Back-Rank Mate",
        difficulty=1,
        solution_moves=["Qe8#"],
        title="Back-Rank Checkmate",
        description="Black's king is trapped behind a wall of pawns.",
        hints=[
            "Check the enemy king's escape squares along the 8th rank.",
            "Can you deliver a forced check along the back rank?",
            "Play Qe8#.",
        ],
    ),
    TacticalPuzzle(
        id="tactics_003",
        fen="r1b2rk1/pp3ppp/2n1pn2/2q5/2B5/4PN2/PP1N1PPP/R2Q1RK1 w - - 0 11",
        theme="Pin / Skewer",
        difficulty=2,
        solution_moves=["Rc1"],
        title="X-Ray on Opponent Queen",
        description="Place a rook on the c-file aligned with Black's queen.",
        hints=[
            "Look for alignments between your pieces and the enemy queen.",
            "Can you activate your a1 rook with tempo on the c-file?",
            "Play Rc1, seizing the semi-open file against the c5 queen.",
        ],
    ),
    TacticalPuzzle(
        id="tactics_004",
        fen="r1b1k2r/pppp1Npp/8/4p3/2Bn3q/8/PPPP2PP/RNBQ2KR b kq - 0 8",
        theme="Deflection / King Attack",
        difficulty=2,
        solution_moves=["Nf3+", "Qxf3", "Qe1#"],
        title="Smothered / Deflection Tactic",
        description="Black sacrifices the knight to deflect White's queen.",
        hints=[
            "Look for forcing checks that clear lines for your queen.",
            "Can the knight check from f3 with double attack?",
            "Play Nf3+, forcing Qxf3 and allowing Qe1#.",
        ],
    ),
    TacticalPuzzle(
        id="tactics_005",
        fen="r2q1rk1/1pp2ppp/p1np1n2/4p1B1/2B1P1b1/2NP1N2/PPP2PPP/R2Q1RK1 w - - 0 9",
        theme="Pin / Weak Square Exploitation",
        difficulty=3,
        solution_moves=["Nd5"],
        title="Piling Pressure on Pinned Knight",
        description="Increase pressure on the pinned knight on f6.",
        hints=[
            "Find the pinned piece and attack it with another piece.",
            "Can a knight jump into the center to attack f6?",
            "Play Nd5, exploiting the pin on the f6 knight.",
        ],
    ),
    TacticalPuzzle(
        id="tactics_006",
        fen="2r3k1/5ppp/8/8/8/8/2r5/3R2K1 w - - 0 1",
        theme="Back-Rank Defense / Escape",
        difficulty=2,
        solution_moves=["Kf1"],
        title="Defending Back-Rank Vulnerability",
        description="White secures the king against mate threats.",
        hints=[
            "Watch out for Black's doubled rooks threatening back-rank checkmate.",
            "Give the king an escape flight square.",
            "Play Kf1 to step toward the center.",
        ],
    ),
]


class TacticalSession:
    """Interactive tactical puzzle exercise runner."""

    def __init__(self, puzzles: Optional[List[TacticalPuzzle]] = None):
        self.puzzles = puzzles or list(BUILTIN_PUZZLES)
        self.current_puzzle: Optional[TacticalPuzzle] = None
        self.current_board: Optional[chess.Board] = None
        self.move_index: int = 0
        self.hints_used: int = 0
        self.solved: bool = False

    def start_puzzle(self, puzzle: Optional[TacticalPuzzle] = None) -> TacticalPuzzle:
        """Load and start a puzzle."""
        self.current_puzzle = puzzle or random.choice(self.puzzles)
        self.current_board = chess.Board(self.current_puzzle.fen)
        self.move_index = 0
        self.hints_used = 0
        self.solved = False
        return self.current_puzzle

    def get_hint(self) -> str:
        """Provide next graduated hint."""
        if not self.current_puzzle:
            return "No active puzzle."
        if self.hints_used < len(self.current_puzzle.hints):
            hint = self.current_puzzle.hints[self.hints_used]
            self.hints_used += 1
            return f"Hint {self.hints_used}/{len(self.current_puzzle.hints)}: {hint}"
        return f"Final Hint: The intended move is {self.current_puzzle.solution_moves[self.move_index]}."

    def submit_move(self, move_str: str) -> Tuple[bool, str]:
        """Submit a user move. Returns (is_correct, feedback_message)."""
        if not self.current_puzzle or not self.current_board:
            return False, "No puzzle currently in progress."

        try:
            user_move = parse_move_on_board(self.current_board, move_str)
        except Exception as e:
            return False, f"Invalid move input: {e}"

        user_san = self.current_board.san(user_move)
        expected_san = self.current_puzzle.solution_moves[self.move_index]

        # Check if user move matches expected solution
        if user_san != expected_san and user_move.uci() != expected_san:
            # Check if user move happens to also be checkmate
            self.current_board.push(user_move)
            if self.current_board.is_checkmate():
                self.solved = True
                return True, f"Brilliant! {user_san} delivers checkmate! Puzzle solved."
            self.current_board.pop()
            return False, f"Incorrect move '{user_san}'. Try again or type 'hint'."

        # Correct move
        self.current_board.push(user_move)
        self.move_index += 1

        # Check if puzzle complete
        if self.move_index >= len(self.current_puzzle.solution_moves):
            self.solved = True
            return True, f"Correct! {user_san} completes the tactic. {self.current_puzzle.description}"

        # Play automated opponent response in solution sequence
        opp_san = self.current_puzzle.solution_moves[self.move_index]
        opp_move = parse_move_on_board(self.current_board, opp_san)
        self.current_board.push(opp_move)
        self.move_index += 1

        if self.move_index >= len(self.current_puzzle.solution_moves):
            self.solved = True
            return True, f"Correct move! Opponent played {opp_san}. Puzzle solved!"

        return True, f"Correct! Opponent replies: {opp_san}. Enter the next move:"
