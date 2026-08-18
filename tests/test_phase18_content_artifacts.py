"""Phase 18 — durable normalized content artifact acceptance.

These tests prove that every newly acquired DocumentVersion references a
durable, immutable, content-addressed normalized content artifact and that the
exact normalized text can be reloaded and hash-verified after process-object
recreation. Artifacts live in a SQLite ``content_artifacts`` table, referenced
by ``document_versions.artifact_id``, created atomically with the version by
the production acquisition path.

The transport is deterministic (no real internet). Live internet behavior was
already proven by Live Test A.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Mapping

import pytest

from newsroom import storage
from newsroom.acquisition import (
    AcquisitionService,
    HttpResponse,
    SafeHTMLExtractor,
)
from newsroom.content_artifacts import (
    ArtifactHashMismatch,
    ArtifactLengthMismatch,
    ArtifactNotFound,
    ContentArtifactService,
    LegacyVersionWithoutArtifact,
    normalized_text_hash,
)
from newsroom.domain import CoreService
from newsroom.integrity import check_database
from newsroom.migrations import apply_migrations, migration_status
from newsroom.monitoring import (
    MonitorExecutionService,
    MonitorService,
    MonitoringPolicyService,
)
from newsroom.scheduler import SchedulerProcess
from newsroom.worker import WorkerProcess
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.evidence import EvidenceService
from newsroom.operations import backup_database, restore_database, export_logical
from newsroom.jobs import MONITOR_CHECK_JOB_TYPE

T0 = "2026-08-18T12:00:00Z"

HTML_A = b"<html><title>Title A</title><p>First paragraph, visible text A.</p></html>"
HTML_B = b"<html><title>Title B</title><p>Second paragraph, visible text B.</p></html>"

RSS_V1 = b"""<rss version="2.0"><channel><title>Feed</title>
<item><title>Entry One</title><link>https://example.test/f/1</link><description>desc 1</description></item>
</channel></rss>"""
RSS_V2 = b"""<rss version="2.0"><channel><title>Feed</title>
<item><title>Entry One</title><link>https://example.test/f/1</link><description>desc 1</description></item>
<item><title>Entry Two</title><link>https://example.test/f/2</link><description>desc 2</description></item>
</channel></rss>"""


class SequencedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[dict[str, Any]] = []

    def get(self, url, *, headers, policy):
        self.requests.append({"url": url, "headers": dict(headers)})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _acquisition(db, transport):
    return AcquisitionService(db, transport=transport)


def _make_source(db, *, slug: str, homepage: str, feed_url: str | None = None) -> dict[str, Any]:
    core = CoreService(db)
    payload: Mapping[str, Any] = {"name": slug, "slug": slug}
    if feed_url:
        payload = {**payload, "feed_url": feed_url, "source_kind": "feed"}
    else:
        payload = {**payload, "homepage_url": homepage}
    return core.create_source(payload)


def _count(db, table: str, where: str = "1=1", params: tuple[Any, ...] = ()) -> int:
    conn = storage.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
    finally:
        conn.close()


def _get(db, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row:
    conn = storage.connect(db)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1-4. HTML artifact persistence + reload + hash verification + durability
# ---------------------------------------------------------------------------


def test_html_acquisition_persists_verifiable_normalized_artifact(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="a-human", homepage="https://example.test/a")
    service = _acquisition(
        tmp_db,
        SequencedTransport([HttpResponse(200, "https://example.test/a", {"content-type": "text/html"}, HTML_A)]),
    )
    result = service.acquire_document(source["id"], "https://example.test/a", channel="direct_http")

    assert result.outcome == "retrieved"
    assert result.artifact_id is not None

    version = _get(tmp_db, "SELECT * FROM document_versions WHERE id = ?", (result.document_version_id,))
    artifact = _get(tmp_db, "SELECT * FROM content_artifacts WHERE id = ?", (result.artifact_id,))
    event = _get(tmp_db, "SELECT * FROM acquisition_events WHERE id = ?", (result.event_id,))

    assert version["artifact_id"] == artifact["id"]
    extracted = SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_A.decode("utf-8"))
    assert artifact["normalized_text"] == extracted.text
    assert artifact["text_length"] == len(extracted.text)
    assert artifact["content_kind"] == "visible_text"
    assert artifact["norm_version"] == "visible_text_v1"
    assert artifact["normalized_content_hash"] == normalized_text_hash(artifact["normalized_text"])
    # The persisted normalized hash equals the exact stored text hash AND the
    # event's normalized hash.
    assert artifact["normalized_content_hash"] == result.normalized_content_hash
    assert event["normalized_content_hash"] == artifact["normalized_content_hash"]


def test_loaded_artifact_text_equals_extracted_visible_text_and_hash_verifies(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="b-human", homepage="https://example.test/b")
    service = _acquisition(
        tmp_db,
        SequencedTransport([HttpResponse(200, "https://example.test/b", {"content-type": "text/html"}, HTML_A)]),
    )
    result = service.acquire_document(source["id"], "https://example.test/b")
    loaded = ContentArtifactService(tmp_db).load_normalized_content(result.document_version_id)
    assert loaded["available"] is True
    extracted = SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_A.decode("utf-8"))
    assert loaded["normalized_text"] == extracted.text
    # Recompute the hash of what we loaded; it must match the persisted hash.
    assert normalized_text_hash(loaded["normalized_text"]) == loaded["normalized_content_hash"]
    # Strict loader returns the same bytes and can be re-verified.
    assert ContentArtifactService(tmp_db).load_verified_text(result.document_version_id) == extracted.text

    # Persisted normalized hash matches recomputed hash at the row level too.
    artifact = _get(tmp_db, "SELECT * FROM content_artifacts WHERE id = ?", (result.artifact_id,))
    assert normalized_text_hash(artifact["normalized_text"]) == artifact["normalized_content_hash"]


def test_artifact_survives_database_close_reopen(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="c-human", homepage="https://example.test/c")
    service = _acquisition(
        tmp_db,
        SequencedTransport([HttpResponse(200, "https://example.test/c", {"content-type": "text/html"}, HTML_A)]),
    )
    result = service.acquire_document(source["id"], "https://example.test/c")

    # Simulate a process restart: drop every in-memory service object and
    # re-read exclusively from SQLite.
    del service
    extracted = SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_A.decode("utf-8"))
    assert ContentArtifactService(tmp_db).load_verified_text(result.document_version_id) == extracted.text


# ---------------------------------------------------------------------------
# 5-6. Deduplication semantics
# ---------------------------------------------------------------------------


def test_unchanged_html_acquisition_reuses_version_and_artifact(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="d-human", homepage="https://example.test/d")
    service = _acquisition(
        tmp_db,
        SequencedTransport(
            [
                HttpResponse(200, "https://example.test/d", {"content-type": "text/html", "etag": '"v1"'}, HTML_A),
                HttpResponse(304, "https://example.test/d", {"etag": '"v1"'}, b""),
            ]
        ),
    )
    first = service.acquire_document(source["id"], "https://example.test/d")
    second = service.acquire_document(source["id"], "https://example.test/d")

    assert first.outcome == "retrieved"
    assert second.outcome == "not_modified"
    assert second.document_version_id == first.document_version_id
    assert second.artifact_id == first.artifact_id
    assert _count(tmp_db, "document_versions") == 1
    assert _count(tmp_db, "content_artifacts") == 1


def test_repeated_unchanged_200_html_creates_no_duplicate_version_or_artifact(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="e-human", homepage="https://example.test/e")
    service = _acquisition(
        tmp_db,
        SequencedTransport(
            [
                HttpResponse(200, "https://example.test/e", {"content-type": "text/html", "etag": '"v1"'}, HTML_A),
                HttpResponse(200, "https://example.test/e", {"content-type": "text/html", "etag": '"v1"'}, HTML_A),
            ]
        ),
    )
    first = service.acquire_document(source["id"], "https://example.test/e")
    second = service.acquire_document(source["id"], "https://example.test/e")

    assert first.outcome == "retrieved"
    assert second.outcome == "unchanged"
    assert _count(tmp_db, "document_versions") == 1
    # identical normalized text cannot create a duplicate artifact
    assert _count(tmp_db, "content_artifacts") == 1
    assert ContentArtifactService(tmp_db).load_verified_text(first.document_version_id)


def test_changed_html_creates_new_version_and_new_artifact(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="f-human", homepage="https://example.test/f")
    service = _acquisition(
        tmp_db,
        SequencedTransport(
            [
                HttpResponse(200, "https://example.test/f", {"content-type": "text/html", "etag": '"v1"'}, HTML_A),
                HttpResponse(200, "https://example.test/f", {"content-type": "text/html", "etag": '"v2"'}, HTML_B),
            ]
        ),
    )
    first = service.acquire_document(source["id"], "https://example.test/f")
    second = service.acquire_document(source["id"], "https://example.test/f")

    assert second.outcome == "retrieved"
    assert second.document_version_id != first.document_version_id
    assert second.artifact_id != first.artifact_id
    assert _count(tmp_db, "document_versions") == 2
    assert _count(tmp_db, "content_artifacts") == 2

    v1 = ContentArtifactService(tmp_db).load_verified_text(first.document_version_id)
    v2 = ContentArtifactService(tmp_db).load_verified_text(second.document_version_id)
    assert v1 == SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_A.decode("utf-8")).text
    assert v2 == SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_B.decode("utf-8")).text
    assert normalized_text_hash(v1) != normalized_text_hash(v2)


# ---------------------------------------------------------------------------
# 7-8. Feed entry artifacts
# ---------------------------------------------------------------------------


def test_feed_entry_acquisition_persists_normalized_metadata_artifact(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(
        tmp_db,
        slug="g-feed",
        homepage="https://example.test/g-home",
        feed_url="https://example.test/g.xml",
    )
    service = _acquisition(
        tmp_db,
        SequencedTransport([HttpResponse(200, "https://example.test/g.xml", {"content-type": "application/rss+xml"}, RSS_V1)]),
    )
    result = service.poll_feed(source["id"])

    assert result.new_count == 1
    assert result.artifact_ids
    artifact_id = result.artifact_ids[0]
    assert artifact_id is not None
    version = _get(tmp_db, "SELECT * FROM document_versions WHERE artifact_id = ?", (artifact_id,))
    artifact = _get(tmp_db, "SELECT * FROM content_artifacts WHERE id = ?", (artifact_id,))
    assert version is not None
    assert artifact["content_kind"] == "feed_metadata"
    assert artifact["norm_version"] == "feed_metadata_v1"
    # Artifact stores the exact normalized entry metadata string from the version.
    assert artifact["normalized_text"] == version["normalized_json"]
    assert artifact["normalized_content_hash"] == version["content_hash"]
    assert artifact["normalized_content_hash"] == normalized_text_hash(artifact["normalized_text"])
    loaded = ContentArtifactService(tmp_db).load_normalized_content(version["id"])
    assert loaded["available"] is True
    assert loaded["normalized_text"] == version["normalized_json"]


def test_repeated_unchanged_feed_creates_no_duplicate_versions_or_artifacts(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(
        tmp_db,
        slug="h-feed",
        homepage="https://example.test/h-home",
        feed_url="https://example.test/h.xml",
    )
    service = _acquisition(
        tmp_db,
        SequencedTransport(
            [
                HttpResponse(200, "https://example.test/h.xml", {"content-type": "application/rss+xml", "etag": '"f1"'}, RSS_V1),
                HttpResponse(304, "https://example.test/h.xml", {"etag": '"f1"'}, b""),
            ]
        ),
    )
    first = service.poll_feed(source["id"])
    second = service.poll_feed(source["id"])

    assert first.new_count == 1
    assert second.outcome == "not_modified"
    assert _count(tmp_db, "document_versions") == 1
    assert _count(tmp_db, "content_artifacts") == 1


# ---------------------------------------------------------------------------
# 9. Content-addressed artifact dedup (shared artifact allowed across versions)
# ---------------------------------------------------------------------------


def test_identical_normalized_content_shares_one_immutable_artifact(tmp_db):
    apply_migrations(tmp_db)
    text = SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_A.decode("utf-8")).text
    service = ContentArtifactService(tmp_db)
    first = service.create(normalized_text=text, content_kind="visible_text")
    # Content-addressing: the same exact normalized text reuses the artifact.
    second = service.create(normalized_text=text, content_kind="visible_text")
    assert second["id"] == first["id"]
    assert _count(tmp_db, "content_artifacts") == 1

    # Immutability: the stored content columns cannot be mutated at the DB layer.
    with pytest.raises(sqlite3.IntegrityError):
        conn = storage.connect(tmp_db)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "UPDATE content_artifacts SET normalized_text = ? WHERE id = ?",
                    ("tampered", first["id"]),
                )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 10. Corruption / mismatch detection
# ---------------------------------------------------------------------------


def test_corrupted_artifact_content_is_detected_by_loader_and_integrity(tmp_db):
    apply_migrations(tmp_db)
    # Directly insert a corrupt artifact whose stored text does NOT hash to its
    # recorded normalized_content_hash (simulating storage corruption).
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO content_artifacts
                    (id, normalized_content_hash, content_kind, norm_version,
                     normalized_text, text_length, retention_eligible, created_at)
                VALUES ('art_corrupt', 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
                        'visible_text', 'visible_text_v1', 'tampered content', 15, 1, ?)
                """,
                ("2026-08-18T12:00:00Z",),
            )
    finally:
        conn.close()

    # The loader must fail closed on hash mismatch.
    with pytest.raises(ArtifactHashMismatch):
        ContentArtifactService(tmp_db).verify("art_corrupt")
    # The integrity checker detects the same well-known mismatch.
    report = check_database(tmp_db)
    assert any(issue.code == "content_artifact_hash_mismatch" for issue in report.issues)


