"""Explicit, guarded runtime configuration for Windows dev/prod roots."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from .paths import APP_NAME


VALID_ENVIRONMENTS = frozenset({"dev", "prod"})


def _environment_name(value: str) -> str:
    environment = value.strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError("environment must be exactly 'dev' or 'prod'")
    return environment


def _source_root() -> Path:
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    root: Path

    @classmethod
    def for_environment(
        cls,
        environment: str,
        *,
        root: str | Path | None = None,
        local_app_data: str | Path | None = None,
    ) -> "RuntimeConfig":
        environment = _environment_name(environment)
        if root is None:
            if local_app_data is None:
                local_app_data = os.environ.get("LOCALAPPDATA")
            if local_app_data:
                root = Path(local_app_data) / APP_NAME / environment
            else:
                root = Path.home() / ".local" / "share" / APP_NAME.lower() / environment
        resolved_root = Path(root).expanduser().resolve()
        if resolved_root.name.casefold() != environment:
            raise ValueError(
                f"runtime root for {environment} must end with '{environment}'"
            )
        source_root = _source_root()
        if resolved_root == source_root or source_root in resolved_root.parents:
            raise ValueError("runtime root cannot be inside the source repository")
        return cls(environment=environment, root=resolved_root)

    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "newsroom.db"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    def ensure_runtime_dirs(self) -> None:
        for directory in (
            self.data_dir,
            self.backups_dir,
            self.logs_dir,
            self.cache_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def load_runtime_config(
    *,
    environment: Optional[str],
    root: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    """Load operator configuration with explicit environment selection.

    `NEWSROOM_HOME` is intentionally ignored. It can silently redirect a
    process across dev/prod boundaries, so callers must use an explicit root.
    """
    values = os.environ if environ is None else environ
    selected = environment or values.get("NEWSROOM_ENV")
    if not selected:
        raise ValueError("an explicit environment ('dev' or 'prod') is required")
    return RuntimeConfig.for_environment(
        selected,
        root=root,
        local_app_data=values.get("LOCALAPPDATA"),
    )


__all__ = ["RuntimeConfig", "VALID_ENVIRONMENTS", "load_runtime_config"]
