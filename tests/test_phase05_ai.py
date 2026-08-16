from __future__ import annotations

import pytest
import time
import json
from pathlib import Path

from fastapi.testclient import TestClient

from newsroom.ai import (
    AIDisabled,
    AITimeout,
    AIValidationError,
    AIRouter,
    CapabilityBundle,
    DeterministicRelevanceProvider,
    DeterministicSynthesisProvider,
    LocalEmbeddingProvider,
    LocalEntailmentProvider,
    LocalExtractionProvider,
    LocalRelevanceProvider,
    LocalRerankerProvider,
    LocalSynthesisProvider,
    RoutePolicy,
    SQLiteTelemetrySink,
    TelemetryEvent,
)
from newsroom.ai_pipeline import AIVerticalSliceService, VerticalSliceInput
from newsroom.ai_benchmark import benchmark_json, run_benchmark
from newsroom.migrations import apply_migrations
from newsroom import storage
from newsroom.app import create_app
from newsroom.config import RuntimeConfig


PASSWORD = "a-long-test-password-12345"


def test_structured_provider_output_is_strictly_validated():
    with pytest.raises(AIValidationError):
        LocalRelevanceProvider(output={"relevant": True, "confidence": 2.0})

    telemetry = []
    router = AIRouter(
        local=CapabilityBundle(relevance=DeterministicRelevanceProvider(output={"relevant": True, "confidence": 2.0, "signal": "bad"})),
        telemetry=telemetry,
    )
    with pytest.raises(AIValidationError):
        router.relevance("text", ["text"], work_id="work-invalid")
    assert telemetry[0].error_code == "invalid_output"


def test_local_bundle_exposes_every_vertical_slice_capability():
    bundle = CapabilityBundle.local_defaults()
    assert bundle.embedding is not None
    assert bundle.reranker is not None
    assert bundle.entailment is not None
    assert bundle.relevance is not None
    assert bundle.extraction is not None
    assert bundle.synthesis is not None


def test_router_records_local_decision_and_does_not_escalate_by_default():
    telemetry = []
    router = AIRouter(
        local=CapabilityBundle(relevance=LocalRelevanceProvider()),
        paid=CapabilityBundle(relevance=DeterministicRelevanceProvider(relevant=True)),
        policy=RoutePolicy(paid_enabled=True, min_confidence=0.99, max_paid_calls=1),
        telemetry=telemetry,
    )

    result = router.relevance("Acme launches Atlas", ["Acme", "Atlas"], work_id="work-1")

    assert result.relevant is True
    assert telemetry[0].route == "local"
    assert telemetry[0].capability == "relevance"
    assert telemetry[0].work_id == "work-1"


def test_router_can_escalate_only_when_policy_and_budget_allow():
    telemetry = []
    router = AIRouter(
        local=CapabilityBundle(relevance=DeterministicRelevanceProvider(relevant=False, confidence=0.2)),
        paid=CapabilityBundle(relevance=DeterministicRelevanceProvider(relevant=True)),
        policy=RoutePolicy(paid_enabled=True, min_confidence=0.8, max_paid_calls=1),
        telemetry=telemetry,
    )

    result = router.relevance("Acme launches Atlas", ["Acme", "Atlas"], work_id="work-1")

    assert result.relevant is True
    assert [event.route for event in telemetry] == ["local", "paid"]
    assert telemetry[1].escalation_reason == "low_confidence"


def test_router_timeout_is_safe_and_attributed():
    class SlowRelevance:
        def classify(self, text, scope_terms):
            time.sleep(0.05)
            return {"relevant": True, "confidence": 1.0, "signal": "slow"}

    telemetry = []
    router = AIRouter(
        local=CapabilityBundle(relevance=SlowRelevance()),
        policy=RoutePolicy(timeout_seconds=0.005),
        telemetry=telemetry,
    )

    with pytest.raises(AITimeout):
        router.relevance("text", ["text"], work_id="work-timeout")

    assert telemetry[0].error_code == "timeout"
    assert telemetry[0].work_id == "work-timeout"


