"""Explicit environment-scoped operator commands."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Optional

from .config import load_runtime_config
from .integrity import check_database
from .migrations import apply_migrations, migration_status
from .operations import (
    backup_database,
    export_logical,
    purge_expired_sessions,
    restore_database,
    retain_backups,
    upgrade_database,
    verify_database,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Newsroom operator commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("migrate", "status", "integrity", "backup", "restore", "verify", "upgrade", "export", "retain"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--environment", choices=("dev", "prod"), required=True)
        subparser.add_argument("--root", type=Path)
    subparsers.choices["backup"].add_argument("--destination", type=Path, required=True)
    subparsers.choices["restore"].add_argument("--backup", type=Path, required=True)
    subparsers.choices["verify"].add_argument("--database", type=Path)
    subparsers.choices["export"].add_argument("--destination", type=Path, required=True)
    subparsers.choices["retain"].add_argument("--directory", type=Path)
    subparsers.choices["retain"].add_argument("--keep", type=int, default=7)
    subparsers.choices["retain"].add_argument("--older-than-days", type=int, default=30)
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
        result = backup_database(config.database_path, args.destination.parent, label="cli")
        destination = args.destination
        generated = Path(result["path"])
        if generated != destination:
            generated.replace(destination)
        print(json.dumps({"backup": str(destination), "environment": config.environment, "verified": True}, sort_keys=True))
        return 0

    if args.command == "restore":
        result = restore_database(args.backup, config.database_path)
        print(json.dumps({"restored": str(config.database_path), "environment": config.environment, "verified": result["verified"]}, sort_keys=True))
        return 0
    if args.command == "verify":
        report = verify_database(args.database or config.database_path)
        print(json.dumps({**report, "path": str(report["path"]), "environment": config.environment}, sort_keys=True))
        return 0 if report["ok"] else 1
    if args.command == "upgrade":
        result = upgrade_database(config.database_path)
        print(json.dumps({"environment": config.environment, "applied_versions": list(result["applied_versions"]), "verified": result["verified"]}, sort_keys=True))
        return 0
    if args.command == "export":
        destination = export_logical(config.database_path, args.destination)
        print(json.dumps({"export": str(destination), "environment": config.environment}, sort_keys=True))
        return 0
    if args.command == "retain":
        result = retain_backups(args.directory or config.backups_dir, keep=args.keep, older_than_days=args.older_than_days)
        result["directory"] = str(result["directory"])
        result["expired_sessions"] = purge_expired_sessions(config.database_path) if config.database_path.is_file() else 0
        print(json.dumps({**result, "environment": config.environment}, sort_keys=True))
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
