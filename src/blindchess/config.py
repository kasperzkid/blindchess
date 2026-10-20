"""Configuration management for BlindChess."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from blindchess.errors import ConfigurationError
from blindchess.paths import get_default_config_path

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """User-configurable settings for BlindChess."""

    engine_path: Optional[str] = None
    default_opponent_level: str = "intermediate"
    board_visibility: str = "hidden"  # "hidden", "manual_reveal", "after_move", "normal"
    strict_blindfold: bool = False
    ascii_only: bool = False
    engine_threads: int = 1
    engine_hash_mb: int = 64
    analysis_depth: int = 15
    analysis_time_limit: float = 2.0
    multipv: int = 3
    tablebase_path: Optional[str] = None
    adaptive_difficulty: bool = True
    training_level: int = 1  # 1 to 6
    user_side: str = "white"

    def validate(self) -> None:
        """Validate configuration parameters."""
        valid_visibilities = {"hidden", "manual_reveal", "after_move", "normal"}
        if self.board_visibility not in valid_visibilities:
            raise ConfigurationError(
                f"Invalid board_visibility: {self.board_visibility}. "
                f"Expected one of: {', '.join(sorted(valid_visibilities))}"
            )

        valid_levels = {"beginner", "casual", "intermediate", "advanced", "expert", "full_strength", "custom"}
        if self.default_opponent_level.lower() not in valid_levels:
            raise ConfigurationError(
                f"Invalid default_opponent_level: {self.default_opponent_level}. "
                f"Expected one of: {', '.join(sorted(valid_levels))}"
            )

        if self.engine_threads < 1 or self.engine_threads > 128:
            raise ConfigurationError(f"engine_threads must be between 1 and 128 (got {self.engine_threads})")

        if self.engine_hash_mb < 4 or self.engine_hash_mb > 32768:
            raise ConfigurationError(f"engine_hash_mb must be between 4 and 32768 (got {self.engine_hash_mb})")

        if self.analysis_depth < 1 or self.analysis_depth > 100:
            raise ConfigurationError(f"analysis_depth must be between 1 and 100 (got {self.analysis_depth})")

        if self.analysis_time_limit <= 0 or self.analysis_time_limit > 300:
            raise ConfigurationError(
                f"analysis_time_limit must be between 0.1 and 300 seconds (got {self.analysis_time_limit})"
            )

        if self.multipv < 1 or self.multipv > 20:
            raise ConfigurationError(f"multipv must be between 1 and 20 (got {self.multipv})")

        if self.training_level < 1 or self.training_level > 6:
            raise ConfigurationError(f"training_level must be between 1 and 6 (got {self.training_level})")

        if self.user_side.lower() not in {"white", "black", "random"}:
            raise ConfigurationError(f"user_side must be 'white', 'black', or 'random' (got {self.user_side})")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        """Create AppConfig from dictionary, ignoring unknown keys for forward compatibility."""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        config = cls(**filtered)
        config.validate()
        return config


def load_config(config_file: Optional[Path] = None) -> AppConfig:
    """Load configuration from file or create defaults if it does not exist."""
    path = config_file or get_default_config_path()
    if not path.is_file():
        config = AppConfig()
        save_config(config, path)
        return config

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppConfig.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to read config from {path}: {e}. Falling back to default settings.")
        return AppConfig()


def save_config(config: AppConfig, config_file: Optional[Path] = None) -> None:
    """Save configuration safely to disk (atomic write)."""
    config.validate()
    path = config_file or get_default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, indent=2)
    temp_path.replace(path)
