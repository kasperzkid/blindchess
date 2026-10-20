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

        # Performance indices
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_mode ON sessions(mode);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tactics_theme ON tactical_results(theme);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calc_session ON calculation_drills(session_id);")

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
            self.conn.execute("DELETE FROM sessions;")
