"""Schema readiness and managed migration-authority guards.

Managed runtime children are readers/writers of an already-prepared schema, not
schema mutation authorities. The supervisor and explicit operator migration
commands acquire the existing component locks as a mechanical writer fence
before applying migrations. Direct development components use the same fence;
when they already own one managed-role lock, that ownership is reused rather
than re-acquired.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from .config import RuntimeConfig
from .migrations import CURRENT_SCHEMA_VERSION, MigrationResult, apply_migrations
from .runtime_identity import ExclusiveFileLock
from .runtime_managed import RUNTIME_ROLES, component_lock_path, current_owner


class SchemaAuthorityError(RuntimeError):
    """Base class for schema readiness/authority failures."""


class SchemaNotReady(SchemaAuthorityError):
    """The persisted database is not at the code's expected schema version."""


class MigrationAuthorityBusy(SchemaAuthorityError):
    """A managed writer is active, so schema mutation is not safe."""


def _readonly_uri(path: Path) -> str:
    # SQLite file URIs accept forward slashes on every supported platform.
    resolved = path.expanduser().resolve().as_posix()
    return f"file:{quote(resolved, safe='/:')}?mode=ro"


def schema_versions_readonly(db_path: str | Path) -> tuple[int, ...]:
    """Read the migration ledger without creating or mutating the database."""
    path = Path(db_path)
    if not path.is_file():
        raise SchemaNotReady(
            f"database is missing; expected schema {CURRENT_SCHEMA_VERSION}"
        )
    try:
        conn = sqlite3.connect(_readonly_uri(path), uri=True)
    except sqlite3.Error as exc:
        raise SchemaNotReady("database cannot be opened read-only") from exc
    try:
        ledger = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
        ).fetchone()
        if ledger is None:
            raise SchemaNotReady("schema migration ledger is missing")
        return tuple(
            int(row[0])
            for row in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        )
    except sqlite3.Error as exc:
        raise SchemaNotReady("schema migration ledger cannot be read") from exc
    finally:
        conn.close()


def verify_schema_ready(db_path: str | Path) -> tuple[int, ...]:
    """Fail closed unless every migration through CURRENT_SCHEMA_VERSION exists."""
    versions = schema_versions_readonly(db_path)
    expected = tuple(range(1, CURRENT_SCHEMA_VERSION + 1))
    if versions != expected:
        current = max(versions, default=0)
        missing = [version for version in expected if version not in set(versions)]
        detail = (
            f"schema is not ready: current ledger version {current}, "
            f"expected {CURRENT_SCHEMA_VERSION}"
        )
        if missing:
            detail += f"; missing migrations {missing[:8]}"
        raise SchemaNotReady(detail)

    path = Path(db_path)
    try:
        conn = sqlite3.connect(_readonly_uri(path), uri=True)
    except sqlite3.Error as exc:
        raise SchemaNotReady("schema metadata cannot be opened read-only") from exc
    try:
        row = conn.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.Error as exc:
        raise SchemaNotReady("schema metadata cannot be read") from exc
    finally:
        conn.close()
    if row is None or str(row[0]) != str(CURRENT_SCHEMA_VERSION):
        raise SchemaNotReady(
            "schema metadata does not match the migration ledger"
        )
    return versions


def _verify_held_role(config: RuntimeConfig, role: str) -> None:
    if role not in RUNTIME_ROLES:
        raise SchemaAuthorityError(f"unsupported held writer role: {role}")
    owner = current_owner(config, role)
    if owner is None or owner.pid != os.getpid():
        raise SchemaAuthorityError(
            f"migration caller does not own the declared {role} writer lock"
        )


def current_process_held_role(config: RuntimeConfig, role: str) -> str | None:
    """Return role only when this process already owns its managed-role lock."""
    if role not in RUNTIME_ROLES:
        raise SchemaAuthorityError(f"unsupported writer role: {role}")
    owner = current_owner(config, role)
    if owner is not None and owner.pid == os.getpid():
        return role
    return None


@contextmanager
def migration_writer_fence(
    config: RuntimeConfig,
    *,
    held_role: str | None = None,
) -> Iterator[None]:
    """Hold all managed writer locks across a schema mutation boundary.

    ``held_role`` is only for a development child already inside its
    ManagedRoleContext. The caller's ownership is verified before the other
    locks are acquired. Supervisor/operator paths leave it unset and acquire
    every component writer lock themselves.
    """
    if held_role is not None:
        _verify_held_role(config, held_role)
    locks: list[ExclusiveFileLock] = []
    try:
        for role in RUNTIME_ROLES:
            if role == held_role:
                continue
            lock = ExclusiveFileLock(component_lock_path(config, role))
            if not lock.acquire():
                raise MigrationAuthorityBusy(
                    f"cannot migrate while managed writer role {role} is active"
                )
            locks.append(lock)
        yield
    finally:
        for lock in reversed(locks):
            lock.release()


def apply_migrations_with_fence(
    config: RuntimeConfig,
    *,
    held_role: str | None = None,
) -> MigrationResult:
    """Apply migrations while the managed-writer boundary is mechanically held."""
    with migration_writer_fence(config, held_role=held_role):
        result = apply_migrations(config.database_path)
        verify_schema_ready(config.database_path)
        return result


def apply_component_migrations(config: RuntimeConfig, role: str) -> MigrationResult:
    """Migrate for a direct component without assuming how it was invoked.

    Normal runtime entry goes through ``ManagedRoleContext`` and therefore
    already owns ``role``. Focused tests and narrow embedding callers may invoke
    the component runner directly; in that case the function acquires all
    managed writer locks itself. Either route preserves the same writer fence.
    """
    held_role = current_process_held_role(config, role)
    return apply_migrations_with_fence(config, held_role=held_role)


__all__ = [
    "MigrationAuthorityBusy",
    "SchemaAuthorityError",
    "SchemaNotReady",
    "apply_component_migrations",
    "apply_migrations_with_fence",
    "current_process_held_role",
    "migration_writer_fence",
    "schema_versions_readonly",
    "verify_schema_ready",
]
