from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from newsroom import storage
from newsroom.acquisition import AcquisitionBlocked, AcquisitionPolicy, UrllibHttpTransport
from newsroom.ai import AIProviderError, AIDisabled, ArticleAnalysisRequest
from newsroom.article_analysis import (
    AnalysisProviderConfig,
    ArticleAnalysisService,
    analysis_identity_hash,
    build_analysis_input,
    canonical_feed_analysis_view,
)
from newsroom.content_artifacts import ContentArtifactService, normalized_text_hash
from newsroom.domain import CoreService, DomainValidation
from newsroom.document_processing import DocumentProcessingExecutionService, enqueue_document_version_processing_tx
from newsroom.integrity import check_database
from newsroom.jobs import BudgetService, JobService
from newsroom.migrations import apply_migrations, migration_status
from newsroom.monitoring import (
    DocumentVersionRelevanceService,
    MonitorService,
    MonitoringPolicyService,
    RelevanceResult,
    RelevanceScope,
)
from newsroom.provenance import ProvenanceValidationError, validate_analysis_provenance


T0 = "2026-08-19T12:00:00Z"

VALID_OUTPUT: dict[str, Any] = {
    "summary": "The agency released a UAP report.",
    "key_developments": ["The agency released a UAP report."],
    "entities": [{"name": "Agency", "category": "organization"}],
    "dates": [],
    "locations": [],
    "significance": "The report matches the approved UAP scope.",
    "novelty": "Article-level observation only.",
    "candidate_claims": [{"index": 0, "proposition": "The agency released a UAP report."}],
    "candidate_evidence_excerpts": [
        {"candidate_claim_index": 0, "excerpt": "The agency released a UAP report."}
    ],
    "confidence": 0.9,
}


class CountingProvider:
    model_name = "test-paid-model"

    def __init__(self, *, gate: threading.Event | None = None, error: BaseException | None = None):
        self.calls = 0
        self.gate = gate
        self.error = error
        self.seen_invocation_states: list[str] = []

    def analyze(self, request: ArticleAnalysisRequest) -> dict[str, Any]:
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(timeout=5)
        if self.error is not None:
            raise self.error
        return dict(VALID_OUTPUT)


def _get(db: Path, sql: str, params: tuple[Any, ...] = ()) -> storage.sqlite3.Row | None:
    conn = storage.connect(db)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _disable_relevance_immutability_for_corruption_test(db: Path) -> None:
    """Allow legacy validator tests to manufacture impossible restored state."""
    raw = sqlite3.connect(str(db))
    try:
        raw.execute("DROP TRIGGER document_version_relevance_immutable_update")
        raw.commit()
    finally:
        raw.close()


