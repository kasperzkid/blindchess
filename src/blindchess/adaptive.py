"""Adaptive difficulty engine, curriculum progression, and skill tracking for BlindChess."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import random
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import chess

from blindchess.blindfold import (
    BlindfoldExercise,
    get_square_color,
    normalize_square_list_input,
    shortest_knight_path,
)
from blindchess.errors import BlindChessError


# -----------------------------------------------------------------------------
# Configuration & Thresholds
# -----------------------------------------------------------------------------

BASE_TIMERS_BY_LEVEL: Dict[int, float] = {
    1: 15.0,   # Board coordinates and square colors
    2: 20.0,   # Individual piece movement
    3: 25.0,   # Spatial relationships
    4: 35.0,   # Knight routes
    5: 45.0,   # Multi-move routes
    6: 45.0,   # Multiple pieces
    7: 60.0,   # Position memory
    8: 75.0,   # Move sequence tracking
    9: 90.0,   # Tactical visualization
    10: 120.0, # Advanced blindfold calculation
}

LEVEL_TIMER_BOUNDS: Dict[int, Tuple[float, float]] = {
    1: (8.0, 30.0),
    2: (10.0, 40.0),
    3: (12.0, 50.0),
    4: (15.0, 70.0),
    5: (20.0, 90.0),
    6: (20.0, 90.0),
    7: (25.0, 120.0),
    8: (30.0, 150.0),
    9: (40.0, 180.0),
    10: (50.0, 240.0),
}


@dataclass
class AdaptiveConfig:
    """Configurable thresholds for promotion, demotion, and anti-repetition."""
    promotion_min_accuracy: float = 0.8         # >= 80% correct first attempts
    promotion_window: int = 10                  # over last 10 attempts
    promotion_min_variants: int = 2             # at least 2 distinct exercise variants
    promotion_max_hint_ratio: float = 0.2       # hints used on <= 20% of attempts in window
    demotion_fail_count: int = 4                # 4 failures
    demotion_window: int = 5                    # in the last 5 attempts
    spaced_repetition_interval_days: int = 3    # review mastered items after 3 days
    recent_history_limit: int = 20              # avoid repeating last N exercise variants


@dataclass
class PromotionResult:
    """Result of evaluating a player's attempt for difficulty adaptation."""
    action: str                                 # "promoted", "demoted", "maintained"
    old_difficulty: int
    new_difficulty: int
    reason: str
    message: Optional[str] = None


def compute_exercise_complexity_multiplier(exercise: BlindfoldExercise) -> float:
    """Compute complexity factor based on exercise category, plies, and constraints."""
    category_factors = {
        "coordinate_file": 0.85,
        "coordinate_intersection": 0.85,
        "coordinate_neighbors": 1.25,
        "coordinate_distance": 1.20,
        "square_color": 0.85,
        "color_complex": 1.0,
        "diagonal_color": 1.15,
        "empty_board_rook": 0.90,
        "corner_knight_movement": 1.0,
        "position_legality": 1.30,
        "spatial_line_sharing": 0.85,
        "king_distance": 1.10,
        "spatial_midpoint": 1.25,
        "knight_1hop": 0.80,
        "knight_2hop_route": 1.0,
        "knight_shortest_distance": 1.25,
        "multi_piece_sight": 1.0,
        "board_reconstruction": 1.20,
        "sequence_tracking": 1.25,
        "blindfold_tactic": 1.30,
    }

    mult = category_factors.get(exercise.category, 1.0)

    if exercise.expected_square_set and len(exercise.expected_square_set) > 2:
        mult *= 1.20

    if exercise.moves_sequence:
        if len(exercise.moves_sequence) >= 6:
            mult *= 1.30
        elif len(exercise.moves_sequence) >= 4:
            mult *= 1.15

    return round(mult, 2)


def compute_allowed_time(
    level: int,
    exercise: BlindfoldExercise,
    profile: Optional["SkillProfile"] = None,
    timer_mode: Optional[str] = None,
) -> float:
    """
    Calculate the precise time allowed in seconds for a specific exercise.
    
    Determined by:
    - Current curriculum level (1 to 10 base times).
    - Exercise complexity multiplier.
    - User demonstrated performance multiplier (0.80 to 1.50).
    - Timer mode (learning=1.5x, adaptive=1.0x, challenge=0.85x).
    """
    lvl = max(1, min(10, level))
    base = BASE_TIMERS_BY_LEVEL.get(lvl, 30.0)
    complexity = compute_exercise_complexity_multiplier(exercise)

    mode = timer_mode or (profile.timer_mode if profile else "adaptive")
    perf_mult = profile.time_multiplier if (profile and mode == "adaptive") else 1.0

    if mode == "learning":
        mode_mult = 1.50
    elif mode == "challenge":
        mode_mult = 0.85
    else:
        mode_mult = 1.0

    raw_time = base * complexity * perf_mult * mode_mult
    min_b, max_b = LEVEL_TIMER_BOUNDS.get(lvl, (10.0, 180.0))

    if mode == "learning":
        max_b *= 1.5

    return round(max(min_b, min(max_b, raw_time)), 1)


# -----------------------------------------------------------------------------
# 9 Independent Skill Definitions
# -----------------------------------------------------------------------------

SKILL_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "coordinates": {
        "name": "Coordinate Recognition",
        "description": "Board coordinates, ranks, files, intersections, and edge squares.",
        "primary_curriculum_level": 1,
    },
    "square_colors": {
        "name": "Square-Color Recognition",
        "description": "Immediate square color parity, color complexes, and diagonal color shifts.",
        "primary_curriculum_level": 1,
    },
    "piece_movement": {
        "name": "Piece Movement & Legality",
        "description": "Geometric reachability on empty board vs legal moves in real positions.",
        "primary_curriculum_level": 2,
    },
    "spatial_relationships": {
        "name": "Spatial Relationships",
        "description": "Shared lines, distance estimation, alignments, and geometry.",
        "primary_curriculum_level": 3,
    },
    "knight_routes": {
        "name": "Knight-Route Calculation",
        "description": "1-move hops, 2-hop intermediate squares, multi-move routes, and shortest paths.",
        "primary_curriculum_level": 4,
    },
    "multi_piece": {
        "name": "Multi-Piece Visualization",
        "description": "Lines of sight, pins, forks, and attacker/defender balances across 3-5 pieces.",
        "primary_curriculum_level": 6,
    },
    "position_memory": {
        "name": "Position Memory",
        "description": "Static position memorization, hidden-board recall, and piece reconstruction.",
        "primary_curriculum_level": 7,
    },
    "move_sequences": {
        "name": "Move-Sequence Tracking",
        "description": "Mental 3-8 ply variation execution and resulting position calculation.",
        "primary_curriculum_level": 8,
    },
    "tactical_calc": {
        "name": "Tactical Visualization",
        "description": "Calculating forcing lines, checks, captures, undefended pieces, and mating nets.",
        "primary_curriculum_level": 9,
    },
}


