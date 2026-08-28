from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from scripts.create_review_snapshot import create_snapshot


def test_review_snapshot_contains_tracked_authority_and_excludes_working_directory_artifacts(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    output = tmp_path / "review.zip"

    file_count, ci_included = create_snapshot(repo, output)

    with ZipFile(output) as archive:
        members = set(archive.namelist())

    assert file_count == len(members)
    assert ci_included is True
    assert ".github/workflows/ci.yml" in members
    assert "scripts/create_review_snapshot.py" in members
    assert "plan/phases-v2/Phase 29.5.md" in members
    assert not any(
        part in member.split("/")
        for member in members
        for part in ("node_modules", "dist", ".pytest_cache", ".mypy_cache", "__pycache__")
    )
    assert not any(member.endswith((".sqlite", ".sqlite3", ".db")) for member in members)