def test_content_artifact_length_mismatch_is_detected(tmp_db):
    apply_migrations(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO content_artifacts
                    (id, normalized_content_hash, content_kind, norm_version,
                     normalized_text, text_length, retention_eligible, created_at)
                VALUES ('art_len', ?, 'visible_text', 'visible_text_v1', 'text', 999, 1, ?)
                """,
                (normalized_text_hash("text"), "2026-08-18T12:00:00Z"),
            )
    finally:
        conn.close()
    with pytest.raises(ArtifactLengthMismatch):
        ContentArtifactService(tmp_db).verify("art_len")
    assert any(issue.code == "content_artifact_length_mismatch" for issue in check_database(tmp_db).issues)


def test_missing_referenced_artifact_is_reported(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="k-orphan", homepage="https://example.test/k")
    service = _acquisition(
        tmp_db,
        SequencedTransport([HttpResponse(200, "https://example.test/k", {"content-type": "text/html"}, HTML_A)]),
    )
    result = service.acquire_document(source["id"], "https://example.test/k")

    # Simulate a dangling artifact reference directly (document_versions is
    # immutable, so we use a raw sqlite connection with FK enforcement off).
    raw = sqlite3.connect(str(tmp_db))
    raw.execute("PRAGMA foreign_keys = OFF")
    raw.execute(
        "INSERT INTO document_versions (id, document_id, retrieved_at, content_hash, content_kind, artifact_id, normalized_json, created_at) "
        "VALUES ('dv_dangling', ?, '2026-08-18T12:00:00Z', 'hash', 'excerpt', 'art_ghost', '{}', '2026-08-18T12:00:00Z')",
        (result.document_id,),
    )
    raw.commit()
    raw.close()

    assert any(issue.code in {"missing_content_artifact", "foreign_key_violation"} for issue in check_database(tmp_db).issues)


# ---------------------------------------------------------------------------
# 11. Legacy DocumentVersion behavior
# ---------------------------------------------------------------------------


def test_legacy_version_without_artifact_reports_truthful_unavailability(tmp_db):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="l-legacy", homepage="https://example.test/l")
    core = CoreService(tmp_db)
    document = core.create_document({"source_id": source["id"], "canonical_url": "https://example.test/l", "title": "Legacy"})
    # Insert a pre-Phase-18 style version directly (no artifact).
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO document_versions (id, document_id, retrieved_at, content_hash, content_kind, normalized_json, created_at)
                VALUES ('dv_legacy', ?, '2026-08-01T00:00:00Z', 'oldhash', 'excerpt', '{"title":"Legacy"}', '2026-08-01T00:00:00Z')
                """,
                (document["id"],),
            )
    finally:
        conn.close()

    loaded = ContentArtifactService(tmp_db).load_normalized_content("dv_legacy")
    assert loaded["available"] is False
    assert loaded["reason"] == "legacy_version_without_artifact"
    with pytest.raises(LegacyVersionWithoutArtifact):
        ContentArtifactService(tmp_db).load_verified_text("dv_legacy")
    # Historical metadata remains fully readable and unmodified.
    restored = EvidenceService(tmp_db).get_document_version("dv_legacy")
    assert restored["content_hash"] == "oldhash"
    assert restored["normalized_json"] == {"title": "Legacy"}
    assert restored["artifact_id"] is None or "artifact_id" not in restored
    # Integrity check does NOT flag legacy versions for missing artifacts.
    assert check_database(tmp_db).ok is True