def _setup_analysis(db: Path, *, suffix: str = "") -> dict[str, Any]:
    apply_migrations(db)
    core = CoreService(db)
    label = suffix or "a"
    category = core.create_category({"slug": f"science-{label}", "name": f"Science {label}"})
    topic = core.create_topic({"category_id": category["id"], "slug": f"uap-{label}", "name": "UAP"})
    core.create_vocabulary(topic["id"], {"term": "UAP", "term_type": "include"})
    source = core.create_source(
        {"name": f"Example {label}", "slug": f"example-{label}", "homepage_url": "https://example.test"}
    )
    policy = MonitoringPolicyService(db).create(
        {
            "name": f"Example policy {label}",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        }
    )
    monitor = MonitorService(db).create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "need_type": "topic",
            "need_id": topic["id"],
            "next_check_at": T0,
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": f"https://example.test/uap-{label}",
            "title": "UAP report",
        }
    )
    artifact = ContentArtifactService(db).create(
        normalized_text="The agency released a UAP report.",
        content_kind="visible_text",
    )
    version_id = f"dv_phase21h_{label}"
    now = T0
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO document_versions
                    (id, document_id, retrieved_at, content_hash, content_kind,
                     artifact_id, normalized_json, created_at)
                VALUES (?, ?, ?, ?, 'full_text', ?, ?, ?)
                """,
                (
                    version_id,
                    document["id"],
                    now,
                    "raw-phase21h",
                    artifact["id"],
                    json.dumps({"normalized_content_hash": artifact["normalized_content_hash"]}),
                    now,
                ),
            )
    finally:
        conn.close()
    relevance = DocumentVersionRelevanceService(db).persist_decision(
        job_id=None,
        document_version_id=version_id,
        monitor_id=monitor["id"],
        scope_version=1,
        scope=MonitorService(db).scope_at_version(monitor["id"], 1),
        result=RelevanceResult(True, "exact", 1.0, ("UAP",), "match"),
        observed_at=T0,
    )
    return {
        "core": core,
        "topic": topic,
        "source": source,
        "policy": policy,
        "monitor": monitor,
        "document": document,
        "artifact": artifact,
        "version_id": version_id,
        "relevance": relevance,
    }


def _service(db: Path, provider: CountingProvider, *, max_calls: int = 10, max_cost: float = 10.0):
    return ArticleAnalysisService(
        db,
        config=AnalysisProviderConfig(
            provider="openai",
            api_key="test-key",
            model="test-paid-model",
            max_paid_calls=max_calls,
            max_paid_cost_usd=max_cost,
            request_cost_usd=0.01,
        ),
        paid_provider_factory=lambda _config: provider,
    )


def _analyze(service: ArticleAnalysisService, fixture: dict[str, Any], *, job_id: str | None = None):
    relevance = fixture["relevance"]
    return service.analyze(
        document_version_id=fixture["version_id"],
        relevance={
            "status": "evaluated",
            "relevant": True,
            "relevance_id": relevance["id"],
            "monitor_id": fixture["monitor"]["id"],
            "scope_version": relevance["scope_version"],
        },
        content=ContentArtifactService(service.db_path).load_normalized_content(fixture["version_id"]),
        job_id=job_id,
    )


def _make_retryable_paid_invocation(
    db: Path,
    fixture: dict[str, Any],
    *,
    job_id: str | None = None,
) -> None:
    def explode(_config):
        raise RuntimeError("provider construction failed")

    service = ArticleAnalysisService(
        db,
        config=AnalysisProviderConfig(
            provider="openai",
            api_key="test-key",
            model="test-paid-model",
            max_paid_calls=10,
            max_paid_cost_usd=10.0,
            request_cost_usd=0.01,
        ),
        paid_provider_factory=explode,
    )
    with pytest.raises(AIProviderError):
        _analyze(service, fixture, job_id=job_id)
    assert _get(db, "SELECT state FROM analysis_invocations")[0] == "retryable"


def _assert_retryable_reauthorization_blocks(
    db: Path,
    fixture: dict[str, Any],
    *,
    job_id: str | None = None,
) -> None:
    provider = CountingProvider()
    with pytest.raises(AIDisabled):
        _analyze(_service(db, provider), fixture, job_id=job_id)
    assert provider.calls == 0
    assert _get(db, "SELECT state FROM analysis_invocations")[0] == "retryable"


def _attach_automatic_processing_job(db: Path, fixture: dict[str, Any], *, key: str) -> dict[str, Any]:
    job = JobService(db).enqueue(
        "document_version_process",
        {
            "document_version_id": fixture["version_id"],
            "document_id": fixture["document"]["id"],
            "source_id": fixture["source"]["id"],
            "monitor_id": fixture["monitor"]["id"],
            "scope_version": 1,
        },
        document_version_id=fixture["version_id"],
        idempotency_key=key,
    )
    _disable_relevance_immutability_for_corruption_test(db)
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET job_id = ? WHERE id = ?",
                (job["id"], fixture["relevance"]["id"]),
            )
    finally:
        conn.close()
    return job


def _insert_version_for_future_processing(db: Path, fixture: dict[str, Any], identifier: str) -> str:
    artifact = ContentArtifactService(db).create(
        normalized_text="The agency released a future UAP report.",
        content_kind="visible_text",
    )
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO document_versions
                    (id, document_id, retrieved_at, content_hash, content_kind,
                     artifact_id, normalized_json, created_at)
                VALUES (?, ?, ?, ?, 'full_text', ?, ?, ?)
                """,
                (
                    identifier,
                    fixture["document"]["id"],
                    T0,
                    "raw-future-phase21h1",
                    artifact["id"],
                    json.dumps({"normalized_content_hash": artifact["normalized_content_hash"]}),
                    T0,
                ),
            )
    finally:
        conn.close()
    return identifier


def test_phase21h_migration_is_additive_and_idempotent(tmp_db):
    assert apply_migrations(tmp_db).current_version == 36
    assert apply_migrations(tmp_db).applied_versions == ()
    assert migration_status(tmp_db)[-1] == 36
    conn = storage.connect(tmp_db)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        columns = {row[1] for row in conn.execute("PRAGMA table_info(provider_usage)")}
        analysis_columns = {row[1] for row in conn.execute("PRAGMA table_info(article_analyses)")}
    finally:
        conn.close()
    assert "analysis_invocations" in tables
    assert "invocation_id" in columns
    assert {"input_view_version", "input_content_hash", "analyzed_content_hash", "invocation_id"} <= analysis_columns


def test_paid_reservation_exists_before_call_and_limit_blocks_next_analysis(tmp_db):
    fixture_a = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    BudgetService(tmp_db).configure_limit("global", None, "lifetime", "paid_requests", 1)
    BudgetService(tmp_db).configure_limit("global", None, "lifetime", "usd", 0.01)
    provider = CountingProvider()

    class InspectingProvider(CountingProvider):
        def analyze(self, request):
            row = _get(tmp_db, "SELECT state FROM analysis_invocations")
            assert row is not None and row["state"] == "running"
            return super().analyze(request)

    provider = InspectingProvider()
    first = _analyze(_service(tmp_db, provider), fixture_a)
    assert first["paid"] is True
    assert provider.calls == 1

    fixture_b = _setup_analysis(tmp_db, suffix="b")
    with pytest.raises(AIDisabled):
        _analyze(_service(tmp_db, provider), fixture_b)
    assert provider.calls == 1
    assert _get(tmp_db, "SELECT COUNT(*) FROM analysis_invocations")[0] == 1


