from __future__ import annotations

import json

import pytest

from newsroom import storage
from newsroom.article_analysis import ArticleAnalysisService, analysis_identity_hash
from newsroom.domain import CoreService, DomainConflict, DomainNotFound, DomainValidation
from newsroom.evidence import EvidenceService
from newsroom.evidence_promotion import ArticleAnalysisPromotionService
from newsroom.document_processing import DocumentProcessingExecutionService
from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.operations import export_logical
from newsroom.workbench import ComparisonService, SearchService
from newsroom.worker import RetryableJobFailure, WorkerProcess

from test_phase22_evidence_promotion import _analysis


def _count(db, table: str) -> int:
    conn = storage.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _variant_analysis(db, analysis):
    conn = storage.connect(db)
    try:
        row = conn.execute("SELECT * FROM article_analyses WHERE id = ?", (analysis["id"],)).fetchone()
    finally:
        conn.close()
    identity = analysis_identity_hash(
        document_version_id=row["document_version_id"],
        relevance_id=row["relevance_id"],
        scope_version=row["scope_version"],
        schema_version=row["schema_version"],
        prompt_version=row["prompt_version"],
        provider="local-variant",
        model="deterministic-local-v2",
        artifact_id=row["artifact_id"],
        normalized_content_hash=row["normalized_content_hash"],
        input_view_version=row["input_view_version"],
        input_content_hash=row["input_content_hash"],
        analyzed_content_hash=row["analyzed_content_hash"],
    )
    return ArticleAnalysisService(db).persist(
        document_version_id=row["document_version_id"],
        relevance_id=row["relevance_id"],
        monitor_id=row["monitor_id"],
        scope_version=row["scope_version"],
        job_id=row["job_id"],
        artifact_id=row["artifact_id"],
        normalized_content_hash=row["normalized_content_hash"],
        schema_version=row["schema_version"],
        prompt_version=row["prompt_version"],
        identity_hash=identity,
        provider="local-variant",
        model="deterministic-local-v2",
        paid=False,
        confidence=row["confidence"],
        input_char_count=row["input_char_count"],
        analyzed_char_count=row["analyzed_char_count"],
        truncated=bool(row["truncated"]),
        input_view_version=row["input_view_version"],
        input_content_hash=row["input_content_hash"],
        analyzed_content_hash=row["analyzed_content_hash"],
        result=json.loads(row["result_json"]),
    )


def test_automatic_promotion_does_not_reuse_manual_evidence_as_verified(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    manual = EvidenceService(tmp_db).create_evidence_span(
        analysis["document_version_id"],
        {
            "excerpt": "released a UAP report",
            "locator_type": "codepoint_offset",
            "locator_value": "11;32",
        },
    )

    outcome = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])

    assert outcome["outcomes"][0]["code"] == "verified"
    manual_replay = EvidenceService(tmp_db).create_evidence_span(
        analysis["document_version_id"],
        {
            "excerpt": "released a UAP report",
            "locator_type": "codepoint_offset",
            "locator_value": "11;32",
        },
    )
    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute("SELECT * FROM evidence_spans ORDER BY id").fetchall()
        linked_id = conn.execute("SELECT evidence_span_id FROM claim_evidence").fetchone()[0]
    finally:
        conn.close()
    assert len(rows) == 2
    assert manual_replay["id"] == manual["id"]
    assert linked_id != manual["id"]
    verified = next(row for row in rows if row["id"] == linked_id)
    assert verified["article_analysis_id"] == analysis["id"]
    assert verified["verification_method"] == "exact_analyzed_slice_v1"


