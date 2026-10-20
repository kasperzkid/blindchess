"""Active training and game session management."""

from datetime import datetime
import time
from typing import Optional

from blindchess.board_state import BoardState
from blindchess.persistence import DatabaseManager


class ActiveSession:
    """Tracks state, timing, and metrics for an in-progress training session."""

    def __init__(self, mode: str, level: int, db_mgr: Optional[DatabaseManager] = None):
        self.mode = mode
        self.level = level
        self.db_mgr = db_mgr
        self.start_time = time.time()
        self.session_id: Optional[int] = None

        if self.db_mgr:
            self.session_id = self.db_mgr.record_session_start(mode, level)

        self.board_state = BoardState()
        self.hints_count: int = 0
        self.notes: str = ""

    def record_hint(self) -> None:
        """Increment count of hints requested by user."""
        self.hints_count += 1

    def record_reveal(self) -> None:
        """Increment count of board reveals."""
        self.board_state.record_reveal()

    @property
    def duration_seconds(self) -> float:
        """Return total elapsed time in seconds."""
        return time.time() - self.start_time

    def close(self, result: Optional[str] = None, notes: Optional[str] = None) -> None:
        """Conclude session and persist final summary to database."""
        if self.db_mgr and self.session_id is not None:
            self.db_mgr.record_session_end(
                session_id=self.session_id,
                duration_sec=self.duration_seconds,
                moves_count=len(self.board_state.history),
                reveals_count=self.board_state.reveal_count,
                hints_count=self.hints_count,
                result=result,
                notes=notes or self.notes,
            )
