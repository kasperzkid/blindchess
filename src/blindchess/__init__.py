"""BlindChess: A Local-First Linux Blindfold Chess, Strategic Thinking, and Variation Training System."""

__version__ = "1.0.0"
__author__ = "BlindChess Contributors"

from blindchess.board_state import BoardState
from blindchess.config import AppConfig
from blindchess.engine_manager import EngineManager
from blindchess.errors import BlindChessError

__all__ = [
    "BoardState",
    "AppConfig",
    "EngineManager",
    "BlindChessError",
]
