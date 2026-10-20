"""Stockfish UCI engine discovery, lifecycle, and process management."""

import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
import chess
import chess.engine

from blindchess.config import AppConfig
from blindchess.engine_profiles import EngineProfile, get_profile
from blindchess.errors import EngineCommunicationError, EngineNotFoundError

logger = logging.getLogger(__name__)

COMMON_STOCKFISH_PATHS = [
    Path.home() / ".local" / "bin" / "stockfish",
    Path("/usr/bin/stockfish"),
    Path("/usr/games/stockfish"),
    Path("/usr/local/bin/stockfish"),
    Path("/opt/stockfish/stockfish"),
    Path("/var/lib/snapd/snap/bin/stockfish"),
    Path("/nix/var/nix/profiles/default/bin/stockfish"),
]


def find_stockfish_binary(explicit_path: Optional[str] = None, config: Optional[AppConfig] = None) -> Optional[Path]:
    """Discover Stockfish executable following priority order.

    If an explicit path is provided, it is strictly tested and returned only
    if valid (does not silently fall back to other paths).
    """
    # 1. Explicit path parameter
    if explicit_path:
        p = Path(explicit_path).expanduser().resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return p
        return None

    # 2. Configured path in settings
    if config and config.engine_path:
        p = Path(config.engine_path).expanduser().resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return p
        return None

    # 3. Environment variable STOCKFISH_PATH
    env_path = os.environ.get("STOCKFISH_PATH")
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return p

    # 4. PATH lookup
    which_path = shutil.which("stockfish")
    if which_path:
        p = Path(which_path).resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return p

    # 5. Common standard Linux locations
    for candidate in COMMON_STOCKFISH_PATHS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate

    return None


def get_stockfish_installation_help() -> str:
    """Return actionable instructions for installing Stockfish on Linux."""
    return (
        "Stockfish chess engine was not found on your system.\n"
        "To install it on common Linux distributions:\n"
        "  • Ubuntu/Debian:  sudo apt install stockfish\n"
        "  • Arch Linux:     sudo pacman -S stockfish\n"
        "  • Fedora:         sudo dnf install stockfish\n"
        "  • openSUSE:       sudo zypper install stockfish\n"
        "Or download official binaries from https://stockfishchess.org/download/ "
        "and place them in ~/.local/bin/stockfish or pass --engine /path/to/stockfish."
    )


class EngineManager:
    """Manages the lifecycle, configuration, and execution of a UCI chess engine."""

    def __init__(
        self,
        engine_path: Optional[str | Path] = None,
        config: Optional[AppConfig] = None,
        threads: int = 1,
        hash_mb: int = 64,
    ):
        self.config = config or AppConfig()
        self.threads = threads or self.config.engine_threads
        self.hash_mb = hash_mb or self.config.engine_hash_mb
        self.binary_path = find_stockfish_binary(str(engine_path) if engine_path else None, self.config)
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.engine_name: str = "Unknown Engine"
        self.engine_author: str = "Unknown"
        self.supported_options: Dict[str, Any] = {}
        self.current_profile: Optional[EngineProfile] = None

    @property
    def is_available(self) -> bool:
        """Check whether an engine binary was successfully located."""
        return self.binary_path is not None

    def start(self) -> None:
        """Launch the UCI engine process and negotiate options."""
        if not self.binary_path:
            raise EngineNotFoundError(
                "Stockfish engine executable not found.",
                get_stockfish_installation_help(),
            )

        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(str(self.binary_path))
            self.supported_options = dict(self.engine.options)
            self.engine_name = self.engine.id.get("name", "UCI Chess Engine")
            self.engine_author = self.engine.id.get("author", "Unknown Author")
            self._apply_base_options()
            logger.info(f"Engine started successfully: {self.engine_name}")
        except Exception as e:
            self.close()
            raise EngineCommunicationError(
                f"Failed to start engine process at '{self.binary_path}': {e}",
                "Check that the binary is compatible with your architecture and has execute permissions."
            ) from e

    def _apply_base_options(self) -> None:
        """Configure conservative thread and memory limits."""
        if not self.engine:
            return
        options: Dict[str, Any] = {}
        if "Threads" in self.supported_options:
            options["Threads"] = max(1, self.threads)
        if "Hash" in self.supported_options:
            options["Hash"] = max(4, self.hash_mb)
        if self.config.tablebase_path and "SyzygyPath" in self.supported_options:
            options["SyzygyPath"] = self.config.tablebase_path

        if options:
            try:
                self.engine.configure(options)
            except Exception as e:
                logger.warning(f"Could not apply base engine options: {e}")

    def configure_profile(self, profile: EngineProfile) -> None:
        """Apply opponent or analysis profile options."""
        if not self.engine:
            return
        self.current_profile = profile
        uci_opts = profile.get_uci_options(self.supported_options)
        if uci_opts:
            try:
                self.engine.configure(uci_opts)
            except Exception as e:
                logger.warning(f"Error configuring profile '{profile.name}': {e}")

    def play_move(
        self,
        board: chess.Board,
        profile: Optional[EngineProfile] = None,
        time_limit: Optional[float] = None,
        depth_limit: Optional[int] = None,
    ) -> chess.Move:
        """Request the engine to play a move in the current position."""
        if not self.engine:
            raise EngineCommunicationError("Engine is not running.")

        prof = profile or self.current_profile or get_profile("intermediate")
        self.configure_profile(prof)

        t_limit = time_limit or prof.time_limit
        d_limit = depth_limit or prof.search_depth

        limit = chess.engine.Limit(time=t_limit, depth=d_limit)

        try:
            result = self.engine.play(board, limit)
            if result.move is None:
                raise EngineCommunicationError("Engine returned no move for position.")
            return result.move
        except chess.engine.EngineTerminatedError as e:
            self.close()
            raise EngineCommunicationError(
                "Engine process terminated unexpectedly during play.",
                "The engine may have crashed or run out of memory."
            ) from e
        except Exception as e:
            raise EngineCommunicationError(f"Error communicating with engine: {e}") from e

    def close(self) -> None:
        """Safely terminate engine process."""
        if self.engine:
            try:
                self.engine.quit()
            except Exception:
                try:
                    self.engine.close()
                except Exception:
                    pass
            finally:
                self.engine = None

    def __enter__(self) -> "EngineManager":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