def test_competing_paid_workers_make_one_provider_call_and_one_row(tmp_db):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    gate = threading.Event()
    provider = CountingProvider(gate=gate)
    services = [_service(tmp_db, provider), _service(tmp_db, provider)]
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def run(service):
        try:
            results.append(_analyze(service, fixture))
        except BaseException as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(service,)) for service in services]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + 5
    while provider.calls < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    gate.set()
    for thread in threads:
        thread.join(timeout=10)
    assert not errors, errors
    assert provider.calls == 1
    assert len(results) == 2
    assert results[0]["id"] == results[1]["id"]
    assert _get(tmp_db, "SELECT COUNT(*) FROM article_analyses")[0] == 1
    assert _get(tmp_db, "SELECT COUNT(*) FROM analysis_invocations")[0] == 1


def test_concurrent_distinct_paid_analyses_honor_global_limit(tmp_db):
    fixture_a = _setup_analysis(tmp_db)
    fixture_b = _setup_analysis(tmp_db, suffix="b")
    BudgetService(tmp_db).set_paid_enabled(True)
    BudgetService(tmp_db).configure_limit("global", None, "lifetime", "paid_requests", 1)
    BudgetService(tmp_db).configure_limit("global", None, "lifetime", "usd", 0.01)
    provider = CountingProvider()
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def run(fixture):
        try:
            results.append(_analyze(_service(tmp_db, provider), fixture))
        except BaseException as exc:  # pragma: no cover - assertion below reports it
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(fixture,)) for fixture in (fixture_a, fixture_b)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert provider.calls == 1
    assert len(results) == 1
    assert len(errors) == 1 and isinstance(errors[0], AIDisabled)
    assert _get(tmp_db, "SELECT COUNT(*) FROM analysis_invocations")[0] == 1


def test_uncertain_paid_invocation_blocks_duplicate_until_explicit_release(tmp_db):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    provider = CountingProvider(error=TimeoutError("provider timeout"))
    with pytest.raises(Exception):
        _analyze(_service(tmp_db, provider), fixture)
    assert provider.calls == 1
    assert _get(tmp_db, "SELECT state FROM analysis_invocations")[0] == "uncertain"
    with pytest.raises(AIDisabled):
        _analyze(_service(tmp_db, provider), fixture)
    assert provider.calls == 1


def test_retryable_paid_reauthorization_rechecks_global_limit(tmp_db):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    _make_retryable_paid_invocation(tmp_db, fixture)
    BudgetService(tmp_db).configure_limit("global", None, "lifetime", "paid_requests", 0)
    _assert_retryable_reauthorization_blocks(tmp_db, fixture)


def test_retryable_paid_reauthorization_rechecks_policy_limit(tmp_db):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    _make_retryable_paid_invocation(tmp_db, fixture)
    BudgetService(tmp_db).configure_limit(
        "policy", fixture["policy"]["id"], "lifetime", "paid_requests", 0
    )
    _assert_retryable_reauthorization_blocks(tmp_db, fixture)


def test_retryable_paid_reauthorization_rechecks_job_limit(tmp_db):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    job = JobService(tmp_db).enqueue(
        "document_version_process",
        {
            "document_version_id": fixture["version_id"],
            "monitor_id": fixture["monitor"]["id"],
            "scope_version": 1,
        },
        document_version_id=fixture["version_id"],
        idempotency_key="phase21h1-job-budget",
    )
    _disable_relevance_immutability_for_corruption_test(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET job_id = ? WHERE id = ?",
                (job["id"], fixture["relevance"]["id"]),
            )
    finally:
        conn.close()
    _make_retryable_paid_invocation(tmp_db, fixture, job_id=job["id"])
    BudgetService(tmp_db).configure_limit("job", job["id"], "lifetime", "paid_requests", 0)
    _assert_retryable_reauthorization_blocks(tmp_db, fixture, job_id=job["id"])


def test_retryable_paid_reauthorization_rechecks_usd_limit(tmp_db):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    _make_retryable_paid_invocation(tmp_db, fixture)
    BudgetService(tmp_db).configure_limit("global", None, "lifetime", "usd", 0.0)
    _assert_retryable_reauthorization_blocks(tmp_db, fixture)


def test_retryable_paid_reauthorization_rechecks_paid_enabled(tmp_db):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    _make_retryable_paid_invocation(tmp_db, fixture)
    BudgetService(tmp_db).set_paid_enabled(False)
    _assert_retryable_reauthorization_blocks(tmp_db, fixture)


def test_automatic_provenance_bundle_is_eligible(tmp_db):
    fixture = _setup_analysis(tmp_db)
    job = _attach_automatic_processing_job(tmp_db, fixture, key="phase21h1-auto-valid")
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(_service(tmp_db, CountingProvider()), fixture, job_id=job["id"])
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["eligible_for_automatic_promotion"] is True
    assert bundle["provenance_class"] == "automatic"
    assert bundle["job"]["id"] == job["id"]


def test_standalone_analysis_is_not_eligible_for_automatic_promotion(tmp_db):
    fixture = _setup_analysis(tmp_db)
    analysis = _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["eligible_for_automatic_promotion"] is False
    assert bundle["provenance_class"] == "standalone"


def test_automatic_analysis_missing_job_provenance_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    _attach_automatic_processing_job(tmp_db, fixture, key="phase21h1-auto-missing-job")
    with pytest.raises(ProvenanceValidationError):
        _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)