# ---------------------------------------------------------------------------
# 12. Backup / restore preserves artifacts
# ---------------------------------------------------------------------------


def test_backup_restore_preserves_artifact_content_and_references(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="m-backup", homepage="https://example.test/m")
    service = _acquisition(
        tmp_db,
        SequencedTransport([HttpResponse(200, "https://example.test/m", {"content-type": "text/html"}, HTML_A)]),
    )
    result = service.acquire_document(source["id"], "https://example.test/m")

    backup = backup_database(tmp_db, tmp_path / "backups")
    restored_path = tmp_path / "restored" / "newsroom.db"
    restored_path.parent.mkdir(parents=True, exist_ok=True)
    restore_database(backup["path"], restored_path)

    conn = storage.connect(restored_path)
    try:
        version = conn.execute("SELECT * FROM document_versions WHERE id = ?", (result.document_version_id,)).fetchone()
        artifact = conn.execute("SELECT * FROM content_artifacts WHERE id = ?", (result.artifact_id,)).fetchone()
        assert version["artifact_id"] == artifact["id"]
        assert artifact["normalized_text"] == SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_A.decode("utf-8")).text
        assert artifact["normalized_content_hash"] == normalized_text_hash(artifact["normalized_text"])
    finally:
        conn.close()
    assert ContentArtifactService(restored_path).load_verified_text(result.document_version_id)


