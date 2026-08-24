from __future__ import annotations

import sqlite3

import pytest

from newsroom import storage
from newsroom.cli import main as cli_main
from newsroom.integrity import check_database
from newsroom.migrations import MIGRATION_0001_STATEMENTS, apply_migrations, migration_status
from newsroom.repository import Repository, RepositoryIntegrityError, evidence_span_hash


EXPECTED_TABLES = {
    "schema_migrations",
    "app_meta",
    "settings",
    "users",
    "sessions",
    "categories",
    "topics",
    "topic_terms",
    "subjects",
    "subject_aliases",
    "topic_subjects",
    "sources",
    "documents",
    "document_versions",
    "stories",
    "story_revisions",
    "story_topics",
    "story_subjects",
    "claims",
    "claim_state_history",
    "claim_story_assignment_history",
    "evidence_spans",
    "claim_evidence",
    "research_questions",
    "monitoring_policies",
    "monitors",
    "jobs",
    "job_attempts",
    "runs",
    "tags",
    "story_tags",
    "story_review",
    "feedback_events",
    "provider_usage",
    "acquisition_events",
    "source_profiles",
    "source_suggestions",
    "budget_limits",
    "budget_reservations",
    "scheduler_state",
    "story_documents",
    "document_lineage",
    "story_evolution_events",
    "story_revision_documents",
    "ask_conversations",
    "ask_runs",
    "content_artifacts",
    "document_version_relevance",
    "article_analyses",
    "article_analysis_promotions",
}


def test_fresh_migration_creates_the_proposed_schema_and_rerun_is_idempotent(tmp_db):
    first = apply_migrations(tmp_db)
    second = apply_migrations(tmp_db)

    assert first.applied_versions == tuple(range(1, 32))
    assert second.applied_versions == ()
    assert migration_status(tmp_db) == tuple(range(1, 32))

    conn = storage.connect(tmp_db)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert EXPECTED_TABLES <= tables
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()[0] == "31"
    finally:
        conn.close()


def test_existing_phase02_database_migrates_forward_without_replaying_0001(tmp_db):
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            for statement in MIGRATION_0001_STATEMENTS:
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (1, '2026-01-01T00:00:00Z')")
            conn.execute("INSERT INTO app_meta(key, value) VALUES ('schema_version', '1')")
            conn.execute("INSERT INTO app_meta(key, value) VALUES ('schema_seeded_at', '2026-01-01T00:00:00Z')")
    finally:
        conn.close()

    result = apply_migrations(tmp_db)
    assert result.applied_versions == tuple(range(2, 32))
    assert migration_status(tmp_db) == tuple(range(1, 32))


def test_evidence_span_hash_includes_excerpt_and_locator():
    first = evidence_span_hash("same excerpt", "paragraph", "3")
    different_locator = evidence_span_hash("same excerpt", "paragraph", "4")
    different_excerpt = evidence_span_hash("different excerpt", "paragraph", "3")

    assert first == evidence_span_hash("same excerpt", "paragraph", "3")
    assert first != different_locator
    assert first != different_excerpt


def test_integrity_checker_reports_orphaned_polymorphic_monitor(tmp_db):
    apply_migrations(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        conn.execute(
            """
            INSERT INTO monitoring_policies
                (id, name, allowed_channels, base_cadence_seconds,
                 min_cadence_seconds, max_cadence_seconds, created_at, updated_at)
            VALUES ('pol_1', 'test', '[]', 60, 60, 3600, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.execute(
            """
            INSERT INTO monitors
                (id, target_type, target_id, policy_id, created_at, updated_at)
            VALUES ('mon_1', 'topic', 'missing-topic', 'pol_1', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
    finally:
        conn.close()

    report = check_database(tmp_db)
    assert not report.ok
    assert any(issue.code == "orphan_monitor_target" for issue in report.issues)


def test_repository_validates_monitor_target_inside_write_boundary(tmp_db):
    apply_migrations(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO categories(id, slug, name, created_at, updated_at) VALUES ('cat_1', 'cat', 'Cat', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO topics(id, category_id, slug, name, created_at, updated_at) VALUES ('top_1', 'cat_1', 'topic', 'Topic', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            """
            INSERT INTO monitoring_policies
                (id, name, allowed_channels, base_cadence_seconds,
                 min_cadence_seconds, max_cadence_seconds, created_at, updated_at)
            VALUES ('pol_1', 'test', '[]', 60, 60, 3600, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        repository = Repository(conn)
        repository.create_monitor(
            {
                "id": "mon_1",
                "target_type": "topic",
                "target_id": "top_1",
                "policy_id": "pol_1",
                "enabled": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )
        assert conn.execute("SELECT COUNT(*) FROM monitors").fetchone()[0] == 1
        with pytest.raises(RepositoryIntegrityError, match="does not exist"):
            repository.create_monitor(
                {
                    "id": "mon_2",
                    "target_type": "topic",
                    "target_id": "missing",
                    "policy_id": "pol_1",
                    "enabled": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            )
        assert conn.execute("SELECT COUNT(*) FROM monitors").fetchone()[0] == 1
    finally:
        conn.close()


def test_online_backup_restore_round_trip(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO app_meta(key, value) VALUES ('round_trip', 'before-restore')"
        )
    finally:
        conn.close()

    backup = storage.online_backup(tmp_path / "backup.db", source_path=tmp_db)
    conn = storage.connect(tmp_db)
    try:
        conn.execute(
            "UPDATE app_meta SET value = 'after-backup' WHERE key = 'round_trip'"
        )
    finally:
        conn.close()

    storage.restore_backup(backup, tmp_db)
    restored = storage.connect(tmp_db)
    try:
        assert restored.execute(
            "SELECT value FROM app_meta WHERE key = 'round_trip'"
        ).fetchone()[0] == "before-restore"
        assert storage.integrity_check(tmp_db) == "ok"
    finally:
        restored.close()


def test_operator_migrate_command_requires_environment_and_targets_its_root(tmp_path):
    root = tmp_path / "dev"
    assert cli_main(["migrate", "--environment", "dev", "--root", str(root)]) == 0
    assert (root / "data" / "newsroom.db").is_file()
    assert cli_main(["status", "--environment", "dev", "--root", str(root)]) == 0

    with pytest.raises(SystemExit):
        cli_main(["migrate", "--root", str(tmp_path / "dev")])