def test_automatic_analysis_wrong_job_provenance_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    job = _attach_automatic_processing_job(tmp_db, fixture, key="phase21h1-auto-wrong-job")
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(_service(tmp_db, CountingProvider()), fixture, job_id=job["id"])
    other_job = JobService(tmp_db).enqueue("unrelated", {}, idempotency_key="phase21h1-unrelated-job")
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET job_id = ? WHERE id = ?",
                (other_job["id"], fixture["relevance"]["id"]),
            )
    finally:
        conn.close()
    with pytest.raises(ProvenanceValidationError):
        validate_analysis_provenance(tmp_db, analysis["id"])


def test_historical_analysis_remains_valid_after_need_deletion(tmp_db):
    fixture = _setup_analysis(tmp_db)
    analysis = _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)
    CoreService(tmp_db).delete_topic(fixture["topic"]["id"])
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["current_need_available"] is False
    assert bundle["current_need_status"] == "deleted"


def test_future_processing_becomes_acquisition_only_after_need_deletion(tmp_db):
    fixture = _setup_analysis(tmp_db)
    CoreService(tmp_db).delete_topic(fixture["topic"]["id"])
    version_id = _insert_version_for_future_processing(tmp_db, fixture, "dv_phase21h1_future")
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            enqueue_document_version_processing_tx(
                conn,
                version_id=version_id,
                monitor_id=fixture["monitor"]["id"],
            )
            row = conn.execute(
                "SELECT * FROM jobs WHERE document_version_id = ?",
                (version_id,),
            ).fetchone()
    finally:
        conn.close()
    assert row is not None
    payload = json.loads(row["payload_json"])
    assert "scope_version" not in payload
    result = DocumentProcessingExecutionService(tmp_db).handle({**dict(row), "payload": payload})
    assert result["relevance"]["status"] == "not_applicable"


def test_provenance_validator_rejects_cross_reference_corruption(tmp_db):
    fixture = _setup_analysis(tmp_db)
    service = _service(tmp_db, CountingProvider())
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(service, fixture)
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["analysis"]["id"] == analysis["id"]

    other = _setup_analysis(tmp_db, suffix="b")
    _disable_relevance_immutability_for_corruption_test(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET monitor_id = ? WHERE id = ?",
                (other["monitor"]["id"], fixture["relevance"]["id"]),
            )
    finally:
        conn.close()
    with pytest.raises(ProvenanceValidationError):
        validate_analysis_provenance(tmp_db, analysis["id"])


def test_integrity_detects_invalid_polymorphic_monitor_need(tmp_db):
    fixture = _setup_analysis(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE monitors SET need_type = 'subject', need_id = 'sub_missing' WHERE id = ?",
                (fixture["monitor"]["id"],),
            )
    finally:
        conn.close()
    report = check_database(tmp_db)
    assert any(issue.code == "invalid_monitor_need_reference" for issue in report.issues)