def test_disabled_paid_route_does_not_turn_low_confidence_into_unbounded_work():
    telemetry = []
    router = AIRouter(
        local=CapabilityBundle(),
        policy=RoutePolicy(local_enabled=False, paid_enabled=False),
        telemetry=telemetry,
    )

    with pytest.raises(AIDisabled):
        router.relevance("text", ["text"], work_id="work-disabled")

    assert telemetry[-1].outcome == "blocked"
    assert telemetry[-1].error_code == "paid_disabled"


def test_sqlite_telemetry_preserves_route_confidence_and_escalation_context(tmp_db):
    apply_migrations(tmp_db)
    SQLiteTelemetrySink(tmp_db).record(
        TelemetryEvent(
            capability="relevance",
            route="paid",
            provider="paid-test",
            outcome="succeeded",
            work_id="work-telemetry",
            confidence=0.91,
            decision_signal="classifier",
            latency_ms=12,
            estimated_cost_usd=0.01,
            escalation_reason="low_confidence",
        )
    )

    conn = storage.connect(tmp_db)
    try:
        row = conn.execute("SELECT * FROM provider_usage").fetchone()
    finally:
        conn.close()

    assert row["capability"] == "relevance"
    assert row["provider"] == "paid-test"
    assert json.loads(row["outcome"]) == {
        "confidence": 0.91,
        "compute_units": None,
        "decision_signal": "classifier",
        "error_code": None,
        "escalation_reason": "low_confidence",
        "model": None,
        "route": "paid",
        "status": "succeeded",
        "work_id": "work-telemetry",
    }


def test_local_only_vertical_slice_writes_validated_evidence_bound_revision(tmp_db):
    from newsroom.migrations import apply_migrations

    apply_migrations(tmp_db)
    telemetry = []
    service = AIVerticalSliceService(
        tmp_db,
        AIRouter(local=CapabilityBundle.local_defaults(), telemetry=telemetry),
    )

    result = service.run(
        VerticalSliceInput(
            source={"name": "Local Gazette", "slug": "local-gazette", "source_kind": "official"},
            document={
                "canonical_url": "https://local.test/atlas",
                "title": "Acme launches Atlas",
            },
            document_version={"content_hash": "atlas-v1", "content_kind": "excerpt"},
            content_text="Acme launched the Atlas product on August 16. The product is available today.",
            scope_terms=("Acme", "Atlas"),
            story={"headline": "Acme launches Atlas"},
            work_id="local-run-1",
        )
    )

    assert result["resolution"] == "new"
    assert len(result["claims"]) == 2
    assert all(claim["accepted"] for claim in result["claims"])
    assert result["revision"]["audit"]["passed"] is True
    assert {event.capability for event in telemetry} == {
        "embedding",
        "reranker",
        "relevance",
        "extraction",
        "entailment",
        "synthesis",
    }


def test_authenticated_ai_run_api_uses_local_route_and_persists_usage(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}

    response = client.post(
        "/api/v1/runs/ai",
        headers=headers,
        json={
            "source": {"name": "API Gazette", "slug": "api-gazette"},
            "document": {
                "canonical_url": "https://api.test/atlas",
                "title": "Atlas update",
            },
            "document_version": {"content_hash": "api-v1", "content_kind": "excerpt"},
            "content_text": "Acme launched Atlas today.",
            "scope_terms": ["Acme", "Atlas"],
            "story": {"headline": "Atlas update"},
            "work_id": "api-work-1",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["revision"]["audit"]["passed"] is True
    conn = storage.connect(config.database_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM provider_usage").fetchone()[0] >= 6
    finally:
        conn.close()


def test_ai_benchmark_is_reproducible_and_selects_every_local_capability():
    first = run_benchmark()
    second = run_benchmark()

    assert first == second
    assert set(first["tasks"]) == {
        "embedding",
        "reranker",
        "entailment",
        "relevance",
        "extraction",
        "synthesis",
    }
    assert all(task["selected_default"].startswith("local-") for task in first["tasks"].values())
    assert benchmark_json(first) == benchmark_json(second)
    artifact = json.loads(
        (Path(__file__).resolve().parents[1] / "evals" / "benchmarks" / "phase05_ai_benchmark.json").read_text()
    )
    assert artifact == first
