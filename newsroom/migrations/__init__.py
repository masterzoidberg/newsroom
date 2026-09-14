"""Newsroom migration authority.

The original migration definitions remain in the sibling ``migrations.py``
module.  This package is the stable import/CLI surface and extends that applied
history without rewriting migrations 1-39.  The package form lets new bounded
migration slices live in small reviewable modules while preserving the public
``newsroom.migrations`` API used throughout the codebase.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Iterable, Optional

from .. import storage
from ..migration_0040_research_membership import MIGRATION_0040_STATEMENTS


_BASE_MODULE_NAME = "newsroom._migrations_0001_0039"
_BASE_PATH = Path(__file__).resolve().parent.parent / "migrations.py"
_spec = importlib.util.spec_from_file_location(_BASE_MODULE_NAME, _BASE_PATH)
if _spec is None or _spec.loader is None:  # pragma: no cover - packaging invariant
    raise ImportError(f"cannot load migration base from {_BASE_PATH}")
_base = importlib.util.module_from_spec(_spec)
sys.modules.setdefault(_BASE_MODULE_NAME, _base)
_spec.loader.exec_module(_base)

# Preserve the historical module API for callers/tests that import individual
# migration constants or helpers.  Overrides below remain the schema authority.
for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

MIGRATION_0040_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0040_STATEMENTS).encode("utf-8")
).hexdigest()
CURRENT_SCHEMA_VERSION = 40


def apply_migrations(db_path: Optional[str | Path] = None):
    """Apply immutable migrations 1-40 in one caller-visible operation."""
    base_result = _base.apply_migrations(db_path)
    conn = storage.connect(db_path)
    applied = list(base_result.applied_versions)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        with storage.write_tx(conn):
            existing = {
                int(row[0])
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            if 40 not in existing:
                missing_base = [version for version in range(1, 40) if version not in existing]
                if missing_base:
                    raise RuntimeError(
                        f"schema 40 requires contiguous migrations 1-39; missing {missing_base[:8]}"
                    )
                for statement in MIGRATION_0040_STATEMENTS:
                    conn.execute(statement)
                now = _base.utc_now()
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (40, now),
                )
                conn.execute(
                    "UPDATE app_meta SET value = ? WHERE key = 'schema_version'",
                    ("40",),
                )
                applied.append(40)
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError("migration 40 produced foreign-key violations")
        conn.execute("PRAGMA foreign_keys = ON")
        return _base.MigrationResult(tuple(applied), CURRENT_SCHEMA_VERSION)
    finally:
        conn.close()


def migration_status(db_path: Optional[str | Path] = None) -> tuple[int, ...]:
    """Return the complete applied migration ledger, including extensions."""
    return _base.migration_status(db_path)


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Keep ``python -m newsroom.migrations`` compatible with the new authority."""
    args = _base._parser().parse_args(argv)
    if args.command == "migrate":
        result = apply_migrations(args.db)
        print(
            f"migrated={','.join(map(str, result.applied_versions)) or 'none'} "
            f"current={result.current_version}"
        )
    else:
        print(",".join(map(str, migration_status(args.db))) or "none")
    return 0


__all__ = sorted(
    {
        *[name for name in dir(_base) if not name.startswith("__")],
        "CURRENT_SCHEMA_VERSION",
        "MIGRATION_0040_CHECKSUM",
        "MIGRATION_0040_STATEMENTS",
        "apply_migrations",
        "migration_status",
        "main",
    }
)