# -----------------------------------------------------------------------------
# 10 Ordered Curriculum Levels
# -----------------------------------------------------------------------------

CURRICULUM_LEVELS: Dict[int, Dict[str, Any]] = {
    1: {
        "title": "Level 1 — Board Foundations",
        "subtitle": "Files, ranks, square colors, coordinate orientation.",
        "description": "Identify files, ranks, square colors, starting squares, and basic coordinates.",
        "primary_skill": "coordinates",
    },
    2: {
        "title": "Level 2 — Individual Piece Movement",
        "subtitle": "Geometric destinations on empty board & board edge boundaries.",
        "description": "Distinguish rook, bishop, queen, king, knight, and pawn movement and legal destinations.",
        "primary_skill": "piece_movement",
    },
    3: {
        "title": "Level 3 — Spatial Relationships",
        "subtitle": "Shared files/ranks/diagonals, color math, and distance estimation.",
        "description": "Determine line-sharing, calculate square colors mentally, and estimate square distances.",
        "primary_skill": "spatial_relationships",
    },
    4: {
        "title": "Level 4 — Basic Knight Routes",
        "subtitle": "1-move leaps, 2-move routes, and intermediate squares.",
        "description": "Find 1-move knight destinations, calculate 2-move routes, and name intermediate squares.",
        "primary_skill": "knight_routes",
    },
    5: {
        "title": "Level 5 — Multi-Move Routes",
        "subtitle": "3- and 4-move knight routes, shortest paths, and obstacle navigation.",
        "description": "Solve 3- and 4-move knight routes, compare routes, and navigate around blocked squares.",
        "primary_skill": "knight_routes",
    },
    6: {
        "title": "Level 6 — Multiple Pieces",
        "subtitle": "Track 2+ pieces simultaneously, attacks, and pin relationships.",
        "description": "Track multiple pieces mentally, determine attacks, and distinguish geometry from legal moves.",
        "primary_skill": "multi_piece",
    },
    7: {
        "title": "Level 7 — Position Memory",
        "subtitle": "Memorize static piece locations and reconstruct layouts mentally.",
        "description": "Memorize piece positions, answer recall probes after board is hidden, and reconstruct layouts.",
        "primary_skill": "position_memory",
    },
    8: {
        "title": "Level 8 — Move Sequences",
        "subtitle": "Track 3-8 ply variations and calculate resulting positions.",
        "description": "Track move sequences mentally, identify captures, and deduce changed piece locations.",
        "primary_skill": "move_sequences",
    },
    9: {
        "title": "Level 9 — Tactical Visualization",
        "subtitle": "Calculate checks, captures, threats, and 2-4 ply combinations.",
        "description": "Visualize 2-4 ply variations, identify undefended pieces, and calculate forcing combinations.",
        "primary_skill": "tactical_calc",
    },
    10: {
        "title": "Level 10 — Advanced Blindfold Calculation",
        "subtitle": "Longer variations, candidate moves, and branching tactical trees.",
        "description": "Calculate 4-8 ply variations without a board, compare candidate moves, and evaluate resulting positions.",
        "primary_skill": "tactical_calc",
    },
}


# -----------------------------------------------------------------------------
# Skill Profile Data Structure
# -----------------------------------------------------------------------------

