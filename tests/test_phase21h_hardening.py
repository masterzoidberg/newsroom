from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from newsroom import storage
from newsroom.acquisition import AcquisitionBlocked, AcquisitionPolicy, UrllibHttpTransport
from newsroom.ai import AIProviderError, AIDisabled, ArticleAnalysisRequest
from newsroom.article_analysis import AnalysisProviderConfig, ArticleAnalysisService
from newsroom.content_artifacts import ContentArtifactService, normalized_text_hash
from newsroom.domain import CoreService
from newsroom.integrity import check_database
from newsroom.jobs import BudgetService
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


def test_phase21h_migration_is_additive_and_idempotent(tmp_db):
    assert apply_migrations(tmp_db).current_version == 19
    assert apply_migrations(tmp_db).applied_versions == ()
    assert migration_status(tmp_db)[-1] == 19
    conn = storage.connect(tmp_db)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        columns = {row[1] for row in conn.execute("PRAGMA table_info(provider_usage)")}
    finally:
        conn.close()
    assert "analysis_invocations" in tables
    assert "invocation_id" in columns


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


def test_provenance_validator_rejects_cross_reference_corruption(tmp_db):
    fixture = _setup_analysis(tmp_db)
    service = _service(tmp_db, CountingProvider())
    BudgetService(tmp_db).set_paid_enabled(True)
    analysis = _analyze(service, fixture)
    bundle = validate_analysis_provenance(tmp_db, analysis["id"])
    assert bundle["analysis"]["id"] == analysis["id"]

    other = _setup_analysis(tmp_db, suffix="b")
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