# ---------------------------------------------------------------------------
# Privacy: exports must not include normalized article text
# ---------------------------------------------------------------------------


def test_logical_export_excludes_normalized_artifact_text(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    source = _make_source(tmp_db, slug="n-expr", homepage="https://example.test/n")
    service = _acquisition(
        tmp_db,
        SequencedTransport([HttpResponse(200, "https://example.test/n", {"content-type": "text/html"}, HTML_A)]),
    )
    service.acquire_document(source["id"], "https://example.test/n")
    destination = export_logical(tmp_db, tmp_path / "export.jsonl")
    contents = destination.read_text(encoding="utf-8")
    assert "First paragraph, visible text A." not in contents
    assert '"content_artifacts"' not in contents


# ---------------------------------------------------------------------------
# Bounded size behavior for artifacts
# ---------------------------------------------------------------------------


def test_artifact_service_rejects_oversized_direct_content(tmp_db):
    apply_migrations(tmp_db)
    service = ContentArtifactService(tmp_db, max_text_chars=10)
    with pytest.raises(Exception):
        service.create(normalized_text="x" * 11, content_kind="visible_text")


# ---------------------------------------------------------------------------
# Production-composition acceptance: Scheduler -> Job -> Worker -> artifact
# ---------------------------------------------------------------------------


def test_production_composition_persists_reloadable_normalized_artifact(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Runtime Artifact", "slug": "rt-art", "homepage_url": "https://example.test/rt"})
    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "rt-art-policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 600,
        }
    )
    monitor = MonitorService(tmp_db).create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )

    class CountingTransport:
        calls = 0

        def get(self, url, *, headers, policy):
            self.calls += 1
            return HttpResponse(200, "https://example.test/rt", {"content-type": "text/html", "etag": '"rt1"'}, HTML_A)

    transport = CountingTransport()
    acquisition = AcquisitionService(tmp_db, transport=transport)
    handlers = MonitorExecutionService(tmp_db, acquisition_service=acquisition).handlers()
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, handlers, worker_id="worker-rt-art", queue=queue)

    scheduled = SchedulerProcess(tmp_db).run_once()
    assert scheduled["enqueued"] == 1
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert finished["job_type"] == MONITOR_CHECK_JOB_TYPE

    version = _get(tmp_db, "SELECT * FROM document_versions")
    assert version is not None
    artifact = _get(tmp_db, "SELECT * FROM content_artifacts WHERE id = ?", (version["artifact_id"],))
    assert artifact is not None
    assert artifact["content_kind"] == "visible_text"
    assert normalized_text_hash(artifact["normalized_text"]) == artifact["normalized_content_hash"]

    # Destroy every service object; reconstruct and prove reload works.
    del worker, queue, handlers, acquisition, transport, policy, monitor
    extracted = SafeHTMLExtractor(max_text_chars=200_000).extract(HTML_A.decode("utf-8"))
    assert ContentArtifactService(tmp_db).load_verified_text(version["id"]) == extracted.text


