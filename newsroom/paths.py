"""Standalone runtime path resolution.

Runtime data never lives in the source repository.  Production code receives
its runtime root explicitly from configuration; tests can override the DB path.
There is intentionally no host-specific profile dependency.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

APP_NAME = "Newsroom"


def default_runtime_root() -> Path:
    """Return the platform-local standalone runtime root.

    Windows: %LOCALAPPDATA%/Newsroom
    Other platforms: ~/.local/share/newsroom
    """
    if os.name == "nt":
        local = (os.environ.get("LOCALAPPDATA") or "").strip()
        if local:
            return Path(local) / APP_NAME
    return Path.home() / ".local" / "share" / "newsroom"


def runtime_root(explicit: str | Path | None = None) -> Path:
    """Resolve runtime root, preferring an explicit caller-supplied path.

    NEWSROOM_HOME is supported for service/process configuration but operator
    tooling must pass an explicit environment/home and verify it before writes.
    """
    if explicit is not None:
        return Path(explicit)
    env = (os.environ.get("NEWSROOM_HOME") or "").strip()
    return Path(env) if env else default_runtime_root()


def data_dir(root: str | Path | None = None) -> Path:
    return runtime_root(root) / "data"


def db_path(root: str | Path | None = None) -> Path:
    return data_dir(root) / "newsroom.db"


def backups_dir(root: str | Path | None = None) -> Path:
    return runtime_root(root) / "backups"


def logs_dir(root: str | Path | None = None) -> Path:
    return runtime_root(root) / "logs"


def cache_dir(root: str | Path | None = None) -> Path:
    return runtime_root(root) / "cache"


def ensure_runtime_dirs(root: str | Path | None = None) -> None:
    for path in (data_dir(root), backups_dir(root), logs_dir(root), cache_dir(root)):
        path.mkdir(parents=True, exist_ok=True)


_DB_PATH_OVERRIDE: dict[str, Optional[Path]] = {"path": None}


def set_db_path_override(path: Optional[str | Path]) -> None:
    _DB_PATH_OVERRIDE["path"] = None if path is None else Path(path)


def active_db_path(root: str | Path | None = None) -> Path:
    override = _DB_PATH_OVERRIDE.get("path")
    return override if override else db_path(root)