def test_manual_evidence_path_does_not_reuse_automatic_span(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promoted = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    automatic_id = promoted["outcomes"][0]["evidence_span_ids"][0]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            manual_id = EvidenceService(tmp_db)._create_span_tx(
                conn,
                analysis["document_version_id"],
                {
                    "excerpt": "released a UAP report",
                    "locator_type": "codepoint_offset",
                    "locator_value": "11;32",
                },
            )
            row = conn.execute("SELECT verification_method FROM evidence_spans WHERE id = ?", (manual_id,)).fetchone()
    finally:
        conn.close()

    assert manual_id != automatic_id
    assert row["verification_method"] is None


def test_comparison_safely_represents_storyless_and_story_linked_claims(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    conn = storage.connect(tmp_db)
    try:
        first_document_id = conn.execute(
            "SELECT document_id FROM document_versions WHERE id = ?",
            (analysis["document_version_id"],),
        ).fetchone()[0]
    finally:
        conn.close()

    core = CoreService(tmp_db)
    story = core.create_story({"headline": "UAP report"})
    second_document = core.create_document(
        {
            "source_id": core.list_sources()["items"][0]["id"],
            "canonical_url": "https://example.test/uap-follow-up",
            "title": "UAP follow-up",
        }
    )
    ledger = EvidenceService(tmp_db)
    version = ledger.create_document_version(
        second_document["id"],
        {"content_hash": "manual-follow-up", "content_kind": "excerpt"},
    )
    span = ledger.create_evidence_span(
        version["id"],
        {"excerpt": "The agency did not release a UAP report."},
    )
    claim = ledger.create_claim(
        story["id"],
        {"proposition": "The agency did not release a UAP report."},
    )
    ledger.link_claim_evidence(
        claim["id"],
        {"evidence_span_id": span["id"], "relationship": "contradicts"},
    )

    comparison = ComparisonService(tmp_db).compare([first_document_id, second_document["id"]])

    storyless = [item for item in comparison["unique_claims"] if item["claim_id"] != claim["id"]]
    assert storyless
    assert storyless[0]["story_id"] is None
    assert comparison["contradictions"]


def test_storyless_claim_is_serializable_and_searchable(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]

    claim = EvidenceService(tmp_db).get_claim(claim_id)
    result = SearchService(tmp_db).search("released UAP", entity_types=["claim"])

    assert claim["story_id"] is None
    assert claim["story_assignment_history"] == []
    assert any(item["entity_id"] == claim_id and item["story_id"] is None for item in result["items"])


def test_controlled_assignment_allows_initial_story_link_for_automatic_claim(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    claim_id = promotion["outcomes"][0]["claim_id"]
    story = CoreService(tmp_db).create_story({"headline": "UAP report"})

    assigned = EvidenceService(tmp_db).assign_claim_to_story(claim_id, story["id"])

    assert assigned["id"] == claim_id
    assert assigned["story_id"] == story["id"]
    assert len(assigned["story_assignment_history"]) == 1


def test_same_story_assignment_replay_is_idempotent(tmp_db):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]
    story = CoreService(tmp_db).create_story({"headline": "UAP report"})
    service = EvidenceService(tmp_db)

    first = service.assign_claim_to_story(claim_id, story["id"])
    second = service.assign_claim_to_story(claim_id, story["id"])

    assert first["story_id"] == story["id"]
    assert second["story_id"] == story["id"]
    assert len(second["story_assignment_history"]) == 1


def test_conflicting_story_reassignment_is_rejected(tmp_db):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]
    core = CoreService(tmp_db)
    first_story = core.create_story({"headline": "First UAP report"})
    second_story = core.create_story({"headline": "Second UAP report"})
    service = EvidenceService(tmp_db)
    service.assign_claim_to_story(claim_id, first_story["id"])

    with pytest.raises(DomainConflict, match="cannot be reassigned"):
        service.assign_claim_to_story(claim_id, second_story["id"])


def test_story_removal_is_rejected(tmp_db):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]
    story = CoreService(tmp_db).create_story({"headline": "UAP report"})
    service = EvidenceService(tmp_db)
    service.assign_claim_to_story(claim_id, story["id"])

    with pytest.raises(DomainValidation, match="story_id"):
        service.assign_claim_to_story(claim_id, None)


def test_nonexistent_story_assignment_is_rejected(tmp_db):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]

    with pytest.raises(DomainNotFound, match="story not found"):
        EvidenceService(tmp_db).assign_claim_to_story(claim_id, "st_missing")


def test_story_assignment_cannot_mutate_automatic_provenance(tmp_db):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]
    story = CoreService(tmp_db).create_story({"headline": "UAP report"})
    conn = storage.connect(tmp_db)
    try:
        with pytest.raises(storage.sqlite3.IntegrityError, match="automatic claim provenance"):
            conn.execute(
                "UPDATE claims SET story_id = ?, proposition = ? WHERE id = ?",
                (story["id"], "tampered", claim_id),
            )
    finally:
        conn.close()


def test_direct_story_reassignment_is_rejected_by_database(tmp_db):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]
    core = CoreService(tmp_db)
    first_story = core.create_story({"headline": "First UAP report"})
    second_story = core.create_story({"headline": "Second UAP report"})
    EvidenceService(tmp_db).assign_claim_to_story(claim_id, first_story["id"])
    conn = storage.connect(tmp_db)
    try:
        with pytest.raises(storage.sqlite3.IntegrityError, match="Story association"):
            conn.execute("UPDATE claims SET story_id = ? WHERE id = ?", (second_story["id"], claim_id))
    finally:
        conn.close()