@dataclass
class SkillProfile:
    """Tracks independent proficiency and progression for a single skill."""
    skill_id: str
    name: str
    current_difficulty: int = 1
    proficiency: float = 0.0
    total_attempts: int = 0
    first_attempt_successes: int = 0
    total_solved: int = 0
    total_hints: int = 0
    total_response_time: float = 0.0
    recent_first_attempts: List[bool] = field(default_factory=list)
    recent_hints: List[int] = field(default_factory=list)
    recent_exercise_ids: List[str] = field(default_factory=list)
    recent_mistakes: List[str] = field(default_factory=list)
    mastered_concepts: Set[str] = field(default_factory=set)
    last_trained_at: Optional[str] = None

    # Adaptive Timing Attributes
    time_multiplier: float = 1.0                # Adapts between 0.80 and 1.50 based on performance
    total_timeouts: int = 0
    fastest_solve_seconds: Optional[float] = None
    timer_mode: str = "adaptive"                # "learning", "adaptive", "challenge"
    recent_response_ratios: List[float] = field(default_factory=list)

    @property
    def timeout_rate(self) -> float:
        """Percentage of attempts that resulted in timeout."""
        if self.total_attempts == 0:
            return 0.0
        return round((self.total_timeouts / self.total_attempts) * 100.0, 1)

    @property
    def recent_accuracy(self) -> float:
        """Accuracy percentage across the recent attempts window."""
        if not self.recent_first_attempts:
            return 0.0
        return round((sum(1 for x in self.recent_first_attempts if x) / len(self.recent_first_attempts)) * 100.0, 1)

    @property
    def first_attempt_accuracy(self) -> float:
        """Lifetime first-attempt accuracy percentage."""
        if self.total_attempts == 0:
            return 0.0
        return round((self.first_attempt_successes / self.total_attempts) * 100.0, 1)

    @property
    def avg_response_time(self) -> float:
        """Average response time in seconds."""
        if self.total_attempts == 0:
            return 0.0
        return round(self.total_response_time / self.total_attempts, 1)

    def get_next_objective(self) -> str:
        """Generate human-readable next objective for UI display."""
        diff = self.current_difficulty
        objectives: Dict[str, Dict[int, str]] = {
            "coordinates": {
                1: "Identify basic file and rank coordinates.",
                2: "Identify coordinate intersections instantly.",
                3: "Recognize board edges and corner squares without hesitating.",
                4: "Name all 4 orthogonal neighboring squares.",
                5: "Calculate Manhattan distances between coordinates.",
                6: "Calculate diagonal intersection squares mentally.",
                7: "Navigate coordinate quadrants accurately without sight.",
                8: "Solve multi-coordinate parity puzzles.",
                9: "Rapid coordinate mapping under 3 seconds.",
                10: "Flawless instant spatial coordinate mastery.",
            },
            "square_colors": {
                1: "Identify whether individual squares (e.g. c2, e4) are light or dark.",
                2: "Identify color complexes of starting piece squares.",
                3: "Determine if two squares share the same color complex.",
                4: "Calculate color parity across diagonal paths.",
                5: "Determine square color shifts after knight moves.",
                6: "Recognize long-diagonal square colors instantly.",
                7: "Recall colors for any pair of coordinates in under 2 seconds.",
                8: "Solve 4-square color parity challenges.",
                9: "Advanced multi-square color mapping.",
                10: "Instantaneous unconscious square-color mastery.",
            },
            "piece_movement": {
                1: "List legal destinations for Rook or Bishop on an empty board.",
                2: "List legal knight leap targets from edge and center squares.",
                3: "Identify Queen and King destination boundaries.",
                4: "Calculate unavailable squares on board boundaries.",
                5: "Determine pawn double-step and capture destinations.",
                6: "Distinguish geometric moves from legal moves in check.",
                7: "Recognize absolute pin restrictions on moving pieces.",
                8: "Validate en passant legality under spatial constraints.",
                9: "Calculate castling legality through attacked squares.",
                10: "Master comprehensive piece movement rules under pins & checks.",
            },
            "spatial_relationships": {
                1: "Determine if two squares share a file or rank.",
                2: "Determine if two squares share a diagonal.",
                3: "Estimate Chebyshev (king move) distance between squares.",
                4: "Calculate diagonal intersection of two distant squares.",
                5: "Identify squares lying directly between two pieces.",
                6: "Determine knight fork geometric relations.",
                7: "Estimate Manhattan vs Chebyshev distance differentials.",
                8: "Solve triangular geometric alignments.",
                9: "Rapid spatial relationship calculation under 3 seconds.",
                10: "Complete mental board geometric mastery.",
            },
            "knight_routes": {
                1: "Find all 1-move knight destinations from any square.",
                2: "Find a valid two-move route with intermediate square without hints.",
                3: "Determine if a destination takes an even or odd number of moves.",
                4: "Find two distinct intermediate squares for a 2-hop route.",
                5: "Find shortest 3-move knight routes on an empty board.",
                6: "Navigate 3-move knight routes avoiding blocked squares.",
                7: "Calculate 4-move knight routes between distant corners.",
                8: "Compare candidate routes and identify the unique shortest path.",
                9: "Solve complex knight routes with multiple obstacles.",
                10: "Grandmaster-level instant knight pathfinding.",
            },
            "multi_piece": {
                1: "Track 2 pieces and determine direct check status.",
                2: "Track 3 pieces and calculate mutual attack lines.",
                3: "Determine attacker vs defender count on a central square.",
                4: "Recognize absolute pins between King, Bishop, and Rook.",
                5: "Identify double attacks and forks with 3 pieces.",
                6: "Calculate discovered check rays through an intermediate piece.",
                7: "Track 4 pieces and identify undefended pieces.",
                8: "Calculate 5-piece mutual attack and defence nets.",
                9: "Track dynamic pin-breaking interactions mentally.",
                10: "Flawless multi-piece spatial visualization.",
            },
            "position_memory": {
                1: "Memorize 3-4 piece locations and recall piece on a given square.",
                2: "Recall the exact square of a piece after board is hidden.",
                3: "Memorize 5 pieces and recall total pawn count on a file.",
                4: "Reconstruct a 5-piece position from partial clues.",
                5: "Memorize a 6-7 piece opening position and recall all minors.",
                6: "Recall piece colors on specific ranks without peeking.",
                7: "Memorize an 8-piece endgame setup and identify king positions.",
                8: "Reconstruct 8 pieces from memory with zero errors.",
                9: "Memorize 10+ piece complex middlegame positions.",
                10: "Photographic mental board reconstruction.",
            },
            "move_sequences": {
                1: "Track a 2-ply move sequence and report final square.",
                2: "Track a 3-ply opening sequence and identify the moved piece.",
                3: "Follow a 4-ply line with pawn captures.",
                4: "Determine which piece occupies a contested square after 4 plies.",
                5: "Track a 5-ply variation including castling.",
                6: "Follow a 6-ply line and identify which piece delivered check.",
                7: "Track piece trades and determine remaining material after 6 plies.",
                8: "Follow an 8-ply variation and recall exact final board features.",
                9: "Calculate deep tactical branching variations mentally.",
                10: "Master 8+ ply deep sequence tracking without board.",
            },
            "tactical_calc": {
                1: "Calculate a 1-move checkmate or direct capture.",
                2: "Identify a 1-move knight fork or skewer.",
                3: "Calculate a 2-ply forcing tactic (check then capture).",
                4: "Find a queen double attack winning material in 2 plies.",
                5: "Calculate a 3-ply deflection combination.",
                6: "Identify pieces left undefended after a 3-ply sequence.",
                7: "Calculate a 4-ply forcing mate combination.",
                8: "Visualize intermediate checks (zwischenzug) in 4-ply lines.",
                9: "Calculate 5-6 ply forcing tactical lines without sight.",
                10: "Deep blindfold combination calculation.",
            },
        }

        skill_objs = objectives.get(self.skill_id, {})
        return skill_objs.get(diff, f"Advance {self.name} to higher proficiency.")


# -----------------------------------------------------------------------------
# Shortest Knight Path with Obstacles (BFS)
# -----------------------------------------------------------------------------

def shortest_knight_path_with_obstacles(
    start: chess.Square,
    end: chess.Square,
    blocked: Optional[Set[chess.Square]] = None,
) -> Tuple[int, List[List[chess.Square]]]:
    """Compute shortest knight path avoiding blocked squares."""
    blocked_set = blocked or set()
    if start == end:
        return 0, [[start]]
    if start in blocked_set or end in blocked_set:
        return 0, []

    queue = deque([(start, [start])])
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
            if nxt in blocked_set and nxt != end:
                continue
            nxt_dist = curr_dist + 1
            if min_dist is not None and nxt_dist > min_dist:
                continue
            if nxt not in dist_to or dist_to[nxt] == nxt_dist:
                dist_to[nxt] = nxt_dist
                queue.append((nxt, path + [nxt]))

    return min_dist or 0, all_shortest


# -----------------------------------------------------------------------------
# Adaptive Engine Controller
# -----------------------------------------------------------------------------