def test_subject_edit_refreshes_only_future_scope_versions(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    subject = core.create_subject({"canonical_name": "Original", "subject_type": "agency"})
    source = core.create_source({"name": "Source", "slug": "scope-source", "homepage_url": "https://example.test"})
    policy = MonitoringPolicyService(tmp_db).create({
        "name": "Policy", "allowed_channels": ["direct_http"],
        "base_cadence_seconds": 60, "min_cadence_seconds": 30, "max_cadence_seconds": 300,
    })
    monitor = MonitorService(tmp_db).create({
        "target_type": "source", "target_id": source["id"], "policy_id": policy["id"],
        "need_type": "subject", "need_id": subject["id"],
    })
    old_scope = MonitorService(tmp_db).scope_at_version(monitor["id"], 1)
    core.add_subject_alias(subject["id"], "Updated")
    new_scope = MonitorService(tmp_db).scope_at_version(monitor["id"], 2)
    assert old_scope.vocabulary == ()
    assert "Updated" in new_scope.vocabulary


def test_research_question_edit_refreshes_scope(tmp_db):
    apply_migrations(tmp_db)
    from newsroom.research_questions import ResearchQuestionService

    question = ResearchQuestionService(tmp_db).create({"question": "Original question"})
    source = CoreService(tmp_db).create_source({"name": "Source", "slug": "rq-source", "homepage_url": "https://example.test"})
    policy = MonitoringPolicyService(tmp_db).create({
        "name": "Policy", "allowed_channels": ["direct_http"],
        "base_cadence_seconds": 60, "min_cadence_seconds": 30, "max_cadence_seconds": 300,
    })
    monitor = MonitorService(tmp_db).create({
        "target_type": "source", "target_id": source["id"], "policy_id": policy["id"],
        "need_type": "research_question", "need_id": question["id"],
    })
    ResearchQuestionService(tmp_db).update(question["id"], {"question": "Updated question"})
    scope = MonitorService(tmp_db).scope_at_version(monitor["id"], 2)
    assert scope.exact_terms == ("Updated question",)


def test_peer_address_rebinding_is_blocked_after_validated_dns(monkeypatch):
    policy = AcquisitionPolicy()

    def public_dns(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    class FakeSocket:
        def getpeername(self):
            return ("127.0.0.1", 443)

        def close(self):
            return None

    monkeypatch.setattr(socket, "getaddrinfo", public_dns)
    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())
    with pytest.raises(AcquisitionBlocked, match="connected address"):
        UrllibHttpTransport()._open_connection("https", "example.test", 443, "93.184.216.34", policy)


def test_stable_public_peer_is_allowed_by_pinned_connection(monkeypatch):
    policy = AcquisitionPolicy()

    class FakeSocket:
        def getpeername(self):
            return ("93.184.216.34", 443)

        def close(self):
            return None

    monkeypatch.setattr(socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())
    connection = UrllibHttpTransport()._open_connection("http", "example.test", 80, "93.184.216.34", policy)
    assert connection.sock.getpeername()[0] == "93.184.216.34"
    connection.close()


# ---------------------------------------------------------------------------
# Phase 21H.1 — historical provenance and automatic processing-Job provenance
# ---------------------------------------------------------------------------


def _insert_orphan_analysis_row(
    db: Path,
    fixture: dict[str, Any],
    *,
    analysis_id: str,
    document_version_id: str,
    monitor_id: str | None = None,
    relevance_id: str | None = None,
) -> None:
    """Raw-insert an article_analyses row with FK checks disabled.

    Used only to prove the read-only validator rejects impossible chains;
    the production writer can never produce these rows.
    """
    relevance_id = relevance_id or fixture["relevance"]["id"]
    monitor_id = monitor_id or fixture["monitor"]["id"]
    raw = sqlite3.connect(str(db))
    try:
        raw.execute("PRAGMA foreign_keys = OFF")
        raw.execute(
            """
            INSERT INTO article_analyses
                (id, document_version_id, relevance_id, monitor_id, scope_version,
                 artifact_id, normalized_content_hash, identity_hash, schema_version,
                 prompt_version, provider, model, paid, confidence, input_char_count,
                 analyzed_char_count, truncated, result_json, created_at)
            VALUES (?, ?, ?, ?, 1, ?, 'hash-orphan', 'identity-orphan', 'article_analysis_schema_v1',
                    'article_analysis_v1', 'local', 'local', 0, 0.5, 10, 10, 0, ?, ?)
            """,
            (
                analysis_id,
                document_version_id,
                relevance_id,
                monitor_id,
                fixture["artifact"]["id"],
                json.dumps(VALID_OUTPUT),
                T0,
            ),
        )
        raw.commit()
    finally:
        raw.close()


def test_automatic_analysis_missing_document_version_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    _insert_orphan_analysis_row(
        tmp_db, fixture, analysis_id="ana_21h1_orphan_version", document_version_id="dv_missing_21h1"
    )
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, "ana_21h1_orphan_version")
    assert any(issue.startswith("orphan_analysis_version") for issue in excinfo.value.issues)


def test_automatic_analysis_wrong_document_version_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    other = _setup_analysis(tmp_db, suffix="b")
    analysis = _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)
    _disable_relevance_immutability_for_corruption_test(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET document_version_id = ? WHERE id = ?",
                (other["version_id"], fixture["relevance"]["id"]),
            )
    finally:
        conn.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith("analysis_relevance_document_version_mismatch") for issue in excinfo.value.issues)


def test_analysis_missing_monitor_provenance_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    _insert_orphan_analysis_row(
        tmp_db,
        fixture,
        analysis_id="ana_21h1_orphan_monitor",
        document_version_id=fixture["version_id"],
        monitor_id="mon_missing_21h1",
    )
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, "ana_21h1_orphan_monitor")
    assert any(issue.startswith("orphan_analysis_monitor") for issue in excinfo.value.issues)


def test_automatic_analysis_wrong_monitor_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    other = _setup_analysis(tmp_db, suffix="b")
    analysis = _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)
    _disable_relevance_immutability_for_corruption_test(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET monitor_id = ? WHERE id = ?",
                (other["monitor"]["id"], fixture["relevance"]["id"]),
            )
    finally:
        conn.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith("analysis_relevance_monitor_mismatch") for issue in excinfo.value.issues)


def test_automatic_analysis_wrong_scope_version_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    analysis = _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)
    _disable_relevance_immutability_for_corruption_test(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET scope_version = 2 WHERE id = ?",
                (fixture["relevance"]["id"],),
            )
    finally:
        conn.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith("analysis_relevance_scope_mismatch") for issue in excinfo.value.issues)


def test_automatic_analysis_scope_snapshot_mismatch_is_rejected(tmp_db):
    fixture = _setup_analysis(tmp_db)
    analysis = _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)
    _disable_relevance_immutability_for_corruption_test(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE document_version_relevance SET scope_json = ? WHERE id = ?",
                (
                    json.dumps({"exact_terms": ["NOT-THE-PINNED-SNAPSHOT"], "algorithm": "tampered"}),
                    fixture["relevance"]["id"],
                ),
            )
    finally:
        conn.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith("relevance_scope_snapshot_mismatch") for issue in excinfo.value.issues)


def test_automatic_local_analysis_is_eligible_for_promotion(tmp_db):
    fixture = _setup_analysis(tmp_db)
    job = _attach_automatic_processing_job(tmp_db, fixture, key="phase21h1-auto-local")
    analysis = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")),
        fixture,
        job_id=job["id"],
    )
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["provenance_class"] == "automatic"
    assert bundle["eligible_for_automatic_promotion"] is True
    assert bundle["analysis"]["job_id"] == job["id"]


