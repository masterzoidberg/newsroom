"""Explicit environment-scoped operator commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from .config import load_runtime_config
from .integrity import check_database
from .migrations import apply_migrations, migration_status
from .storage import online_backup, restore_backup


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Newsroom operator commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("migrate", "status", "integrity", "backup", "restore"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--environment", choices=("dev", "prod"), required=True)
        subparser.add_argument("--root", type=Path)
    subparsers.choices["backup"].add_argument("--destination", type=Path, required=True)
    subparsers.choices["restore"].add_argument("--backup", type=Path, required=True)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    config = load_runtime_config(
        environment=args.environment,
        root=args.root,
    )
    config.ensure_runtime_dirs()

    if args.command == "migrate":
        result = apply_migrations(config.database_path)
        print(
            json.dumps(
                {
                    "applied_versions": list(result.applied_versions),
                    "current_version": result.current_version,
                    "environment": config.environment,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "status":
        print(
            json.dumps(
                {"environment": config.environment, "versions": list(migration_status(config.database_path))},
                sort_keys=True,
            )
        )
        return 0
    if args.command == "integrity":
        report = check_database(config.database_path)
        print(
            json.dumps(
                {
                    "environment": config.environment,
                    "ok": report.ok,
                    "issues": [
                        {"code": issue.code, "detail": issue.detail}
                        for issue in report.issues
                    ],
                },
                sort_keys=True,
            )
        )
        return 0 if report.ok else 1
    if args.command == "backup":
        destination = online_backup(args.destination, source_path=config.database_path)
        print(json.dumps({"backup": str(destination), "environment": config.environment}, sort_keys=True))
        return 0

    restore_backup(args.backup, config.database_path)
    print(json.dumps({"restored": str(config.database_path), "environment": config.environment}, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
