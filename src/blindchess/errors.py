"""Custom exception classes for BlindChess."""

from typing import Optional


class BlindChessError(Exception):
    """Base exception for all BlindChess application errors."""

    def __init__(self, message: str, actionable_hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.actionable_hint = actionable_hint

    def __str__(self) -> str:
        if self.actionable_hint:
            return f"{self.message}\nHint: {self.actionable_hint}"
        return self.message


class InvalidMoveError(BlindChessError):
    """Raised when a move is illegal or cannot be parsed."""
    pass


class AmbiguousMoveError(BlindChessError):
    """Raised when a move notation is ambiguous."""
    pass


class EngineNotFoundError(BlindChessError):
    """Raised when Stockfish or the specified UCI engine cannot be located."""
    pass


class EngineCommunicationError(BlindChessError):
    """Raised when communicating with the UCI engine fails or crashes."""
    pass


class PositionError(BlindChessError):
    """Raised when a FEN or board configuration is invalid."""
    pass


class PGNError(BlindChessError):
    """Raised when reading, parsing, or exporting PGN data fails."""
    pass


class PersistenceError(BlindChessError):
    """Raised when SQLite operations or file saving encounters an error."""
    pass


class ConfigurationError(BlindChessError):
    """Raised when settings or configuration parameters are invalid."""
    pass
