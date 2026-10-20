"""SQLite database schema, data persistence, backups, and migration subsystem."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional

from blindchess.errors import PersistenceError
from blindchess.paths import get_backup_dir, get_default_db_path

CURRENT_SCHEMA_VERSION = 1


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create and return a configured SQLite connection."""
    path = db_path or get_default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn
    except sqlite3.Error as e:
        raise PersistenceError(f"Failed to connect to database at {path}: {e}") from e


def initialize_database(conn: sqlite3.Connection) -> None:
    """Create schema tables and indices if they do not exist."""
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_meta (
                version INTEGER PRIMARY KEY,
                updated_at TEXT NOT NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                mode TEXT NOT NULL,
                training_level INTEGER NOT NULL,
                duration_seconds REAL DEFAULT 0,
                moves_count INTEGER DEFAULT 0,
                reveals_count INTEGER DEFAULT 0,
                hints_count INTEGER DEFAULT 0,
                result TEXT,
                notes TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS calculation_drills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                created_at TEXT NOT NULL,
                fen TEXT NOT NULL,
                candidate_san TEXT NOT NULL,
                predicted_replies TEXT,
                user_eval TEXT,
                engine_best_san TEXT,
                is_engine_top INTEGER DEFAULT 0,
                accuracy_score REAL DEFAULT 0,
                missed_resources TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS tactical_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                created_at TEXT NOT NULL,
                puzzle_id TEXT NOT NULL,
                theme TEXT,
                solved INTEGER NOT NULL,
                hints_used INTEGER DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                date TEXT NOT NULL,
                white TEXT NOT NULL,
                black TEXT NOT NULL,
                result TEXT NOT NULL,
                pgn_content TEXT NOT NULL,
                fen_start TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS spatial_drills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                created_at TEXT NOT NULL,
                stage INTEGER NOT NULL,
                stage_name TEXT NOT NULL,
                category TEXT NOT NULL,
                exercise_id TEXT NOT NULL,
                solved INTEGER NOT NULL,
                attempts INTEGER DEFAULT 1,
                hints_used INTEGER DEFAULT 0,
                response_time_seconds REAL DEFAULT 0,
                user_answer TEXT,
                error_reason TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS spatial_stage_mastery (
                stage INTEGER PRIMARY KEY,
                stage_name TEXT NOT NULL,
                unlocked INTEGER DEFAULT 1,
                completed INTEGER DEFAULT 0,
                total_attempted INTEGER DEFAULT 0,
                total_solved INTEGER DEFAULT 0,
                best_accuracy REAL DEFAULT 0,
                last_trained_at TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_skill_profiles (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                current_difficulty INTEGER DEFAULT 1,
                proficiency REAL DEFAULT 0.0,
                total_attempts INTEGER DEFAULT 0,
                first_attempt_successes INTEGER DEFAULT 0,
                total_solved INTEGER DEFAULT 0,
                total_hints INTEGER DEFAULT 0,
                total_response_time REAL DEFAULT 0.0,
                recent_history_json TEXT DEFAULT '[]',
                mastered_concepts_json TEXT DEFAULT '[]',
                last_trained_at TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                created_at TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                old_difficulty INTEGER,
                new_difficulty INTEGER,
                reason TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS adaptive_spaced_repetition (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                concept_key TEXT NOT NULL,
                due_at TEXT NOT NULL,
                interval_days INTEGER DEFAULT 1,
                repetitions INTEGER DEFAULT 0,
                UNIQUE(skill_id, concept_key)
            );
        """)

        # Performance indices
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_mode ON sessions(mode);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tactics_theme ON tactical_results(theme);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calc_session ON calculation_drills(session_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spatial_stage ON spatial_drills(stage);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_spatial_category ON spatial_drills(category);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_adaptive_skill ON adaptive_skill_profiles(skill_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_adaptive_events ON adaptive_events(skill_id);")

        # Initialize default stages in spatial_stage_mastery if empty
        cur = conn.execute("SELECT COUNT(*) FROM spatial_stage_mastery;")
        if cur.fetchone()[0] == 0:
            default_stages = [
                (1, "Coordinates & Colors", 1),
                (2, "Piece Movement & Legal Targets", 0),
                (3, "Knight Movement & Routes", 0),
                (4, "Multi-Piece Spatial Visualization", 0),
                (5, "Position Memory & Reconstruction", 0),
                (6, "Move-Sequence Tracking", 0),
                (7, "Blindfold Tactical Calculation", 0),
            ]
            for st, name, unl in default_stages:
                conn.execute(
                    """INSERT INTO spatial_stage_mastery
                       (stage, stage_name, unlocked, completed, total_attempted, total_solved, best_accuracy, last_trained_at)
                       VALUES (?, ?, ?, 0, 0, 0, 0.0, ?)""",
                    (st, name, unl, datetime.now().isoformat()),
                )

        # Set version if not present
        cur = conn.execute("SELECT version FROM schema_meta WHERE version = ?", (CURRENT_SCHEMA_VERSION,))
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO schema_meta (version, updated_at) VALUES (?, ?)",
                (CURRENT_SCHEMA_VERSION, datetime.now().isoformat()),
            )


class DatabaseManager:
    """High-level persistence manager for training data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_default_db_path()
        self.conn = get_db_connection(self.db_path)
        initialize_database(self.conn)

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass

    def record_session_start(self, mode: str, level: int) -> int:
        """Insert new session record and return session ID."""
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO sessions (start_time, mode, training_level)
                   VALUES (?, ?, ?)""",
                (datetime.now().isoformat(), mode, level),
            )
            return cur.lastrowid  # type: ignore

    def record_session_end(
        self,
        session_id: int,
        duration_sec: float,
        moves_count: int,
        reveals_count: int,
        hints_count: int,
        result: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """Update session record with end time, stats, and outcome."""
        with self.conn:
            self.conn.execute(
                """UPDATE sessions
                   SET end_time = ?, duration_seconds = ?, moves_count = ?,
                       reveals_count = ?, hints_count = ?, result = ?, notes = ?
                   WHERE id = ?""",
                (
                    datetime.now().isoformat(),
                    duration_sec,
                    moves_count,
                    reveals_count,
                    hints_count,
                    result,
                    notes,
                    session_id,
                ),
            )

    def record_tactical_result(
        self, session_id: Optional[int], puzzle_id: str, theme: str, solved: bool, hints_used: int
    ) -> None:
        """Save result of a tactical drill."""
        with self.conn:
            self.conn.execute(
                """INSERT INTO tactical_results (session_id, created_at, puzzle_id, theme, solved, hints_used)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    datetime.now().isoformat(),
                    puzzle_id,
                    theme,
                    1 if solved else 0,
                    hints_used,
                ),
            )

    def record_calculation_drill(
        self,
        session_id: Optional[int],
        fen: str,
        candidate_san: str,
        predicted_replies: List[str],
        user_eval: Optional[str],
        engine_best_san: Optional[str],
        is_engine_top: bool,
        accuracy_score: float,
        missed_resources: List[str],
    ) -> None:
        """Save a calculation training attempt."""
        with self.conn:
            self.conn.execute(
                """INSERT INTO calculation_drills
                   (session_id, created_at, fen, candidate_san, predicted_replies, user_eval,
                    engine_best_san, is_engine_top, accuracy_score, missed_resources)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    datetime.now().isoformat(),
                    fen,
                    candidate_san,
                    json.dumps(predicted_replies),
                    user_eval,
                    engine_best_san,
                    1 if is_engine_top else 0,
                    accuracy_score,
                    json.dumps(missed_resources),
                ),
            )

    def save_game(
        self,
        pgn_text: str,
        white: str,
        black: str,
        result: str,
        session_id: Optional[int] = None,
        fen_start: Optional[str] = None,
    ) -> int:
        """Save a completed game into the database."""
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO saved_games (session_id, date, white, black, result, pgn_content, fen_start)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    datetime.now().isoformat(),
                    white,
                    black,
                    result,
                    pgn_text,
                    fen_start,
                ),
            )
            return cur.lastrowid  # type: ignore

    def record_spatial_drill(
        self,
        session_id: Optional[int],
        stage: int,
        stage_name: str,
        category: str,
        exercise_id: str,
        solved: bool,
        attempts: int = 1,
        hints_used: int = 0,
        response_time_seconds: float = 0.0,
        user_answer: Optional[str] = None,
        error_reason: Optional[str] = None,
    ) -> None:
        """Record the attempt and outcome of a spatial memory drill."""
        with self.conn:
            self.conn.execute(
                """INSERT INTO spatial_drills
                   (session_id, created_at, stage, stage_name, category, exercise_id,
                    solved, attempts, hints_used, response_time_seconds, user_answer, error_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    datetime.now().isoformat(),
                    stage,
                    stage_name,
                    category,
                    exercise_id,
                    1 if solved else 0,
                    attempts,
                    hints_used,
                    response_time_seconds,
                    user_answer,
                    error_reason,
                ),
            )

    def get_all_spatial_stage_mastery(self) -> List[Dict[str, Any]]:
        """Retrieve progress and mastery statistics for all 7 blindfold stages."""
        cur = self.conn.execute("""
            SELECT stage, stage_name, unlocked, completed, total_attempted, total_solved,
                   best_accuracy, last_trained_at
            FROM spatial_stage_mastery
            ORDER BY stage ASC;
        """)
        results = []
        for row in cur.fetchall():
            results.append({
                "stage": row["stage"],
                "stage_name": row["stage_name"],
                "unlocked": bool(row["unlocked"]),
                "completed": bool(row["completed"]),
                "total_attempted": row["total_attempted"],
                "total_solved": row["total_solved"],
                "best_accuracy": row["best_accuracy"],
                "last_trained_at": row["last_trained_at"],
            })
        return results

    def update_spatial_stage_mastery(
        self,
        stage: int,
        stage_name: str,
        solved_count: int,
        attempted_count: int,
        session_accuracy: float,
    ) -> None:
        """Update mastery status and unlock subsequent stages upon mastery (>=80% accuracy)."""
        now = datetime.now().isoformat()
        is_completed = 1 if (session_accuracy >= 80.0 and attempted_count >= 5) else 0

        with self.conn:
            # Update current stage
            self.conn.execute(
                """UPDATE spatial_stage_mastery
                   SET total_attempted = total_attempted + ?,
                       total_solved = total_solved + ?,
                       best_accuracy = MAX(best_accuracy, ?),
                       completed = CASE WHEN completed = 1 THEN 1 ELSE ? END,
                       last_trained_at = ?
                   WHERE stage = ?""",
                (attempted_count, solved_count, session_accuracy, is_completed, now, stage),
            )

            # If completed, unlock next stage
            if is_completed and stage < 7:
                self.conn.execute(
                    """UPDATE spatial_stage_mastery
                       SET unlocked = 1
                       WHERE stage = ?""",
                    (stage + 1,),
                )

    def get_recurring_spatial_errors(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve categories where user has the highest error rates."""
        cur = self.conn.execute("""
            SELECT category, stage, stage_name,
                   COUNT(*) as total_attempts,
                   SUM(CASE WHEN solved = 0 THEN 1 ELSE 0 END) as failed_attempts,
                   ROUND(AVG(response_time_seconds), 1) as avg_time
            FROM spatial_drills
            GROUP BY category
            HAVING failed_attempts > 0
            ORDER BY failed_attempts DESC, total_attempts DESC
            LIMIT ?;
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

    def backup_database(self, custom_path: Optional[Path] = None) -> Path:
        """Create a timestamped SQLite database backup file."""
        backup_dir = get_backup_dir() if custom_path is None else custom_path.parent
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target_path = custom_path or (backup_dir / f"blindchess_backup_{timestamp}.db")
        target_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(str(target_path)) as bck_conn:
            self.conn.backup(bck_conn)
        return target_path

    def clear_all_history(self) -> None:
        """Safely clear user training tables."""
        with self.conn:
            self.conn.execute("DELETE FROM saved_games;")
            self.conn.execute("DELETE FROM tactical_results;")
            self.conn.execute("DELETE FROM calculation_drills;")
            self.conn.execute("DELETE FROM spatial_drills;")
            self.conn.execute("""
                UPDATE spatial_stage_mastery
                SET completed = 0, total_attempted = 0, total_solved = 0, best_accuracy = 0.0,
                    unlocked = CASE WHEN stage = 1 THEN 1 ELSE 0 END;
            """)
            self.conn.execute("DELETE FROM adaptive_events;")
            self.conn.execute("DELETE FROM adaptive_spaced_repetition;")
            self.conn.execute("DELETE FROM adaptive_skill_profiles;")
            self.conn.execute("DELETE FROM sessions;")

    def save_skill_profile(self, profile: Any) -> None:
        """Persist or update an adaptive skill profile."""
        recent_data = {
            "first_attempts": getattr(profile, "recent_first_attempts", []),
            "hints": getattr(profile, "recent_hints", []),
            "exercise_ids": getattr(profile, "recent_exercise_ids", []),
            "mistakes": getattr(profile, "recent_mistakes", []),
        }
        recent_json = json.dumps(recent_data)
        mastered_list = list(getattr(profile, "mastered_concepts", set()))
        mastered_json = json.dumps(mastered_list)

        with self.conn:
            self.conn.execute(
                """INSERT INTO adaptive_skill_profiles
                   (skill_id, name, current_difficulty, proficiency, total_attempts,
                    first_attempt_successes, total_solved, total_hints, total_response_time,
                    recent_history_json, mastered_concepts_json, last_trained_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(skill_id) DO UPDATE SET
                    name = excluded.name,
                    current_difficulty = excluded.current_difficulty,
                    proficiency = excluded.proficiency,
                    total_attempts = excluded.total_attempts,
                    first_attempt_successes = excluded.first_attempt_successes,
                    total_solved = excluded.total_solved,
                    total_hints = excluded.total_hints,
                    total_response_time = excluded.total_response_time,
                    recent_history_json = excluded.recent_history_json,
                    mastered_concepts_json = excluded.mastered_concepts_json,
                    last_trained_at = excluded.last_trained_at;
                """,
                (
                    profile.skill_id,
                    profile.name,
                    profile.current_difficulty,
                    profile.proficiency,
                    profile.total_attempts,
                    profile.first_attempt_successes,
                    profile.total_solved,
                    profile.total_hints,
                    profile.total_response_time,
                    recent_json,
                    mastered_json,
                    profile.last_trained_at or datetime.now().isoformat(),
                ),
            )

    def get_skill_profile(self, skill_id: str) -> Optional[Any]:
        """Load skill profile from database with graceful corruption recovery."""
        from blindchess.adaptive import SkillProfile
        cur = self.conn.execute(
            """SELECT skill_id, name, current_difficulty, proficiency, total_attempts,
                      first_attempt_successes, total_solved, total_hints, total_response_time,
                      recent_history_json, mastered_concepts_json, last_trained_at
               FROM adaptive_skill_profiles
               WHERE skill_id = ?;""",
            (skill_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        recent_first = []
        recent_hints = []
        recent_ids = []
        recent_mistakes = []
        try:
            r_data = json.loads(row["recent_history_json"] or "{}")
            if isinstance(r_data, dict):
                recent_first = r_data.get("first_attempts", [])
                recent_hints = r_data.get("hints", [])
                recent_ids = r_data.get("exercise_ids", [])
                recent_mistakes = r_data.get("mistakes", [])
            elif isinstance(r_data, list):
                recent_first = r_data
        except Exception:
            pass

        mastered = set()
        try:
            m_list = json.loads(row["mastered_concepts_json"] or "[]")
            if isinstance(m_list, list):
                mastered = set(m_list)
        except Exception:
            pass

        return SkillProfile(
            skill_id=row["skill_id"],
            name=row["name"],
            current_difficulty=row["current_difficulty"],
            proficiency=row["proficiency"],
            total_attempts=row["total_attempts"],
            first_attempt_successes=row["first_attempt_successes"],
            total_solved=row["total_solved"],
            total_hints=row["total_hints"],
            total_response_time=row["total_response_time"],
            recent_first_attempts=recent_first,
            recent_hints=recent_hints,
            recent_exercise_ids=recent_ids,
            recent_mistakes=recent_mistakes,
            mastered_concepts=mastered,
            last_trained_at=row["last_trained_at"],
        )

    def get_all_skill_profiles(self) -> Dict[str, Any]:
        """Retrieve all adaptive skill profiles."""
        cur = self.conn.execute("SELECT skill_id FROM adaptive_skill_profiles;")
        profiles = {}
        for row in cur.fetchall():
            p = self.get_skill_profile(row["skill_id"])
            if p:
                profiles[p.skill_id] = p
        return profiles

    def record_adaptive_event(
        self,
        skill_id: str,
        event_type: str,
        old_diff: int,
        new_diff: int,
        reason: str,
        session_id: Optional[int] = None,
    ) -> None:
        """Log a promotion or demotion event."""
        with self.conn:
            self.conn.execute(
                """INSERT INTO adaptive_events
                   (session_id, created_at, skill_id, event_type, old_difficulty, new_difficulty, reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, datetime.now().isoformat(), skill_id, event_type, old_diff, new_diff, reason),
            )

    def get_adaptive_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve recent promotion/demotion events."""
        cur = self.conn.execute("""
            SELECT id, session_id, created_at, skill_id, event_type, old_difficulty, new_difficulty, reason
            FROM adaptive_events
            ORDER BY id DESC
            LIMIT ?;
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

    def reset_adaptive_progress(self) -> None:
        """Reset all adaptive skill ratings back to Level 1 and wipe adaptive history."""
        with self.conn:
            self.conn.execute("DELETE FROM adaptive_events;")
            self.conn.execute("DELETE FROM adaptive_spaced_repetition;")
            self.conn.execute("""
                UPDATE adaptive_skill_profiles
                SET current_difficulty = 1,
                    proficiency = 0.0,
                    total_attempts = 0,
                    first_attempt_successes = 0,
                    total_solved = 0,
                    total_hints = 0,
                    total_response_time = 0.0,
                    recent_history_json = '[]',
                    mastered_concepts_json = '[]';
            """)