def test_standalone_analysis_rejects_claimed_job(tmp_db):
    fixture = _setup_analysis(tmp_db)
    job = JobService(tmp_db).enqueue(
        "document_version_process",
        {
            "document_version_id": fixture["version_id"],
            "monitor_id": fixture["monitor"]["id"],
            "scope_version": 1,
        },
        document_version_id=fixture["version_id"],
        idempotency_key="phase21h1-unrelated-claim",
    )
    service = ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local"))
    with pytest.raises(ProvenanceValidationError):
        _analyze(service, fixture, job_id=job["id"])


def test_analysis_rejects_non_processing_job_claim(tmp_db):
    fixture = _setup_analysis(tmp_db)
    _attach_automatic_processing_job(tmp_db, fixture, key="phase21h1-wrong-type-claim")
    other_job = JobService(tmp_db).enqueue("unrelated", {}, idempotency_key="phase21h1-wrong-type-job")
    service = ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local"))
    with pytest.raises(ProvenanceValidationError):
        _analyze(service, fixture, job_id=other_job["id"])


def test_analysis_job_must_own_the_document_version(tmp_db):
    fixture = _setup_analysis(tmp_db)
    _attach_automatic_processing_job(tmp_db, fixture, key="phase21h1-other-version-claim")
    other = _setup_analysis(tmp_db, suffix="b")
    other_job = JobService(tmp_db).enqueue(
        "document_version_process",
        {
            "document_version_id": other["version_id"],
            "monitor_id": other["monitor"]["id"],
            "scope_version": 1,
        },
        document_version_id=other["version_id"],
        idempotency_key="phase21h1-other-version-job",
    )
    service = ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local"))
    with pytest.raises(ProvenanceValidationError):
        _analyze(service, fixture, job_id=other_job["id"])


def test_historical_analysis_remains_valid_after_need_disabled(tmp_db):
    fixture = _setup_analysis(tmp_db)
    analysis = _analyze(ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")), fixture)
    CoreService(tmp_db).delete_topic(fixture["topic"]["id"])
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["current_need_available"] is False
    assert bundle["current_need_status"] == "deleted"
    assert bundle["provenance_class"] == "standalone"
    # The pinned historical scope snapshot is unchanged.
    scope_history = _get(
        tmp_db,
        "SELECT scope_json FROM monitor_scope_history WHERE monitor_id = ? AND version = 1",
        (fixture["monitor"]["id"],),
    )
    assert scope_history is not None
    assert "UAP" in scope_history["scope_json"]


def test_automatic_analysis_eligibility_survives_need_deletion(tmp_db):
    fixture = _setup_analysis(tmp_db)
    job = _attach_automatic_processing_job(tmp_db, fixture, key="phase21h1-auto-after-delete")
    analysis = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")),
        fixture,
        job_id=job["id"],
    )
    CoreService(tmp_db).delete_topic(fixture["topic"]["id"])
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["current_need_available"] is False
    assert bundle["current_need_status"] == "deleted"
    # Eligibility is judged on the historical chain, not the current need.
    assert bundle["provenance_class"] == "automatic"
    assert bundle["eligible_for_automatic_promotion"] is True


# ---------------------------------------------------------------------------
# Phase 21H.2 — exact input identity and immutable pre-evidence provenance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "summary", "expected"),
    (
        ("Title", "Summary", "Title\nSummary"),
        ("Title", "", "Title\n"),
        ("", "Summary", "\nSummary"),
        ("", "", "\n"),
        ("  Café 🛰️  ", " summary  text ", "  Café 🛰️  \n summary  text "),
        ("Line one\nLine two", "Summary\ncontinued", "Line one\nLine two\nSummary\ncontinued"),
    ),
)
def test_feed_analysis_view_is_exact_title_newline_summary(title, summary, expected):
    metadata = {"title": title, "summary": summary, "url": "https://example.test"}
    assert canonical_feed_analysis_view(metadata) == expected
    if title or summary:
        raw = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        contract = build_analysis_input(
            {"content_kind": "feed_metadata", "normalized_text": raw},
            10_000,
        )
        assert contract.text == expected
        assert contract.analyzed_text == expected
        assert contract.view_version == "feed_entry_projection_v1"
        assert contract.input_content_hash == hashlib.sha256(expected.encode("utf-8")).hexdigest()


def test_empty_feed_projection_fails_closed():
    assert canonical_feed_analysis_view({"title": "", "summary": ""}) == "\n"
    with pytest.raises(DomainValidation, match="artifact text is empty"):
        build_analysis_input(
            {"content_kind": "feed_metadata", "normalized_text": '{"title":"","summary":"","url":"https://example.test"}'},
            10_000,
        )