# ---------------------------------------------------------------------------
# Migration 0015: upgrade + idempotency + legacy preservation
# ---------------------------------------------------------------------------


def test_fresh_database_applies_through_migration_15(tmp_db):
    result = apply_migrations(tmp_db)
    assert result.applied_versions == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)
    assert result.current_version == 17
    assert migration_status(tmp_db) == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)
    assert apply_migrations(tmp_db).applied_versions == ()
    row = _get(tmp_db, "SELECT value FROM app_meta WHERE key = 'schema_version'")
    assert row[0] == "17"
    tables = {r[0] for r in _get_rows(tmp_db, "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "content_artifacts" in tables
    columns = {r[1] for r in _get_rows(tmp_db, "PRAGMA table_info(document_versions)")}
    assert "artifact_id" in columns


def test_schema_14_database_upgrades_to_15_preserving_data(tmp_db):
    from newsroom.migrations import MIGRATION_0001_STATEMENTS, MIGRATION_0002_STATEMENTS, MIGRATION_0003_STATEMENTS, MIGRATION_0004_STATEMENTS, MIGRATION_0005_STATEMENTS, MIGRATION_0006_STATEMENTS, MIGRATION_0007_STATEMENTS, MIGRATION_0008_STATEMENTS, MIGRATION_0009_STATEMENTS, MIGRATION_0010_STATEMENTS, MIGRATION_0011_STATEMENTS, MIGRATION_0012_STATEMENTS, MIGRATION_0013_STATEMENTS, MIGRATION_0014_STATEMENTS

    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            for statements in (
                MIGRATION_0001_STATEMENTS,
                MIGRATION_0002_STATEMENTS,
                MIGRATION_0003_STATEMENTS,
                MIGRATION_0004_STATEMENTS,
                MIGRATION_0005_STATEMENTS,
                MIGRATION_0006_STATEMENTS,
                MIGRATION_0007_STATEMENTS,
                MIGRATION_0008_STATEMENTS,
                MIGRATION_0009_STATEMENTS,
                MIGRATION_0010_STATEMENTS,
                MIGRATION_0011_STATEMENTS,
                MIGRATION_0012_STATEMENTS,
                MIGRATION_0013_STATEMENTS,
                MIGRATION_0014_STATEMENTS,
            ):
                for statement in statements:
                    conn.execute(statement)
            for version in range(1, 15):
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, "2026-08-18T00:00:00Z"),
                )
            conn.execute("UPDATE app_meta SET value = '14' WHERE key = 'schema_version'")
            conn.execute(
                "INSERT INTO sources (id, name, slug, source_kind, created_at, updated_at) VALUES ('src_old','Old','old','web','2026-08-01T00:00:00Z','2026-08-01T00:00:00Z')"
            )
            conn.execute(
                "INSERT INTO documents (id, source_id, canonical_url, canonical_url_hash, title, title_normalized, first_seen_at, created_at) VALUES ('doc_old','src_old','https://example.test/old','old-fp','Old doc','old doc','2026-08-01T00:00:00Z','2026-08-01T00:00:00Z')"
            )
            conn.execute(
                "INSERT INTO document_versions (id, document_id, retrieved_at, content_hash, content_kind, normalized_json, created_at) VALUES ('dv_old','doc_old','2026-08-01T00:00:00Z','old-hash','excerpt','{\"title\":\"Old\"}','2026-08-01T00:00:00Z')"
            )
    finally:
        conn.close()

    result = apply_migrations(tmp_db)
    assert result.applied_versions == (15, 16, 17)
    assert migration_status(tmp_db) == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17)

    old = _get(tmp_db, "SELECT * FROM document_versions WHERE id = 'dv_old'")
    assert old["content_hash"] == "old-hash"
    assert old["artifact_id"] is None
    # Legacy version remains readable without an artifact and is not flagged.
    loaded = ContentArtifactService(tmp_db).load_normalized_content("dv_old")
    assert loaded["available"] is False
    assert check_database(tmp_db).ok is True


def _get_rows(db, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    conn = storage.connect(db)
    try:
        return list(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def test_redirect_regression_from_live_test_a_still_passes(tmp_db):
    from newsroom.acquisition import _BoundedRedirectHandler

    class RecordingPolicy:
        def __init__(self):
            self.checked: list[str] = []

        def check_resolved_url(self, url: str) -> str:
            self.checked.append(url)
            return "https://usa.gov/"

    policy = RecordingPolicy()
    handler = _BoundedRedirectHandler(max_redirects=3, policy=policy)
    import urllib.request

    request = urllib.request.Request("https://usa.gov/", headers={"User-Agent": "newsroom-test"})
    followed = handler.redirect_request(
        request,
        None,
        301,
        "Moved Permanently",
        {"Location": "https://www.usa.gov/"},
        "https://www.usa.gov/",
    )
    assert followed is not None
    assert followed.get_full_url() == "https://www.usa.gov/"
    assert policy.checked == ["https://www.usa.gov/"]
    assert handler.count == 1
