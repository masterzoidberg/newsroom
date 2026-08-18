"""Release identity and installed-artifact verification helpers."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any


_IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "coverage",
        "node_modules",
    }
)
_RUNTIME_SUFFIXES = (".db", ".db-shm", ".db-wal", ".sqlite", ".sqlite3")
_ARTIFACT_PREFIXES = ("newsroom/", "frontend/dist/", "docs/")
_ARTIFACT_FILES = frozenset({"pyproject.toml", "README.md"})


def _relative_files(root: Path, *, include_frontend_dist: bool) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(root)
        parts = relative.parts
        if any(part in _IGNORED_DIRECTORY_NAMES for part in parts):
            continue
        name = relative.name
        if name == ".env" or name.startswith(".env."):
            continue
        if name.endswith(_RUNTIME_SUFFIXES):
            continue
        if not include_frontend_dist and parts[:2] == ("frontend", "dist"):
            continue
        files.append(relative)
    return sorted(files, key=lambda path: path.as_posix())


def _artifact_files(root: Path) -> list[Path]:
    return [
        path
        for path in _relative_files(root, include_frontend_dist=True)
        if path.as_posix().startswith(_ARTIFACT_PREFIXES)
        or path.as_posix() in _ARTIFACT_FILES
    ]


def _file_record(root: Path, relative: Path) -> dict[str, Any]:
    content = (root / relative).read_bytes()
    return {
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


def _digest_records(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(record["sha256"].encode("ascii"))
        digest.update(b"\0")
        digest.update(str(record["size"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _tree_digest(root: Path) -> str:
    records = [_file_record(root, path) for path in _relative_files(root, include_frontend_dist=False)]
    return _digest_records(records)


def build_artifact_manifest(root: str | Path) -> dict[str, Any]:
    """Return a deterministic manifest for files copied to an install root."""
    source = Path(root).resolve()
    records = [_file_record(source, path) for path in _artifact_files(source)]
    return {"digest": _digest_records(records), "files": records}


def _git_value(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip()


def build_release_identity(root: str | Path) -> dict[str, Any]:
    """Record the source, Git state, and artifact identity for a release."""
    source = Path(root).resolve()
    commit = _git_value(source, "rev-parse", "HEAD")
    status = _git_value(source, "status", "--porcelain", "--untracked-files=all")
    artifact = build_artifact_manifest(source)
    return {
        "source_commit": commit,
        "worktree_clean": commit is not None and status == "",
        "source_tree_sha256": _tree_digest(source),
        "artifact_sha256": artifact["digest"],
        "artifact_files": artifact["files"],
    }


def _safe_relative_path(value: str) -> Path | None:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        return None
    return path


def verify_artifact_manifest(root: str | Path, manifest: dict[str, Any]) -> list[str]:
    """Return deterministic issues when an install differs from its manifest."""
    install = Path(root).resolve()
    expected = manifest.get("files", [])
    issues: list[str] = []
    if not isinstance(expected, list):
        return ["invalid manifest files"]
    expected_paths: set[str] = set()
    valid_records: list[dict[str, Any]] = []
    for record in expected:
        if not isinstance(record, dict):
            issues.append("invalid manifest file record")
            continue
        relative = _safe_relative_path(str(record.get("path", "")))
        if relative is None:
            issues.append(f"invalid manifest path: {record.get('path', '')}")
            continue
        path = relative.as_posix()
        valid_records.append(record)
        expected_paths.add(path)
        candidate = install / relative
        if not candidate.is_file():
            issues.append(f"missing: {path}")
            continue
        actual = _file_record(install, relative)
        if actual["sha256"] != record.get("sha256"):
            issues.append(f"hash mismatch: {path}")
        elif actual["size"] != record.get("size"):
            issues.append(f"size mismatch: {path}")

    actual_paths = {path.as_posix() for path in _artifact_files(install)}
    for path in sorted(actual_paths - expected_paths):
        issues.append(f"unexpected: {path}")
    if _digest_records(valid_records) != manifest.get("digest"):
        issues.append("manifest digest mismatch")
    return issues


__all__ = [
    "build_artifact_manifest",
    "build_release_identity",
    "verify_artifact_manifest",
]