def test_feed_artifact_and_analysis_view_hashes_are_independent(tmp_db):
    fixture = _setup_analysis(tmp_db)
    metadata = {
        "published_at": "2026-08-20T12:00:00Z",
        "summary": "Line one\nLine two",
        "title": "  UAP report ☄  ",
        "url": "https://example.test/uap-feed",
    }
    persisted_json = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    artifact = ContentArtifactService(tmp_db).create(
        normalized_text=persisted_json,
        content_kind="feed_metadata",
    )
    version_id = "dv_phase21h_feed_hash_domains"
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO document_versions
                    (id, document_id, retrieved_at, content_hash, content_kind,
                     artifact_id, normalized_json, created_at)
                VALUES (?, ?, ?, ?, 'metadata', ?, ?, ?)
                """,
                (
                    version_id,
                    fixture["document"]["id"],
                    T0,
                    artifact["normalized_content_hash"],
                    artifact["id"],
                    persisted_json,
                    T0,
                ),
            )
    finally:
        conn.close()
    fixture["version_id"] = version_id
    fixture["artifact"] = artifact
    fixture["relevance"] = DocumentVersionRelevanceService(tmp_db).persist_decision(
        job_id=None,
        document_version_id=version_id,
        monitor_id=fixture["monitor"]["id"],
        scope_version=1,
        scope=MonitorService(tmp_db).scope_at_version(fixture["monitor"]["id"], 1),
        result=RelevanceResult(True, "exact", 1.0, ("UAP",), "match"),
        observed_at=T0,
    )
    job = _attach_automatic_processing_job(tmp_db, fixture, key="feed-hash-domains")
    analysis = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")),
        fixture,
        job_id=job["id"],
    )

    persisted_artifact = ContentArtifactService(tmp_db).verify(artifact["id"])
    view = canonical_feed_analysis_view(json.loads(persisted_artifact["normalized_text"]))
    artifact_hash = normalized_text_hash(persisted_artifact["normalized_text"])
    view_hash = normalized_text_hash(view)

    assert artifact_hash == persisted_artifact["normalized_content_hash"]
    assert view == "  UAP report ☄  \nLine one\nLine two"
    assert view_hash == analysis["input_content_hash"]
    assert persisted_artifact["normalized_text"] != view
    assert artifact_hash != view_hash
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["eligible_for_automatic_promotion"] is True
    assert bundle["artifact"]["normalized_content_hash"] == artifact_hash
    assert bundle["analysis"]["input_content_hash"] == view_hash


def test_analysis_identity_changes_with_analyzed_slice():
    common = {
        "document_version_id": "dv",
        "relevance_id": "rel",
        "scope_version": 1,
        "schema_version": "schema",
        "prompt_version": "prompt",
        "provider": "local",
        "model": "local",
        "artifact_id": "art",
        "normalized_content_hash": "artifact-hash",
        "input_view_version": "artifact_norm_v1",
        "input_content_hash": "full-input-hash",
    }
    assert analysis_identity_hash(**common, analyzed_content_hash="slice-a") != analysis_identity_hash(
        **common, analyzed_content_hash="slice-b"
    )


def test_analysis_identity_reuses_same_slice_across_different_limits(tmp_db):
    fixture = _setup_analysis(tmp_db)
    first = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local", max_input_chars=100)),
        fixture,
    )
    second = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local", max_input_chars=200)),
        fixture,
    )
    assert first["analyzed_content_hash"] == second["analyzed_content_hash"]
    assert first["identity_hash"] == second["identity_hash"]
    assert first["id"] == second["id"]
    assert _get(tmp_db, "SELECT COUNT(*) FROM article_analyses")[0] == 1


def test_analysis_identity_changes_when_different_limits_change_the_slice(tmp_db):
    fixture = _setup_analysis(tmp_db)
    first = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local", max_input_chars=10)),
        fixture,
    )
    second = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local", max_input_chars=20)),
        fixture,
    )
    assert first["analyzed_content_hash"] != second["analyzed_content_hash"]
    assert first["identity_hash"] != second["identity_hash"]
    assert first["id"] != second["id"]
    assert _get(tmp_db, "SELECT COUNT(*) FROM article_analyses")[0] == 2


def test_relevance_rows_are_database_immutable(tmp_db):
    fixture = _setup_analysis(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="relevance is immutable"):
            with storage.write_tx(conn):
                conn.execute(
                    "UPDATE document_version_relevance SET reason = 'tampered' WHERE id = ?",
                    (fixture["relevance"]["id"],),
                )
        with pytest.raises(sqlite3.IntegrityError, match="relevance is immutable"):
            with storage.write_tx(conn):
                conn.execute(
                    "DELETE FROM document_version_relevance WHERE id = ?",
                    (fixture["relevance"]["id"],),
                )
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("assignment", "expected_issue"),
    (
        ("input_content_hash = 'tampered'", "analysis_input_hash_mismatch"),
        ("input_char_count = input_char_count + 1", "analysis_input_length_mismatch"),
        ("analyzed_char_count = analyzed_char_count - 1", "analysis_slice_hash_mismatch"),
        ("analyzed_char_count = input_char_count + 1", "analysis_input_bounds_invalid"),
        ("truncated = 1", "analysis_truncation_mismatch"),
        (
            "analyzed_char_count = analyzed_char_count - 1, truncated = 0",
            "analysis_truncation_mismatch",
        ),
        ("analyzed_content_hash = 'tampered'", "analysis_slice_hash_mismatch"),
    ),
)
def test_provenance_rejects_tampered_analysis_input_contract(
    tmp_db, assignment, expected_issue
):
    fixture = _setup_analysis(tmp_db)
    analysis = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")),
        fixture,
    )
    raw = sqlite3.connect(str(tmp_db))
    try:
        raw.execute("DROP TRIGGER article_analyses_immutable_update")
        raw.execute(
            f"UPDATE article_analyses SET {assignment} WHERE id = ?",
            (analysis["id"],),
        )
        raw.commit()
    finally:
        raw.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith(expected_issue) for issue in excinfo.value.issues)
    assert _get(tmp_db, "SELECT COUNT(*) FROM evidence_spans")[0] == 0
    assert _get(tmp_db, "SELECT COUNT(*) FROM claims")[0] == 0


@pytest.mark.parametrize("state", ("running", "uncertain", "failed_terminal"))
def test_paid_analysis_rejects_non_succeeded_invocation_states(tmp_db, state):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(_service(tmp_db, CountingProvider()), fixture)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE analysis_invocations SET state = ? WHERE id = ?",
                (state, analysis["invocation_id"]),
            )
    finally:
        conn.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith("analysis_invocation_not_succeeded") for issue in excinfo.value.issues)


@pytest.mark.parametrize(
    ("assignment", "params"),
    (
        ("invocation_id = NULL", ()),
        ("invocation_id = ?", ("inv_missing",)),
    ),
)
def test_paid_analysis_rejects_missing_invocation_linkage(tmp_db, assignment, params):
    fixture = _setup_analysis(tmp_db)
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(_service(tmp_db, CountingProvider()), fixture)
    raw = sqlite3.connect(str(tmp_db))
    try:
        raw.execute("DROP TRIGGER article_analyses_immutable_update")
        raw.execute(
            f"UPDATE article_analyses SET {assignment} WHERE id = ?",
            (*params, analysis["id"]),
        )
        raw.commit()
    finally:
        raw.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith("missing_analysis_invocation") for issue in excinfo.value.issues)


@pytest.mark.parametrize(
    "assignment",
    (
        "identity_hash = 'wrong-identity'",
        "document_version_id = 'wrong-version'",
        "relevance_id = 'wrong-relevance'",
        "monitor_id = 'wrong-monitor'",
        "job_id = 'wrong-job'",
    ),
)
def test_paid_analysis_rejects_mismatched_invocation_provenance(tmp_db, assignment):
    fixture = _setup_analysis(tmp_db)
    job = _attach_automatic_processing_job(tmp_db, fixture, key=f"paid-mismatch-{assignment}")
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(_service(tmp_db, CountingProvider()), fixture, job_id=job["id"])
    raw = sqlite3.connect(str(tmp_db))
    try:
        raw.execute(
            f"UPDATE analysis_invocations SET {assignment} WHERE id = ?",
            (analysis["invocation_id"],),
        )
        raw.commit()
    finally:
        raw.close()
    with pytest.raises(ProvenanceValidationError) as excinfo:
        validate_analysis_provenance(tmp_db, analysis["id"])
    assert any(issue.startswith("analysis_invocation_mismatch") for issue in excinfo.value.issues)


def test_paid_succeeded_matching_invocation_is_automatically_eligible(tmp_db):
    fixture = _setup_analysis(tmp_db)
    job = _attach_automatic_processing_job(tmp_db, fixture, key="paid-valid-v2")
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(_service(tmp_db, CountingProvider()), fixture, job_id=job["id"])
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    usage = _get(
        tmp_db,
        "SELECT * FROM provider_usage WHERE invocation_id = ?",
        (analysis["invocation_id"],),
    )
    assert bundle["eligible_for_automatic_promotion"] is True
    assert bundle["invocation"]["state"] == "succeeded"
    assert usage is not None
    assert usage["request_type"] == "ai:paid"
    assert json.loads(usage["outcome"])["route"] == "paid"


def test_legacy_analysis_remains_readable_but_is_not_automatically_eligible(tmp_db):
    fixture = _setup_analysis(tmp_db)
    job = _attach_automatic_processing_job(tmp_db, fixture, key="legacy-v1-analysis")
    analysis = _analyze(
        ArticleAnalysisService(tmp_db, config=AnalysisProviderConfig(provider="local")),
        fixture,
        job_id=job["id"],
    )
    legacy_identity = analysis_identity_hash(
        document_version_id=analysis["document_version_id"],
        relevance_id=analysis["relevance_id"],
        scope_version=analysis["scope_version"],
        schema_version=analysis["schema_version"],
        prompt_version=analysis["prompt_version"],
        provider=analysis["provider"],
        model=analysis["model"],
    )
    raw = sqlite3.connect(str(tmp_db))
    try:
        raw.execute("DROP TRIGGER article_analyses_immutable_update")
        raw.execute(
            """
            UPDATE article_analyses
            SET input_view_version = NULL, input_content_hash = NULL,
                analyzed_content_hash = NULL, identity_hash = ?
            WHERE id = ?
            """,
            (legacy_identity, analysis["id"]),
        )
        raw.commit()
    finally:
        raw.close()
    readable = ArticleAnalysisService(tmp_db).get(analysis["id"])
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert readable["id"] == analysis["id"]
    assert bundle["input_contract_complete"] is False
    assert bundle["eligible_for_automatic_promotion"] is False