def test_worker_retry_reuses_committed_phase22_graph_after_completion_ack_failure(tmp_db):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    conn = storage.connect(tmp_db)
    try:
        job_row = conn.execute(
            "SELECT * FROM jobs WHERE idempotency_key = 'phase22'"
        ).fetchone()
    finally:
        conn.close()

    class ReusingAnalysisService:
        def analyze(self, **kwargs):
            return analysis

    execution = DocumentProcessingExecutionService(
        tmp_db,
        analysis_service=ReusingAnalysisService(),
    )
    queue = JobService(tmp_db)
    original_complete = queue.complete
    failed_ack = False

    def fail_once(*args, **kwargs):
        nonlocal failed_ack
        if not failed_ack and args[2] == "succeeded":
            failed_ack = True
            raise RetryableJobFailure("simulated completion acknowledgement failure")
        return original_complete(*args, **kwargs)

    queue.complete = fail_once
    first_worker = WorkerProcess(
        tmp_db,
        execution.handlers(),
        worker_id="phase22-worker-1",
        queue=queue,
    )
    with pytest.raises(RetryableJobFailure, match="acknowledgement"):
        first_worker.run_once(now="2026-08-20T12:00:00Z")

    assert _count(tmp_db, "evidence_spans") == 1
    assert _count(tmp_db, "claims") == 1
    assert _count(tmp_db, "claim_evidence") == 1
    assert _count(tmp_db, "article_analysis_promotions") == 1

    assert JobService(tmp_db).get(job_row["id"])["status"] == "running"

    queue.recover_expired(now="2026-08-20T12:03:00Z")
    second_worker = WorkerProcess(
        tmp_db,
        execution.handlers(),
        worker_id="phase22-worker-2",
        queue=queue,
    )
    result = second_worker.run_once(now="2026-08-20T12:04:00Z")

    assert result["status"] == "succeeded"
    assert _count(tmp_db, "evidence_spans") == 1
    assert _count(tmp_db, "claims") == 1
    assert _count(tmp_db, "claim_evidence") == 1
    assert _count(tmp_db, "article_analysis_promotions") == 1


def test_logical_export_contains_phase22_trusted_lineage(tmp_db, tmp_path):
    analysis = _analysis(tmp_db, text="The agency released a UAP report.", excerpt="released a UAP report")
    ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])

    destination = export_logical(tmp_db, tmp_path / "phase22-export.jsonl")
    rows = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines()]
    by_table = {}
    for row in rows:
        if "table" in row:
            by_table.setdefault(row["table"], []).append(row["data"])

    assert by_table["article_analysis_promotions"]
    assert by_table["evidence_spans"][0]["verification_method"] == "exact_analyzed_slice_v1"
    assert by_table["evidence_spans"][0]["article_analysis_id"] == analysis["id"]
    assert by_table["claims"][0]["story_id"] is None
    assert by_table["claims"][0]["article_analysis_id"] == analysis["id"]
    assert by_table["article_analyses"][0]["input_content_hash"]
    assert by_table["claim_state_history"][0]["from_state"] is None
    assert by_table["claim_state_history"][0]["to_state"] == "pending"


