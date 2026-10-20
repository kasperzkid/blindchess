"""Linux standard directory and file paths following XDG specifications."""

import os
from pathlib import Path
from typing import Optional


def get_config_dir(custom_dir: Optional[Path] = None) -> Path:
    """Return the configuration directory, respecting XDG_CONFIG_HOME."""
    if custom_dir is not None:
        path = Path(custom_dir).expanduser().resolve()
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            path = Path(xdg_config) / "blindchess"
        else:
            path = Path.home() / ".config" / "blindchess"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir(custom_dir: Optional[Path] = None) -> Path:
    """Return the persistent data directory, respecting XDG_DATA_HOME."""
    if custom_dir is not None:
        path = Path(custom_dir).expanduser().resolve()
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            path = Path(xdg_data) / "blindchess"
        else:
            path = Path.home() / ".local" / "share" / "blindchess"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir(custom_dir: Optional[Path] = None) -> Path:
    """Return the cache directory, respecting XDG_CACHE_HOME."""
    if custom_dir is not None:
        path = Path(custom_dir).expanduser().resolve()
    else:
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            path = Path(xdg_cache) / "blindchess"
        else:
            path = Path.home() / ".cache" / "blindchess"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_db_path(data_dir: Optional[Path] = None) -> Path:
    """Return the default SQLite database path."""
    return get_data_dir(data_dir) / "blindchess.db"


def get_default_config_path(config_dir: Optional[Path] = None) -> Path:
    """Return the default JSON configuration file path."""
    return get_config_dir(config_dir) / "config.json"


def get_pgn_dir(data_dir: Optional[Path] = None) -> Path:
    """Return the directory where PGN files are saved."""
    path = get_data_dir(data_dir) / "pgn"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_backup_dir(data_dir: Optional[Path] = None) -> Path:
    """Return the directory where database backups are stored."""
    path = get_data_dir(data_dir) / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path
