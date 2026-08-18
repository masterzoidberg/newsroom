from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.app import create_app
from newsroom.cli import main as cli_main
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService
from newsroom.migrations import apply_migrations, migration_status
from newsroom.operations import (
    ExportLimitExceeded,
    backup_database,
    export_logical,
    purge_expired_sessions,
    restore_database,
    retain_backups,
    upgrade_database,
    verify_database,
)


PASSWORD = "a-long-test-password-12345"


def test_backup_restore_upgrade_and_integrity_rehearsal_are_verified(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        conn.execute("INSERT INTO app_meta(key, value) VALUES ('phase15', 'before')")
    finally:
        conn.close()

    backup = backup_database(tmp_db, tmp_path / "backups")
    assert backup["verified"] is True
    assert backup["integrity"] == "ok"
    assert verify_database(backup["path"])["ok"] is True

    conn = storage.connect(tmp_db)
    try:
        conn.execute("UPDATE app_meta SET value = 'after' WHERE key = 'phase15'")
    finally:
        conn.close()
    restored = restore_database(backup["path"], tmp_db)
    assert restored["verified"] is True

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT value FROM app_meta WHERE key = 'phase15'").fetchone()[0] == "before"
    finally:
        conn.close()

    upgraded = upgrade_database(tmp_db)
    assert upgraded["verified"] is True
    assert migration_status(tmp_db) == tuple(range(1, 15))


def test_logical_export_is_streamed_and_excludes_secrets_prompts_and_note_bodies(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "Export source", "slug": "export-source"})
    CoreService(tmp_db).create_document(
        {"source_id": source["id"], "canonical_url": "https://export.test/item", "title": "Export item"}
    )
    conn = storage.connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO users(id, username, password_hash, password_algo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("usr_export", "admin", "argon2id-secret-hash", "argon2id", "2026-08-16T00:00:00Z", "2026-08-16T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO notes(id, object_type, object_id, note_type, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("note_export", "story", "missing-story", "note", "private note body", "2026-08-16T00:00:00Z", "2026-08-16T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO ask_conversations(id, scope_type, scope_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("ask_export", "global", None, "2026-08-16T00:00:00Z", "2026-08-16T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO ask_runs(id, conversation_id, turn_number, prompt_hash, prompt_length, status, answer_json, retrieval_json, citations_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("ask_run_export", "ask_export", 1, "hash", 20, "answered", json.dumps({"answer": "sensitive answer"}), "{}", "[]", "2026-08-16T00:00:00Z"),
        )
    finally:
        conn.close()

    destination = export_logical(tmp_db, tmp_path / "export.jsonl")
    contents = destination.read_text(encoding="utf-8")
    assert "private note body" not in contents
    assert "argon2id-secret-hash" not in contents
    assert "sensitive answer" not in contents
    assert "password_hash" not in contents
    assert "prompt" not in contents
    assert "documents" in contents

    with pytest.raises(ExportLimitExceeded):
        export_logical(tmp_db, tmp_path / "too-small.jsonl", max_rows=1)


def test_backup_retention_keeps_newest_files_and_session_purge_is_bounded(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for name in ("newsroom-20260101-000000.db", "newsroom-20260102-000000.db", "newsroom-20260103-000000.db"):
        (backup_dir / name).write_bytes(b"placeholder")
    (backup_dir / "unrelated.txt").write_text("keep", encoding="utf-8")

    result = retain_backups(backup_dir, keep=1, older_than_days=0)
    assert result["deleted"] == 2
    assert (backup_dir / "newsroom-20260103-000000.db").exists()
    assert (backup_dir / "unrelated.txt").exists()

    conn = storage.connect(tmp_db)
    try:
        conn.execute(
            "INSERT INTO users(id, username, password_hash, password_algo, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("usr_session", "session-user", "hash", "argon2id", "2026-08-15T00:00:00Z", "2026-08-15T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO sessions(id, user_id, created_at, expires_at, revoked_at, csrf_token_hash) VALUES (?, ?, ?, ?, ?, ?)",
            ("expired", "usr_session", "2026-08-15T00:00:00Z", "2026-08-15T00:00:00Z", None, "hash"),
        )
    finally:
        conn.close()
    assert purge_expired_sessions(tmp_db, now="2026-08-16T00:00:00Z") == 1


def test_operator_cli_exposes_verified_backup_upgrade_export_and_verify(tmp_path):
    root = tmp_path / "dev"
    assert cli_main(["migrate", "--environment", "dev", "--root", str(root)]) == 0
    backup_path = tmp_path / "backups" / "newsroom-latest.db"
    export_path = tmp_path / "backups" / "newsroom-export.jsonl"
    assert cli_main(["backup", "--environment", "dev", "--root", str(root), "--destination", str(backup_path)]) == 0
    assert backup_path.is_file()
    assert cli_main(["verify", "--environment", "dev", "--root", str(root)]) == 0
    assert cli_main(["export", "--environment", "dev", "--root", str(root), "--destination", str(export_path)]) == 0
    assert export_path.is_file()
    assert cli_main(["upgrade", "--environment", "dev", "--root", str(root)]) == 0


def test_request_limits_metrics_cache_control_and_error_redaction(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="newsroom.api")
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")
    app.add_api_route("/api/v1/test-failure", lambda: (_ for _ in ()).throw(RuntimeError(str(tmp_path / "private"))), methods=["GET"])

    with TestClient(app, raise_server_exceptions=False) as client:
        login = client.post("/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD})
        assert login.status_code == 201
        logged_in = client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
        assert logged_in.status_code == 200
        set_cookie = logged_in.headers.get("set-cookie", "").lower()
        assert "httponly" in set_cookie
        assert "samesite=lax" in set_cookie
        assert logged_in.headers["cache-control"] == "no-store"

        too_large = client.post(
            "/api/v1/auth/setup",
            json={"username": "another", "password": "x" * 1_050_000},
        )
        assert too_large.status_code == 413
        streamed_body = b'{"username":"another","password":"' + b"x" * 1_050_000 + b'"}'
        streamed = client.post(
            "/api/v1/auth/setup",
            content=iter([streamed_body]),
            headers={"content-type": "application/json"},
        )
        assert streamed.status_code == 413
        streamed_login = client.post(
            "/api/v1/auth/login",
            content=iter([b'{"username":"admin","password":"' + PASSWORD.encode() + b'"}']),
            headers={"content-type": "application/json"},
        )
        assert streamed_login.status_code == 200

        failure = client.get("/api/v1/test-failure")
        assert failure.status_code == 500
        assert str(tmp_path / "private") not in failure.text
        assert "Traceback" not in failure.text

        for _ in range(130):
            limited = client.get("/api/v1/health")
            if limited.status_code == 429:
                break
        else:
            pytest.fail("request limiter did not engage")
        assert limited.headers["retry-after"]

        metrics = client.get("/api/v1/metrics")
        assert metrics.status_code == 200
        payload = metrics.json()
        assert payload["requests_total"] > 0
        assert payload["failure_counts_by_subsystem"]["domain"] >= 1
        assert "private" not in json.dumps(payload)
        assert "password" not in json.dumps(payload).lower()
    assert all(PASSWORD not in record.getMessage() for record in caplog.records)