def test_schema22_preserves_schema21_manual_evidence_and_child_links(tmp_db):
    import newsroom.migrations as migration_module

    conn = storage.connect(tmp_db)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        with storage.write_tx(conn):
            migration_module._ensure_ledger(conn)
            for version in range(1, 22):
                for statement in getattr(migration_module, f"MIGRATION_{version:04d}_STATEMENTS"):
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, "2026-08-20T12:00:00Z"),
                )
            conn.execute("INSERT INTO app_meta(key, value) VALUES ('schema_version', '21')")
            conn.execute("INSERT INTO app_meta(key, value) VALUES ('schema_seeded_at', '2026-08-20T12:00:00Z')")
            conn.execute(
                "INSERT INTO sources(id, name, slug, created_at, updated_at) VALUES ('src-preserve', 'Preserved', 'preserved', ?, ?)",
                ("2026-08-20T12:00:00Z", "2026-08-20T12:00:00Z"),
            )
            conn.execute(
                """INSERT INTO documents
                   (id, source_id, canonical_url, canonical_url_hash, title, title_normalized, first_seen_at, created_at)
                   VALUES ('doc-preserve', 'src-preserve', 'https://preserve.test/article', 'preserve-url', 'Preserved', 'preserved', ?, ?)""",
                ("2026-08-20T12:00:00Z", "2026-08-20T12:00:00Z"),
            )
            conn.execute(
                """INSERT INTO document_versions
                   (id, document_id, retrieved_at, content_hash, content_kind, created_at)
                   VALUES ('dv-preserve', 'doc-preserve', ?, 'preserve-content', 'excerpt', ?)""",
                ("2026-08-20T12:00:00Z", "2026-08-20T12:00:00Z"),
            )
            conn.execute(
                "INSERT INTO stories(id, created_at, updated_at) VALUES ('st-preserve', ?, ?)",
                ("2026-08-20T12:00:00Z", "2026-08-20T12:00:00Z"),
            )
            conn.execute(
                """INSERT INTO claims
                   (id, story_id, proposition, proposition_hash, created_at)
                   VALUES ('claim-preserve', 'st-preserve', 'Preserved claim', 'preserve-hash', ?)""",
                ("2026-08-20T12:00:00Z",),
            )
            conn.execute(
                """INSERT INTO evidence_spans
                   (id, document_version_id, excerpt, locator_type, locator_value, span_hash, created_at)
                   VALUES ('span-preserve', 'dv-preserve', 'Preserved excerpt', 'paragraph', '1', 'preserve-span', ?)""",
                ("2026-08-20T12:00:00Z",),
            )
            conn.execute(
                """INSERT INTO claim_evidence
                   (id, claim_id, evidence_span_id, relationship, created_at)
                   VALUES ('ce-preserve', 'claim-preserve', 'span-preserve', 'supports', ?)""",
                ("2026-08-20T12:00:00Z",),
            )
    finally:
        conn.close()

    result = apply_migrations(tmp_db)

    assert result.applied_versions == (22, 23, 24, 25)
    conn = storage.connect(tmp_db)
    try:
        span = conn.execute("SELECT * FROM evidence_spans WHERE id = 'span-preserve'").fetchone()
        assert span["verification_method"] is None
        assert conn.execute("SELECT evidence_span_id FROM claim_evidence WHERE id = 'ce-preserve'").fetchone()[0] == "span-preserve"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_exact_automatic_evidence_replay_reuses_existing_span(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    service = ArticleAnalysisPromotionService(tmp_db)
    first = service.promote(analysis["id"])
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analysis_promotions_immutable_delete")
            conn.execute("DELETE FROM article_analysis_promotions")
        original_span_id = conn.execute("SELECT id FROM evidence_spans").fetchone()[0]
    finally:
        conn.close()

    replay = service.promote(analysis["id"])

    assert replay["outcomes"][0]["claim_id"] == first["outcomes"][0]["claim_id"]
    assert replay["outcomes"][0]["evidence_span_ids"] == [original_span_id]
    assert _count(tmp_db, "evidence_spans") == 1


def test_incompatible_analysis_provenance_does_not_reuse_automatic_span(tmp_db):
    first_analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    first = ArticleAnalysisPromotionService(tmp_db).promote(first_analysis["id"])
    second_analysis = _variant_analysis(tmp_db, first_analysis)

    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analysis_promotions_immutable_delete")
            conn.execute("DELETE FROM article_analysis_promotions WHERE article_analysis_id = ?", (first_analysis["id"],))
    finally:
        conn.close()

    second = ArticleAnalysisPromotionService(tmp_db).promote(second_analysis["id"])

    assert second["outcomes"][0]["code"] == "verified"
    assert second["outcomes"][0]["evidence_span_ids"] != first["outcomes"][0]["evidence_span_ids"]
    assert _count(tmp_db, "evidence_spans") == 2


def test_database_rejects_automatic_evidence_without_verification_method(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn), pytest.raises(storage.sqlite3.IntegrityError, match="verified evidence"):
            conn.execute(
                """INSERT INTO evidence_spans
                   (id, document_version_id, excerpt, locator_type, locator_value, span_hash, created_at,
                    article_analysis_id, artifact_id, artifact_content_hash, view_content_hash,
                    view_kind, view_version, start_offset, end_offset, provenance_json)
                   VALUES (?, ?, ?, 'codepoint_offset', '0;3', ?, ?, ?, ?, ?, ?, 'artifact', ?, 0, 3, ?)""",
                (
                    "span-malformed-method",
                    analysis["document_version_id"],
                    "The",
                    "malformed-span-hash",
                    "2026-08-20T12:00:00Z",
                    analysis["id"],
                    conn.execute("SELECT artifact_id FROM article_analyses WHERE id = ?", (analysis["id"],)).fetchone()[0],
                    conn.execute("SELECT normalized_content_hash FROM content_artifacts LIMIT 1").fetchone()[0],
                    conn.execute("SELECT normalized_content_hash FROM content_artifacts LIMIT 1").fetchone()[0],
                    "artifact_view_v1",
                    json.dumps({
                        "analysis_id": analysis["id"],
                        "candidate_claim_index": 0,
                        "candidate_excerpt_index": 0,
                    }),
                ),
            )
    finally:
        conn.close()


def test_database_rejects_automatic_evidence_with_mismatched_view_provenance(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn), pytest.raises(storage.sqlite3.IntegrityError, match="provenance"):
            conn.execute(
                """INSERT INTO evidence_spans
                   (id, document_version_id, excerpt, locator_type, locator_value, span_hash, created_at,
                    article_analysis_id, artifact_id, artifact_content_hash, view_content_hash,
                    view_kind, view_version, start_offset, end_offset,
                    verification_method, provenance_json)
                   VALUES (?, ?, ?, 'codepoint_offset', '11;32', ?, ?, ?, ?, ?, ?, 'artifact', ?, 11, 32, ?, ?)""",
                (
                    "span-mismatched-view",
                    analysis["document_version_id"],
                    "released a UAP report",
                    "mismatched-view-span-hash",
                    "2026-08-20T12:00:00Z",
                    analysis["id"],
                    analysis["artifact_id"],
                    analysis["normalized_content_hash"],
                    "wrong-view-content-hash",
                    "wrong_view_v1",
                    "exact_analyzed_slice_v1",
                    json.dumps(
                        {
                            "analysis_id": analysis["id"],
                            "candidate_claim_index": 0,
                            "candidate_excerpt_index": 0,
                        },
                    ),
                ),
            )
    finally:
        conn.close()


def test_database_rejects_non_pending_automatic_claim_insert(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn), pytest.raises(storage.sqlite3.IntegrityError, match="pending"):
            conn.execute(
                """INSERT INTO claims
                   (id, story_id, proposition, proposition_hash, importance, state,
                    article_analysis_id, candidate_claim_index, created_at)
                   VALUES ('claim-non-pending', NULL, 'The agency released a UAP report.', 'claim-hash',
                           'relevant', 'supported', ?, 0, ?)""",
                (analysis["id"], "2026-08-20T12:00:00Z"),
            )
    finally:
        conn.close()


def test_automatic_claim_cannot_link_manual_evidence(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    claim_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["claim_id"]
    manual = EvidenceService(tmp_db).create_evidence_span(
        analysis["document_version_id"],
        {"excerpt": "released a UAP report", "locator_type": "paragraph", "locator_value": "1"},
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn), pytest.raises(storage.sqlite3.IntegrityError, match="verified evidence"):
            conn.execute(
                """INSERT INTO claim_evidence
                   (id, claim_id, evidence_span_id, relationship, created_at)
                   VALUES ('ce-manual-on-auto', ?, ?, 'supports', ?)""",
                (claim_id, manual["id"], "2026-08-20T12:00:00Z"),
            )
    finally:
        conn.close()


def test_database_rejects_verified_promotion_without_trusted_graph(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn), pytest.raises(storage.sqlite3.IntegrityError, match="promotion"):
            conn.execute(
                """INSERT INTO article_analysis_promotions
                   (id, promotion_identity, article_analysis_id, candidate_claim_index,
                    outcome_code, claim_id, evidence_span_ids_json, created_at)
                   VALUES ('promo-malformed', 'identity-malformed', ?, 0, 'verified', NULL, '[]', ?)""",
                (analysis["id"], "2026-08-20T12:00:00Z"),
            )
    finally:
        conn.close()


def test_database_rejects_verified_promotion_without_claim_evidence_link(tmp_db):
    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report.",
        excerpt="released a UAP report",
    )
    promotion = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])
    outcome = promotion["outcomes"][0]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analysis_promotions_immutable_delete")
            conn.execute("DROP TRIGGER claim_evidence_immutable_delete")
            conn.execute("DELETE FROM article_analysis_promotions WHERE id = ?", (promotion["outcomes"][0]["id"],))
            conn.execute("DELETE FROM claim_evidence WHERE claim_id = ?", (outcome["claim_id"],))
        with storage.write_tx(conn), pytest.raises(storage.sqlite3.IntegrityError, match="promotion"):
            conn.execute(
                """INSERT INTO article_analysis_promotions
                   (id, promotion_identity, article_analysis_id, candidate_claim_index,
                    outcome_code, claim_id, evidence_span_ids_json, created_at)
                   VALUES ('promo-no-link', 'identity-no-link', ?, 0, 'verified', ?, ?, ?)""",
                (
                    analysis["id"],
                    outcome["claim_id"],
                    json.dumps(outcome["evidence_span_ids"]),
                    "2026-08-20T12:00:00Z",
                ),
            )
    finally:
        conn.close()