class AdaptiveEngine:
    """Intelligent performance-based difficulty engine that continuously adapts to player skill."""

    def __init__(self, db_mgr: Any = None, config: Optional[AdaptiveConfig] = None):
        self.db_mgr = db_mgr
        self.config = config or AdaptiveConfig()
        self.profiles: Dict[str, SkillProfile] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load all skill profiles from database or initialize defaults."""
        for skill_id, info in SKILL_DEFINITIONS.items():
            loaded = None
            if self.db_mgr and hasattr(self.db_mgr, "get_skill_profile"):
                try:
                    loaded = self.db_mgr.get_skill_profile(skill_id)
                except Exception:
                    loaded = None

            if loaded:
                self.profiles[skill_id] = loaded
            else:
                self.profiles[skill_id] = SkillProfile(
                    skill_id=skill_id,
                    name=info["name"],
                    current_difficulty=1,
                    proficiency=0.0,
                )

    def save_all_profiles(self) -> None:
        """Persist all skill profiles to the database."""
        if not self.db_mgr or not hasattr(self.db_mgr, "save_skill_profile"):
            return
        for profile in self.profiles.values():
            try:
                self.db_mgr.save_skill_profile(profile)
            except Exception:
                pass

    def get_profile(self, skill_id: str) -> SkillProfile:
        """Retrieve the profile for a given skill ID."""
        if skill_id not in self.profiles:
            info = SKILL_DEFINITIONS.get(skill_id, {"name": skill_id.replace("_", " ").title()})
            self.profiles[skill_id] = SkillProfile(
                skill_id=skill_id,
                name=info["name"],
                current_difficulty=1,
            )
        return self.profiles[skill_id]

    def record_attempt(
        self,
        skill_id: str,
        exercise_id: str,
        is_first_attempt: bool,
        is_correct: bool,
        hints_used: int = 0,
        response_time: float = 0.0,
        was_revealed: bool = False,
        concept_key: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> PromotionResult:
        """
        Record the outcome of an exercise attempt and evaluate promotion/demotion.
        
        Rules:
        - Only clean first attempts (without hints or reveal) count fully toward promotion.
        - Retries help the player learn, but do not artificially inflate first-attempt accuracy.
        - Solutions revealed receive zero credit and are recorded as errors.
        - Promotion requires >= 80% first-attempt accuracy over last 10 attempts across >= 2 variants without excessive hints.
        - Demotion occurs when 4 of the last 5 attempts are failures.
        """
        profile = self.get_profile(skill_id)
        now_str = datetime.now().isoformat()
        profile.last_trained_at = now_str
        profile.total_attempts += 1
        profile.total_response_time += response_time
        profile.total_hints += hints_used

        if is_correct:
            profile.total_solved += 1

        # Evaluate first attempt credit
        clean_first_success = (is_first_attempt and is_correct and not was_revealed and hints_used == 0)

        if is_first_attempt:
            profile.recent_first_attempts.append(clean_first_success)
            profile.recent_hints.append(hints_used)
            profile.recent_exercise_ids.append(exercise_id)

            # Cap recent windows to prevent unbounded memory growth
            if len(profile.recent_first_attempts) > 30:
                profile.recent_first_attempts.pop(0)
                profile.recent_hints.pop(0)
                profile.recent_exercise_ids.pop(0)

            if clean_first_success:
                profile.first_attempt_successes += 1
                if concept_key:
                    profile.mastered_concepts.add(concept_key)
            elif not is_correct or was_revealed:
                if concept_key and concept_key not in profile.recent_mistakes:
                    profile.recent_mistakes.append(concept_key)
                    if len(profile.recent_mistakes) > 5:
                        profile.recent_mistakes.pop(0)

        # Update proficiency score (composite of difficulty and recent accuracy)
        target_prof = (profile.current_difficulty * 10.0) * (profile.recent_accuracy / 100.0 if profile.recent_accuracy > 0 else 0.5)
        profile.proficiency = round(min(100.0, max(0.0, target_prof)), 1)

        # Evaluate Promotion and Demotion
        res = self._evaluate_difficulty_change(profile, session_id=session_id)

        # Save profile
        if self.db_mgr and hasattr(self.db_mgr, "save_skill_profile"):
            try:
                self.db_mgr.save_skill_profile(profile)
            except Exception:
                pass

        return res

    def _evaluate_difficulty_change(self, profile: SkillProfile, session_id: Optional[int] = None) -> PromotionResult:
        """Check promotion or demotion conditions against configurable thresholds."""
        cfg = self.config
        window = profile.recent_first_attempts
        hints = profile.recent_hints
        variants = profile.recent_exercise_ids

        # --- Check Demotion First ---
        # Rule: 4 of the last 5 answers wrong
        if len(window) >= cfg.demotion_window:
            recent_5 = window[-cfg.demotion_window:]
            failures_in_5 = sum(1 for x in recent_5 if not x)
            if failures_in_5 >= cfg.demotion_fail_count:
                if profile.current_difficulty > 1:
                    old_diff = profile.current_difficulty
                    profile.current_difficulty -= 1
                    reason = f"Difficulty reduced temporarily: {failures_in_5} of last {cfg.demotion_window} attempts failed. Reinforcing core understanding."
                    msg = f"Difficulty reduced to {profile.current_difficulty}/10: let's reinforce foundational {profile.name} concepts."

                    # Record event in DB
                    self._record_adaptive_event(profile.skill_id, "demoted", old_diff, profile.current_difficulty, reason, session_id)
                    # Reset recent window slightly to avoid instant re-demotion
                    profile.recent_first_attempts = [True, False]
                    profile.recent_hints = [0, 0]
                    return PromotionResult("demoted", old_diff, profile.current_difficulty, reason, msg)

        # --- Check Promotion ---
        # Rule: At least 8 of the last 10 first attempts correct, across >= 2 variants, without excessive hints
        if len(window) >= cfg.promotion_window:
            recent_10 = window[-cfg.promotion_window:]
            recent_hints_10 = hints[-cfg.promotion_window:]
            recent_variants_10 = set(variants[-cfg.promotion_window:])

            correct_count = sum(1 for x in recent_10 if x)
            acc = correct_count / cfg.promotion_window
            total_hints = sum(recent_hints_10)
            hint_ratio = total_hints / cfg.promotion_window

            if (
                acc >= cfg.promotion_min_accuracy
                and len(recent_variants_10) >= cfg.promotion_min_variants
                and hint_ratio <= cfg.promotion_max_hint_ratio
            ):
                if profile.current_difficulty < 10:
                    old_diff = profile.current_difficulty
                    profile.current_difficulty += 1
                    reason = f"Difficulty increased: {correct_count}/{cfg.promotion_window} correct on first attempt across diverse variants."
                    msg = f"Difficulty increased to {profile.current_difficulty}/10: you consistently solved {profile.name} exercises!"

                    self._record_adaptive_event(profile.skill_id, "promoted", old_diff, profile.current_difficulty, reason, session_id)
                    # Fresh window for the new difficulty level
                    profile.recent_first_attempts = []
                    profile.recent_hints = []
                    profile.recent_exercise_ids = []
                    return PromotionResult("promoted", old_diff, profile.current_difficulty, reason, msg)

        # Maintain difficulty
        return PromotionResult(
            action="maintained",
            old_difficulty=profile.current_difficulty,
            new_difficulty=profile.current_difficulty,
            reason="Performance stable; continuing at current challenge level.",
        )

    def _record_adaptive_event(
        self,
        skill_id: str,
        event_type: str,
        old_diff: int,
        new_diff: int,
        reason: str,
        session_id: Optional[int] = None,
    ) -> None:
        """Record a promotion or demotion event in database."""
        if self.db_mgr and hasattr(self.db_mgr, "record_adaptive_event"):
            try:
                self.db_mgr.record_adaptive_event(
                    skill_id=skill_id,
                    event_type=event_type,
                    old_diff=old_diff,
                    new_diff=new_diff,
                    reason=reason,
                    session_id=session_id,
                )
            except Exception:
                pass

    def reset_all_progress(self) -> None:
        """Reset all skill difficulties to 1 and clear attempt records."""
        for skill_id in self.profiles:
            info = SKILL_DEFINITIONS.get(skill_id, {"name": skill_id})
            self.profiles[skill_id] = SkillProfile(
                skill_id=skill_id,
                name=info["name"],
                current_difficulty=1,
                proficiency=0.0,
            )
        self.save_all_profiles()
        if self.db_mgr and hasattr(self.db_mgr, "reset_adaptive_progress"):
            try:
                self.db_mgr.reset_adaptive_progress()
            except Exception:
                pass


# -----------------------------------------------------------------------------
# Exercise Generation by Skill & Difficulty (Levels 1 to 10)
# -----------------------------------------------------------------------------

def generate_adaptive_exercise(
    skill_id: str,
    difficulty: int = 1,
    exclude_ids: Optional[Set[str]] = None,
) -> BlindfoldExercise:
    """Generate a valid, non-repetitive chess exercise matching skill and difficulty (1-10)."""
    diff = max(1, min(10, difficulty))
    exclude = exclude_ids or set()

    for _ in range(8):  # Re-roll up to 8 times to avoid recent variants
        ex = _dispatch_skill_generator(skill_id, diff)
        if ex.id not in exclude:
            return ex
    return ex


def generate_curriculum_exercise(
    level: int,
    exclude_ids: Optional[Set[str]] = None,
) -> BlindfoldExercise:
    """Generate an exercise matching an ordered curriculum level (1 to 10)."""
    lvl = max(1, min(10, level))
    curr_info = CURRICULUM_LEVELS.get(lvl, CURRICULUM_LEVELS[1])
    skill_id = curr_info["primary_skill"]
    return generate_adaptive_exercise(skill_id, difficulty=lvl, exclude_ids=exclude_ids)


def _dispatch_skill_generator(skill_id: str, difficulty: int) -> BlindfoldExercise:
    """Dispatch to specific generator based on skill and difficulty tier."""
    if skill_id == "coordinates":
        return _gen_coordinates_exercise(difficulty)
    elif skill_id == "square_colors":
        return _gen_square_colors_exercise(difficulty)
    elif skill_id == "piece_movement":
        return _gen_piece_movement_exercise(difficulty)
    elif skill_id == "spatial_relationships":
        return _gen_spatial_relationships_exercise(difficulty)
    elif skill_id == "knight_routes":
        return _gen_knight_routes_exercise(difficulty)
    elif skill_id == "multi_piece":
        return _gen_multi_piece_exercise(difficulty)
    elif skill_id == "position_memory":
        return _gen_position_memory_exercise(difficulty)
    elif skill_id == "move_sequences":
        return _gen_move_sequences_exercise(difficulty)
    elif skill_id == "tactical_calc":
        return _gen_tactical_calc_exercise(difficulty)
    else:
        return _gen_coordinates_exercise(difficulty)


# --- Skill 1: Coordinates ---
def _gen_coordinates_exercise(difficulty: int) -> BlindfoldExercise:
    if difficulty <= 3:
        sq = random.choice(chess.SQUARES)
        name = chess.square_name(sq)
        f_char = name[0].upper()
        r_num = name[1]
        if random.random() < 0.5:
            return BlindfoldExercise(
                id=f"coord_file_{name}",
                stage=1,
                category="coordinate_file",
                title="Coordinate File Identification",
                prompt=f"Which file does the square '{name}' lie on? (e.g. a, b, c...)",
                correct_answers=[name[0], name[0].upper()],
                explanation=f"'{name}' is in the {f_char}-file (column {name[0]}).",
                hint="Look at the first letter of the coordinate.",
                level=difficulty,
            )
        else:
            return BlindfoldExercise(
                id=f"coord_inter_{name}",
                stage=1,
                category="coordinate_intersection",
                title="Coordinate Intersection",
                prompt=f"What square is at the intersection of the {f_char}-file and the {r_num}th rank?",
                correct_answers=[name],
                explanation=f"The intersection of file {f_char} and rank {r_num} is '{name}'.",
                hint="Combine file letter first, followed by the rank digit.",
                level=difficulty,
            )
    elif difficulty <= 6:
        # Orthogonal neighbors or edge detection
        sq = random.choice([chess.E4, chess.D5, chess.C3, chess.F6, chess.B2, chess.G7])
        sq_name = chess.square_name(sq)
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        neighbors = []
        if f > 0: neighbors.append(chess.square_name(chess.square(f - 1, r)))
        if f < 7: neighbors.append(chess.square_name(chess.square(f + 1, r)))
        if r > 0: neighbors.append(chess.square_name(chess.square(f, r - 1)))
        if r < 7: neighbors.append(chess.square_name(chess.square(f, r + 1)))
        neighbors_sorted = sorted(neighbors)
        return BlindfoldExercise(
            id=f"coord_neighbors_{sq_name}",
            stage=1,
            category="coordinate_neighbors",
            title="Orthogonal Neighboring Squares",
            prompt=(
                f"Name the 4 orthogonal neighbors (North, South, East, West) of square '{sq_name}':\n"
                f"(Enter squares separated by spaces or commas, e.g. '{neighbors_sorted[0]} {neighbors_sorted[1]}...')"
            ),
            correct_answers=[" ".join(neighbors_sorted), ", ".join(neighbors_sorted)] + neighbors_sorted,
            expected_square_set=set(chess.parse_square(s) for s in neighbors),
            explanation=f"The orthogonal neighbors of {sq_name} are: {', '.join(neighbors_sorted)}.",
            hint=f"Step 1 square along rank or file from {sq_name}.",
            level=difficulty,
        )
    else:
        # Manhattan distance between squares
        sq1 = random.choice([chess.A1, chess.C2, chess.B1, chess.E1])
        sq2 = random.choice([chess.E4, chess.G7, chess.H8, chess.F5])
        n1, n2 = chess.square_name(sq1), chess.square_name(sq2)
        m_dist = abs(chess.square_file(sq1) - chess.square_file(sq2)) + abs(chess.square_rank(sq1) - chess.square_rank(sq2))
        return BlindfoldExercise(
            id=f"coord_manhattan_{n1}_{n2}",
            stage=1,
            category="coordinate_distance",
            title="Coordinate Manhattan Distance",
            prompt=f"What is the Manhattan distance (|file diff| + |rank diff|) between '{n1}' and '{n2}'?",
            correct_answers=[str(m_dist)],
            explanation=f"Between {n1} and {n2}: file distance is {abs(chess.square_file(sq1) - chess.square_file(sq2))} and rank distance is {abs(chess.square_rank(sq1) - chess.square_rank(sq2))}, totaling {m_dist}.",
            hint="Add the absolute difference in files to the absolute difference in ranks.",
            level=difficulty,
        )


# --- Skill 2: Square Colors ---
def _gen_square_colors_exercise(difficulty: int) -> BlindfoldExercise:
    if difficulty <= 3:
        sq = random.choice(chess.SQUARES)
        name = chess.square_name(sq)
        color = get_square_color(sq)
        return BlindfoldExercise(
            id=f"sq_color_{name}",
            stage=1,
            category="square_color",
            title="Square Color Recognition",
            prompt=f"Is square '{name}' light or dark? (light/dark)",
            correct_answers=[color, color[0]],
            explanation=f"'{name}' is a {color} square (file index {ord(name[0])-ord('a')+1} + rank {name[1]} is {'even' if color=='dark' else 'odd'}).",
            hint="Remember: a1 is dark, h1 is light. Parity of file + rank gives the color.",
            level=difficulty,
        )
    elif difficulty <= 6:
        sq1, sq2 = random.sample([chess.A1, chess.B3, chess.C4, chess.E5, chess.F7, chess.G2, chess.H8, chess.D6], 2)
        n1, n2 = chess.square_name(sq1), chess.square_name(sq2)
        c1, c2 = get_square_color(sq1), get_square_color(sq2)
        same = (c1 == c2)
        ans = "yes" if same else "no"
        return BlindfoldExercise(
            id=f"sq_complex_{n1}_{n2}",
            stage=1,
            category="color_complex",
            title="Color Complex Awareness",
            prompt=f"Are '{n1}' and '{n2}' on the same color complex? (yes/no)",
            correct_answers=[ans, ans[0]],
            explanation=f"{n1} is {c1} and {n2} is {c2}. They are {'on the same color' if same else 'on different colors'}.",
            hint=f"Check if {n1} is light or dark, then check {n2}.",
            level=difficulty,
        )
    else:
        # Long diagonal square color check
        diags = [
            ("a1-h8", "dark", "The long main dark diagonal starts at a1 and ends at h8."),
            ("a8-h1", "light", "The long main light diagonal starts at a8 and ends at h1."),
            ("b1-h7", "light", "The b1-h7 diagonal is light-squared (b1 is light, c2 is light, etc.)."),
            ("c1-h6", "dark", "The c1-h6 diagonal is dark-squared (c1 is dark, d2 is dark, etc.)."),
        ]
        diag_name, color, expl = random.choice(diags)
        return BlindfoldExercise(
            id=f"sq_diag_{diag_name}",
            stage=1,
            category="diagonal_color",
            title="Diagonal Color Parity",
            prompt=f"What color complex is the '{diag_name}' diagonal? (light/dark)",
            correct_answers=[color, color[0]],
            explanation=expl,
            hint="Check the starting square of the diagonal.",
            level=difficulty,
        )


# --- Skill 3: Piece Movement & Legality ---
def _gen_piece_movement_exercise(difficulty: int) -> BlindfoldExercise:
    if difficulty <= 3:
        # Rook or Bishop on empty board
        sq = random.choice([chess.D4, chess.E5, chess.A1, chess.H8])
        sq_name = chess.square_name(sq)
        board = chess.Board(None)
        board.set_piece_at(sq, chess.Piece(chess.ROOK, chess.WHITE))
        dest = sorted(chess.square_name(s) for s in board.attacks(sq))
        return BlindfoldExercise(
            id=f"pm_rook_empty_{sq_name}",
            stage=2,
            category="empty_board_rook",
            title="Empty-Board Rook Reachability",
            prompt=f"On an otherwise empty board, how many squares can a Rook on '{sq_name}' move to?",
            correct_answers=["14", "fourteen"],
            explanation=f"A Rook on any square of an empty board always controls exactly 14 squares (7 on its file + 7 on its rank).",
            hint="Count 7 squares along the file and 7 squares along the rank.",
            level=difficulty,
            is_empty_board=True,
        )
    elif difficulty <= 6:
        # Knight on corner vs center
        sq = random.choice([chess.A1, chess.H1, chess.A8, chess.H8])
        sq_name = chess.square_name(sq)
        board = chess.Board(None)
        board.set_piece_at(sq, chess.Piece(chess.KNIGHT, chess.WHITE))
        dests = sorted(chess.square_name(s) for s in board.attacks(sq))
        return BlindfoldExercise(
            id=f"pm_knight_corner_{sq_name}",
            stage=2,
            category="corner_knight_movement",
            title="Corner Knight Reachability",
            prompt=f"On an empty board: List all legal destination squares for a Knight on '{sq_name}':",
            correct_answers=[" ".join(dests), ", ".join(dests)] + dests,
            expected_square_set=set(chess.parse_square(s) for s in dests),
            explanation=f"A corner Knight on {sq_name} has only 2 legal destinations: {', '.join(dests)}.",
            hint="In the corner, the knight's L-hops are constrained by the board edge.",
            level=difficulty,
            is_empty_board=True,
        )
    else:
        # Pin and legal checks in actual positions
        scenarios = [
            (
                "White: King on e1, Bishop on e2. Black: Rook on e8.\nCan White's Bishop legally move to d3? (yes/no)",
                ["no", "n"],
                "No. The Bishop on e2 is absolutely pinned to the King on e1 by Black's Rook on e8.",
                "Check if moving the Bishop exposes the White King to check.",
                "4r3/8/8/8/8/8/4B3/4K3 w - - 0 1",
            ),
            (
                "White: Pawn on e5. Black: Pawn on d5 (just played d7-d5).\nCan White legally play exd6 en passant? (yes/no)",
                ["yes", "y"],
                "Yes! En passant is legal immediately after an enemy pawn moves two squares forward past an adjacent pawn.",
                "Consider the en passant rule for 5th rank pawns.",
                "rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2",
            ),
            (
                "White: King on e1, Rook on h1. Black: Bishop on a6 attacking f1.\nCan White castle Kingside (O-O)? (yes/no)",
                ["no", "n"],
                "No! A King cannot castle through check. The f1 square is controlled by Black's Bishop on a6.",
                "Castling is forbidden if the King passes through an attacked square.",
                "r3k2r/8/b7/8/8/8/8/R3K2R w KQkq - 0 1",
            ),
        ]
        p, ans, expl, hnt, fen = random.choice(scenarios)
        return BlindfoldExercise(
            id=f"pm_legality_{hash(p)%10000}",
            stage=2,
            category="position_legality",
            title="Legal Move Validation (Pins & Checks)",
            prompt=p,
            correct_answers=ans,
            explanation=expl,
            hint=hnt,
            fen=fen,
            level=difficulty,
        )


# --- Skill 4: Spatial Relationships ---
def _gen_spatial_relationships_exercise(difficulty: int) -> BlindfoldExercise:
    if difficulty <= 3:
        pairs = [
            (chess.C3, chess.F6, "diagonal", "yes"),
            (chess.B2, chess.B7, "file", "yes"),
            (chess.A4, chess.G4, "rank", "yes"),
            (chess.C3, chess.E5, "diagonal", "no"),
            (chess.D2, chess.F5, "straight", "no"),
        ]
        s1, s2, rel_type, ans = random.choice(pairs)
        n1, n2 = chess.square_name(s1), chess.square_name(s2)
        return BlindfoldExercise(
            id=f"spatial_line_{n1}_{n2}",
            stage=3,
            category="spatial_line_sharing",
            title="Line-Sharing Spatial Relationship",
            prompt=f"Do '{n1}' and '{n2}' lie on the same {rel_type}? (yes/no)",
            correct_answers=[ans, ans[0]],
            explanation=f"'{n1}' and '{n2}' {'share' if ans=='yes' else 'do not share'} the same {rel_type}.",
            hint=f"Check the file and rank coordinates of both {n1} and {n2}.",
            level=difficulty,
        )
    elif difficulty <= 6:
        # Chebyshev / King distance estimation
        s1, s2 = random.choice([
            (chess.A1, chess.D4, 3),
            (chess.E2, chess.E7, 5),
            (chess.B3, chess.G8, 5),
            (chess.C2, chess.H2, 5),
            (chess.D4, chess.D6, 2),
        ])
        n1, n2 = chess.square_name(s1), chess.square_name(s2)
        cheb = max(abs(chess.square_file(s1) - chess.square_file(s2)), abs(chess.square_rank(s1) - chess.square_rank(s2)))
        return BlindfoldExercise(
            id=f"spatial_king_dist_{n1}_{n2}",
            stage=3,
            category="king_distance",
            title="Chebyshev (King Move) Distance",
            prompt=f"What is the minimum number of King moves to travel from '{n1}' to '{n2}' on an empty board?",
            correct_answers=[str(cheb)],
            explanation=f"King distance is max(|file diff|, |rank diff|). Between {n1} and {n2}, it is max({abs(chess.square_file(s1)-chess.square_file(s2))}, {abs(chess.square_rank(s1)-chess.square_rank(s2))}) = {cheb}.",
            hint="A King can move 1 square in any direction (orthogonal or diagonal).",
            level=difficulty,
        )
    else:
        # Collinear square between two squares
        lines = [
            (chess.C3, chess.G7, chess.E5, "Between c3 and g7 on the main diagonal, e5 is the exact midpoint."),
            (chess.B2, chess.F6, chess.D4, "Between b2 and f6, d4 is the exact midpoint square."),
            (chess.D1, chess.D7, chess.D4, "On the d-file between d1 and d7, d4 is the midpoint square."),
        ]
        s1, s2, mid, expl = random.choice(lines)
        n1, n2, n_mid = chess.square_name(s1), chess.square_name(s2), chess.square_name(mid)
        return BlindfoldExercise(
            id=f"spatial_midpoint_{n1}_{n2}",
            stage=3,
            category="spatial_midpoint",
            title="Collinear Midpoint Calculation",
            prompt=f"Which square lies directly at the midpoint between '{n1}' and '{n2}'?",
            correct_answers=[n_mid],
            explanation=expl,
            hint="Average the file letters and rank numbers.",
            level=difficulty,
        )


# --- Skill 5: Knight Routes ---
def _gen_knight_routes_exercise(difficulty: int) -> BlindfoldExercise:
    if difficulty <= 3:
        # 1-move knight reachability
        sq = random.choice([chess.C3, chess.F3, chess.D4, chess.E5])
        sq_name = chess.square_name(sq)
        board = chess.Board(None)
        board.set_piece_at(sq, chess.Piece(chess.KNIGHT, chess.WHITE))
        dests = sorted(chess.square_name(s) for s in board.attacks(sq))
        target = random.choice(dests)
        return BlindfoldExercise(
            id=f"knight_1hop_{sq_name}_{target}",
            stage=4,
            category="knight_1hop",
            title="Knight One-Move Reachability",
            prompt=f"Can a Knight on '{sq_name}' reach '{target}' in exactly 1 legal leap? (yes/no)",
            correct_answers=["yes", "y"],
            explanation=f"Yes, {target} is one of the legal L-hop destinations for a knight on {sq_name}.",
            hint="Check if the file and rank differences are (1,2) or (2,1).",
            level=difficulty,
        )
    elif difficulty <= 6:
        # 2-hop route with verified intermediates
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
        ]
        start_sq, dest_sq = random.choice(sample_pairs)
        dist, paths = shortest_knight_path(start_sq, dest_sq)
        valid_intermediates = sorted(set(chess.square_name(p[1]) for p in paths if len(p) == 3))
        s_name, d_name = chess.square_name(start_sq), chess.square_name(dest_sq)
        example_str = f" (e.g. '{valid_intermediates[0]}')" if valid_intermediates else ""
        return BlindfoldExercise(
            id=f"knight_2hop_{s_name}_{d_name}",
            stage=4,
            category="knight_2hop_route",
            title="Knight Two-Move Route",
            prompt=(
                f"A Knight starts on '{s_name}' and reaches '{d_name}' in exactly 2 moves.\n"
                f"Name a valid intermediate square{example_str}:"
            ),
            correct_answers=valid_intermediates,
            explanation=f"Valid intermediate squares between {s_name} and {d_name} are: {', '.join(valid_intermediates)}.",
            hint="Visualize knight hops from the start that can also leap into the destination.",
            level=difficulty,
        )
    else:
        # 3-move route or obstacle navigation
        s_name, d_name = "g7", "c4"
        dist, paths = shortest_knight_path(chess.G7, chess.C4)
        return BlindfoldExercise(
            id=f"knight_shortest_dist_{s_name}_{d_name}",
            stage=5,
            category="knight_shortest_distance",
            title="Shortest Knight Path Distance",
            prompt=f"What is the minimum number of knight moves needed to travel from '{s_name}' to '{d_name}' on an empty board?",
            correct_answers=["3", "three"],
            explanation="g7 (dark) to c4 (light) changes color complex, requiring an odd move count (minimum 3 hops: g7-f5-e3-c4).",
            hint="Note the color parity of g7 and c4. Opposite colors require an odd number of moves.",
            level=difficulty,
        )


# --- Skill 6: Multi-Piece Visualization ---
def _gen_multi_piece_exercise(difficulty: int) -> BlindfoldExercise:
    scenarios = [
        (
            "White: King on g1, Pawns on f2, g2, h2. Black: Rook on a1.\nIs the White King in check? (yes/no)",
            ["yes", "y"],
            "Yes! The 1st rank is open between a1 and g1, delivering back-rank check.",
            "Verify whether any piece or pawn obstructs the 1st rank.",
            "6k1/8/8/8/8/8/5PPP/r5K1 w - - 0 1",
        ),
        (
            "White: Bishop on c4, Knight on f3. Black: Pawn on d5.\nHow many White pieces attack the d5 pawn? (0, 1, or 2)",
            ["2", "two"],
            "Both White pieces attack d5: Bishop on c4 along the a2-g8 diagonal, and Knight on f3 via its L-hop.",
            "Calculate lines of attack from c4 and f3 to d5.",
            "rnbqkbnr/ppp1pppp/8/3p4/2B5/5N2/PPPPPPPP/RNBQK2R w KQkq - 0 1",
        ),
        (
            "White: King on e1, Bishop on b5. Black: King on e8, Knight on c6.\nIs Black's Knight on c6 pinned to the King? (yes/no)",
            ["no", "n"],
            "No. From b5 to e8 is not a clean diagonal (b5-c6-d7-e8 is diagonal, but Black has d7). On b5-c6, d7 is intervening! Black is not in check, so knight is not absolutely pinned.",
            "Check if e8 and b5 share a continuous unobstructed diagonal through c6.",
            "r1bqk2r/pppppppp/2n5/1B6/8/8/PPPPPPPP/RNBQK2R w KQkq - 0 1",
        ),
    ]
    p, ans, expl, hnt, fen = random.choice(scenarios)
    return BlindfoldExercise(
        id=f"multi_piece_{hash(p)%10000}",
        stage=6,
        category="multi_piece_sight",
        title="Multi-Piece Line of Sight",
        prompt=p,
        correct_answers=ans,
        explanation=expl,
        hint=hnt,
        fen=fen,
        level=difficulty,
    )


# --- Skill 7: Position Memory ---
def _gen_position_memory_exercise(difficulty: int) -> BlindfoldExercise:
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
            "expl": "Black's Queen is on a5, creating an active pin along the 5th rank.",
            "hint": "Recall the major Black piece on the queenside a-file.",
            "fen": "5rk1/8/4pn2/q5B1/3P4/8/8/3R2K1 w - - 0 1",
        },
    ]
    sel = random.choice(positions)
    return BlindfoldExercise(
        id=f"pos_mem_{hash(sel['q'])%10000}",
        stage=7,
        category="board_reconstruction",
        title="Mental Board Reconstruction",
        prompt=sel["q"],
        correct_answers=sel["ans"],
        explanation=sel["expl"],
        hint=sel["hint"],
        initial_board_description=sel["desc"],
        fen=sel["fen"],
        level=difficulty,
    )


# --- Skill 8: Move Sequences ---
def _gen_move_sequences_exercise(difficulty: int) -> BlindfoldExercise:
    sequences = [
        (
            ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6"],
            "Where is White's light-squared bishop located?",
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
            "Which square is White's King's Knight on?",
            ["d4"],
            "White's knight moved g1 -> f3 -> d4 (recapturing the pawn).",
            "Recall White's recapture on move 4 in the Open Sicilian.",
        ),
    ]
    seq, prompt, answers, expl, hnt = random.choice(sequences)
    return BlindfoldExercise(
        id=f"move_seq_{seq[0]}_{seq[-1]}",
        stage=8,
        category="sequence_tracking",
        title="Mental Move-Sequence Tracking",
        prompt=(
            f"Mentally visualize this move sequence from the starting position:\n"
            f"Moves: {' '.join(seq)}\n\n"
            f"Question: {prompt}"
        ),
        correct_answers=answers,
        explanation=expl,
        hint=hnt,
        moves_sequence=seq,
        level=difficulty,
    )


# --- Skill 9: Tactical Visualization ---
def _gen_tactical_calc_exercise(difficulty: int) -> BlindfoldExercise:
    tactics = [
        (
            "White: King on h1, Queen on f3, Knight on e5.\n"
            "Black: King on h8, Queen on e7, Pawn on f7.\n"
            "White plays 1. Qxf7! If Black replies 1... Qxf7, what is White's checkmate move?",
            ["ng6#", "ng6", "nxf7#"],
            "1... Qxf7 is answered by 2. Ng6# delivering smothered checkmate with the knight!",
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
    ]
    p, ans, expl, hnt, fen = random.choice(tactics)
    return BlindfoldExercise(
        id=f"tactical_calc_{hash(p)%10000}",
        stage=9,
        category="blindfold_tactic",
        title="Blindfold Tactical Calculation",
        prompt=p,
        correct_answers=ans,
        explanation=expl,
        hint=hnt,
        fen=fen,
        level=difficulty,
    )
