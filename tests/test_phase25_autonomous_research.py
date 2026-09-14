from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.acquisition import AcquisitionService, HttpResponse
from newsroom.ai import AIDisabled, AIRouter, CapabilityBundle, ResearchPlanOutput, ResearchPlanRequest, RoutePolicy
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.hypotheses import HypothesisService
from newsroom.integrity import check_database
from newsroom.jobs import JobService
from newsroom.migrations import CURRENT_SCHEMA_VERSION, apply_migrations
from newsroom.monitoring import MonitoringPolicyService
from newsroom.operations import export_logical
from newsroom.research_questions import (
    ResearchQuestionExecutionService,
    ResearchQuestionService,
)
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.worker import WorkerProcess
from newsroom.intelligent_monitoring import WatchService


T0 = "2026-08-23T12:00:00Z"


def _ledger_fixture(db_path):
    core = CoreService(db_path)
    source = core.create_source(
        {
            "name": "Phase 25 Official",
            "slug": "phase-25-official",
            "source_kind": "official",
            "default_quality": "primary",
            "homepage_url": "https://official.example.test",
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://official.example.test/report",
            "title": "Phase 25 report",
        }
    )
    story = core.create_story({"headline": "Phase 25 report"})
    ledger = EvidenceService(db_path)
    version = ledger.create_document_version(
        document["id"], {"content_hash": "phase25-content", "content_kind": "excerpt"}
    )
    return core, ledger, story, version


def _claim(ledger, story_id, version_id, proposition, excerpt, *, state="supported"):
    span = ledger.create_evidence_span(version_id, {"excerpt": excerpt})
    claim = ledger.create_claim(story_id, {"proposition": proposition, "importance": "major"})
    if state != "pending":
        ledger.set_claim_state(claim["id"], state, "Phase 25 fixture")
    ledger.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"}
    )
    return claim, span


def _question(db_path, **overrides):
    data = {
        "question": "Did the satellite launch occur?",
        "origin_type": "user",
        "search_attempt_budget": 2,
        "query_budget": 4,
        "pursuit_policy": "manual",
    }
    data.update(overrides)
    return ResearchQuestionService(db_path).create(data)


def test_question_assessment_is_deterministic_and_distinguishes_relationships(tmp_db):
    apply_migrations(tmp_db)
    _core, ledger, story, version = _ledger_fixture(tmp_db)
    supporting, _support_span = _claim(
        ledger, story["id"], version["id"],
        "The satellite launch occurred", "The launch occurred on Tuesday.",
    )
    contextual, _context_span = _claim(
        ledger, story["id"], version["id"],
        "The weather was cloudy", "The weather was cloudy on Tuesday.",
    )
    question = _question(tmp_db)
    service = ResearchQuestionService(tmp_db)
    service.link_claim(question["id"], supporting["id"], "supports")
    service.link_claim(question["id"], contextual["id"], "contextualizes")

    current = service.get(question["id"])
    assert current["assessment_state"] == "supported"
    assert current["gaps"][0]["status"] == "satisfied"
    assert any(item["claim_id"] == contextual["id"] and item["relationship"] == "contextualizes" for item in current["claims"])
    before = len(current["assessment_history"])
    service.evaluate(question["id"])
    assert len(service.get(question["id"])["assessment_history"]) == before

    contradiction, _contradiction_span = _claim(
        ledger, story["id"], version["id"],
        "The satellite launch did not occur", "The launch did not occur.",
    )
    service.link_claim(question["id"], contradiction["id"], "contradicts")
    current = service.get(question["id"])
    assert current["assessment_state"] == "partially_answered"
    assert any(item["relationship"] == "contradicts" for item in current["claims"])


def test_phase24_database_upgrades_to_phase25_without_reinterpreting_existing_question(tmp_db):
    import newsroom.migrations as migration_module

    conn = storage.connect(tmp_db)
    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        with storage.write_tx(conn):
            migration_module._ensure_ledger(conn)
            for version in range(1, 25):
                for statement in getattr(migration_module, f"MIGRATION_{version:04d}_STATEMENTS"):
                    conn.execute(statement)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, "2026-08-23T00:00:00Z"),
                )
            conn.execute("UPDATE app_meta SET value = '24' WHERE key = 'schema_version'")
            conn.execute(
                """
                INSERT INTO research_questions
                    (id, question, origin_type, status, priority, search_attempt_budget,
                     created_at, updated_at)
                VALUES ('rq-legacy', 'Was the legacy question preserved?', 'user', 'open',
                        'normal', 1, '2026-08-23T00:00:00Z', '2026-08-23T00:00:00Z')
                """
            )
    finally:
        conn.close()

    from newsroom.migrations import migration_status

    result = apply_migrations(tmp_db)
    assert result.applied_versions == tuple(range(25, CURRENT_SCHEMA_VERSION + 1))
    assert migration_status(tmp_db) == tuple(range(1, CURRENT_SCHEMA_VERSION + 1))
    current = ResearchQuestionService(tmp_db).get("rq-legacy")
    assert current["status"] == "open"
    assert current["assessment_state"] == "open"
    assert current["gaps"]
    assert apply_migrations(tmp_db).applied_versions == ()


def test_unsubstantiated_claim_does_not_resolve_question_and_gap_dismissal_is_stable(tmp_db):
    apply_migrations(tmp_db)
    _core, ledger, story, version = _ledger_fixture(tmp_db)
    pending, _span = _claim(
        ledger, story["id"], version["id"],
        "The satellite launch occurred", "A draft says the launch occurred.", state="pending",
    )
    question = _question(tmp_db)
    service = ResearchQuestionService(tmp_db)
    service.link_claim(question["id"], pending["id"], "supports")
    assert service.get(question["id"])["assessment_state"] == "open"
    gap = service.get(question["id"])["gaps"][0]
    service.set_gap_status(gap["id"], "dismissed", reason="Not useful for this question")
    service.evaluate(question["id"])
    assert service.get(question["id"])["gaps"][0]["status"] == "dismissed"


def test_bounded_task_no_findings_is_successful_and_does_not_satisfy_gap(tmp_db):
    apply_migrations(tmp_db)
    question = _question(tmp_db)

    class EmptySearch:
        def search(self, *args, **kwargs):
            return {"items": []}

    service = ResearchQuestionService(tmp_db)
    job = service.pursue(question["id"], query="unavailable material", query_units=1)
    execution = ResearchQuestionExecutionService(tmp_db, search=EmptySearch())
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, execution.handlers(), worker_id="phase25-test", queue=queue)
    result = worker.run_once(now=T0)
    assert result["status"] == "succeeded"
    current = service.get(question["id"])
    assert current["tasks"][0]["status"] == "completed_no_findings"
    assert current["gaps"][0]["status"] == "open"
    assert current["tasks"][0]["limits"]["max_queries"] <= 12
    assert job["task_id"] == current["tasks"][0]["id"]


def test_failed_bounded_task_reopens_its_question_gap(tmp_db):
    apply_migrations(tmp_db)
    question = _question(tmp_db)
    service = ResearchQuestionService(tmp_db)
    job = service.pursue(question["id"], query="temporarily unavailable material", query_units=1)

    class FailingSearch:
        def search(self, *args, **kwargs):
            raise RuntimeError("controlled search outage")

    execution = ResearchQuestionExecutionService(tmp_db, search=FailingSearch())
    worker = WorkerProcess(
        tmp_db,
        execution.handlers(),
        worker_id="phase25-failing-search",
        queue=build_worker_queue(tmp_db),
    )

    result = worker.run_once(now=T0)

    assert result["status"] == "failed"
    current = service.get(question["id"])
    assert current["gaps"][0]["status"] == "open"
    assert current["tasks"][0]["id"] == job["task_id"]
    assert current["tasks"][0]["status"] == "failed"
    assert current["attempts"][0]["status"] == "failed"


def test_question_watch_source_approval_pins_canonical_question_need(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    question = _question(tmp_db)
    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "Phase 25 question source policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 3600,
            "min_cadence_seconds": 900,
            "max_cadence_seconds": 86400,
            "query_budget": 4,
        }
    )
    watches = WatchService(tmp_db)
    watch = watches.create(
        {
            "name": "Question source Watch",
            "target_type": "research_question",
            "target_id": question["id"],
            "policy_id": policy["id"],
        }
    )
    source = core.create_source(
        {
            "name": "Question source",
            "slug": "phase-25-question-source",
            "source_kind": "official",
            "default_quality": "primary",
            "homepage_url": "https://question-source.example.test",
        }
    )
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": source["name"],
            "homepage_url": source["homepage_url"],
            "rationale": "Controlled source for question-bound monitoring",
            "discovery_method": "existing_source",
            "source_id": source["id"],
        },
    )

    watches.review_source_candidate(watch["id"], candidate["id"], "approved", "editor")

    attached = watches.get(watch["id"])["sources"][0]
    assert attached["monitor"]["need_type"] == "research_question"
    assert attached["monitor"]["need_id"] == question["id"]


def test_automatic_pursuit_uses_existing_job_path_and_obeys_cooldown(tmp_db):
    apply_migrations(tmp_db)
    question = _question(
        tmp_db,
        pursuit_policy="automatic",
        pursuit_cooldown_seconds=120,
        next_attempt_at="2026-08-23T11:00:00Z",
    )
    service = ResearchQuestionService(tmp_db)
    scheduled = service.pursue_due(now=T0)
    assert scheduled["scheduled_count"] == 1

    class EmptySearch:
        def search(self, *args, **kwargs):
            return {"items": []}

    worker = WorkerProcess(
        tmp_db,
        ResearchQuestionExecutionService(tmp_db, search=EmptySearch()).handlers(),
        worker_id="phase25-automatic",
        queue=build_worker_queue(tmp_db),
    )
    assert worker.run_once(now=T0)["status"] == "succeeded"
    current = service.get(question["id"])
    assert current["next_attempt_at"] is not None
    assert current["next_attempt_at"] > T0
    assert service.pursue_due(now=T0)["scheduled_count"] == 0


def test_duplicate_pursuit_converges_on_one_active_task_per_gap(tmp_db):
    apply_migrations(tmp_db)
    question = _question(tmp_db, search_attempt_budget=3, query_budget=4)
    service = ResearchQuestionService(tmp_db)
    first = service.pursue(question["id"], query="same bounded pursuit", query_units=1)
    second = service.pursue(question["id"], query="same bounded pursuit", query_units=1)
    assert second["coalesced"] is True
    assert second["id"] == first["id"]
    assert len(service.get(question["id"])["tasks"]) == 1


def test_provider_planning_is_bounded_advisory_and_falls_back_without_changing_question(tmp_db):
    apply_migrations(tmp_db)
    question = _question(tmp_db)
    service = ResearchQuestionService(tmp_db)
    before = service.get(question["id"])
    planned: list[object] = []

    class Planner:
        def plan(self, request):
            planned.append(request)
            return ResearchPlanOutput(
                query_suggestions=["provider satellite brief"],
                preferred_source_classes=["official"],
                explanation="bounded advisory plan",
            )

    class EmptySearch:
        def __init__(self):
            self.queries: list[str] = []

        def search(self, query, **kwargs):
            self.queries.append(query)
            return {"items": []}

    search = EmptySearch()
    router = AIRouter(
        local=CapabilityBundle(research_plan=Planner()),
        policy=RoutePolicy(local_enabled=True, paid_enabled=False),
    )
    job = service.pursue(question["id"], query="deterministic fallback", query_units=1)
    execution = ResearchQuestionExecutionService(tmp_db, search=search, router=router)
    worker = WorkerProcess(tmp_db, execution.handlers(), worker_id="phase25-provider", queue=build_worker_queue(tmp_db))
    result = worker.run_once(now=T0)

    assert result["status"] == "succeeded"
    assert planned and planned[0].max_queries <= 12
    current = service.get(question["id"])
    task = service.get_task(question["id"], job["task_id"])
    assert any(item["strategy"] == "provider_suggestion" for item in task["queries"])
    assert len(task["queries"]) <= task["limits"]["max_queries"]
    assert current["assessment_state"] == before["assessment_state"] == "open"
    assert current["gaps"][0]["status"] == "open"
    assert "provider satellite brief" in search.queries


def test_existing_router_paid_budget_blocks_second_research_plan(tmp_db):
    apply_migrations(tmp_db)
    events = []

    class PaidPlanner:
        def __init__(self):
            self.calls = 0

        def plan(self, request):
            self.calls += 1
            return {"query_suggestions": ["paid bounded query"]}

    provider = PaidPlanner()
    router = AIRouter(
        local=CapabilityBundle(),
        paid=CapabilityBundle(research_plan=provider),
        policy=RoutePolicy(
            local_enabled=False,
            paid_enabled=True,
            max_paid_calls=1,
            max_paid_cost_usd=0.01,
            max_paid_calls_per_work=1,
            max_paid_cost_usd_per_work=0.01,
            paid_request_cost_usd=0.01,
        ),
        telemetry=events,
    )
    request = ResearchPlanRequest(
        question="Did the satellite launch occur?",
        gap_type="supporting_evidence",
        gap_description="Find evidence",
        approved_vocabulary=(),
        max_queries=2,
    )
    assert router.research_plan(request, work_id="task-budget").query_suggestions == ["paid bounded query"]
    with pytest.raises(AIDisabled):
        router.research_plan(request, work_id="task-budget")
    assert provider.calls == 1
    assert any(event.error_code == "paid_budget_exhausted" for event in events)


def test_external_candidate_uses_approved_watch_acquisition_and_never_becomes_claim(tmp_db):
    apply_migrations(tmp_db)
    _core, _ledger, _story, version = _ledger_fixture(tmp_db)
    question = _question(tmp_db)
    service = ResearchQuestionService(tmp_db)
    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "Phase 25 research policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 3600,
            "min_cadence_seconds": 900,
            "max_cadence_seconds": 86400,
            "query_budget": 4,
        }
    )
    watches = WatchService(tmp_db)
    watch = watches.create(
        {
            "name": "Satellite research",
            "target_type": "research_question",
            "target_id": question["id"],
            "policy_id": policy["id"],
        }
    )
    watches.add_vocabulary(watch["id"], {"term": "satellite launch", "kind": "primary"})
    source = _core.create_source(
        {
            "name": "Phase 25 Approved Source",
            "slug": "phase-25-approved-source",
            "source_kind": "official",
            "default_quality": "primary",
            "homepage_url": "https://approved.example.test",
        }
    )
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": source["name"],
            "homepage_url": source["homepage_url"],
            "rationale": "Approved research source fixture",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(watch["id"], candidate["id"], "approved", "editor")
    approved = watches.get(watch["id"])["sources"][0]

    class EmptySearch:
        def search(self, *args, **kwargs):
            return {"items": []}

    class ExternalSearch:
        def search(self, query, *, limit):
            return [
                {
                    "url": "https://approved.example.test/research",
                    "title": "Official satellite release",
                    "snippet": "Candidate metadata only",
                    "source_id": source["id"],
                }
            ]

    acquired_calls = []

    class ReusingAcquirer:
        def acquire_document(self, source_id, url, **kwargs):
            acquired_calls.append((source_id, url, kwargs))
            return SimpleNamespace(
                document_id=version["document_id"],
                document_version_id=version["id"],
                outcome="unchanged",
            )

    job = service.pursue(question["id"], query="satellite launch", query_units=1)
    execution = ResearchQuestionExecutionService(
        tmp_db,
        search=EmptySearch(),
        external_search=ExternalSearch(),
        acquirer=ReusingAcquirer(),
    )
    worker = WorkerProcess(tmp_db, execution.handlers(), worker_id="phase25-acquisition", queue=build_worker_queue(tmp_db))
    result = worker.run_once(now=T0)

    assert result["status"] == "succeeded"
    assert acquired_calls == [(source["id"], "https://approved.example.test/research", {"channel": "direct_http", "monitor_id": approved["monitor"]["id"]})]
    current = service.get(question["id"])
    assert current["assessment_state"] == "open"
    assert current["claims"] == []
    task = service.get_task(question["id"], job["task_id"])
    assert task["status"] == "completed_with_candidates"
    assert any(item["finding_type"] == "document" and item["document_id"] == version["document_id"] for item in task["findings"])
    assert any(item["status"] == "suggested" for item in watches.get(watch["id"])["source_candidates"])


def test_production_composition_research_candidate_reaches_canonical_evidence_path(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    question = _question(tmp_db, question="Did the satellite launch occur?", search_attempt_budget=2, query_budget=4)
    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "Phase 25 end-to-end policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 3600,
            "min_cadence_seconds": 900,
            "max_cadence_seconds": 86400,
            "query_budget": 4,
        }
    )
    watches = WatchService(tmp_db)
    watch = watches.create(
        {
            "name": "Satellite launch research",
            "target_type": "research_question",
            "target_id": question["id"],
            "policy_id": policy["id"],
        }
    )
    watches.add_vocabulary(watch["id"], {"term": "satellite launch", "kind": "primary"})
    source = core.create_source(
        {
            "name": "Phase 25 End-to-End Source",
            "slug": "phase-25-end-to-end-source",
            "source_kind": "official",
            "default_quality": "primary",
            "homepage_url": "https://e2e.example.test",
        }
    )
    candidate = watches.add_source_candidate(
        watch["id"],
        {
            "name": source["name"],
            "homepage_url": source["homepage_url"],
            "rationale": "Controlled canonical acquisition fixture",
            "discovery_method": "manual",
        },
    )
    watches.review_source_candidate(watch["id"], candidate["id"], "approved", "editor")

    class ExternalSearch:
        def search(self, query, *, limit):
            return [{
                "url": "https://e2e.example.test/launch",
                "title": "Satellite launch report",
                "snippet": "Untrusted search metadata",
                "source_id": source["id"],
            }]

    class ControlledTransport:
        def get(self, url, *, headers, policy):
            return HttpResponse(
                200,
                url,
                {"content-type": "text/html"},
                b"<html><title>Satellite launch report</title><p>The satellite launch occurred on Tuesday.</p></html>",
            )

    service = ResearchQuestionService(tmp_db)
    job = service.pursue(question["id"], query="satellite launch", query_units=1)
    acquisition = AcquisitionService(tmp_db, transport=ControlledTransport())
    research_execution = ResearchQuestionExecutionService(
        tmp_db,
        external_search=ExternalSearch(),
        acquirer=acquisition,
    )
    research_worker = WorkerProcess(
        tmp_db,
        research_execution.handlers(),
        worker_id="phase25-e2e-research",
        queue=build_worker_queue(tmp_db),
    )
    research_result = research_worker.run_once(now=T0)
    assert research_result["status"] == "succeeded"
    assert research_result["result"]["documents_acquired"] == 1
    assert service.get_task(question["id"], job["task_id"])["findings"]
    assert service.get(question["id"])["claims"] == []

    processing_worker = WorkerProcess(
        tmp_db,
        build_worker_handlers(tmp_db),
        worker_id="phase25-e2e-processing",
        queue=build_worker_queue(tmp_db),
    )
    processing_result = processing_worker.run_once(now=T0)
    assert processing_result["status"] == "succeeded"
    assert processing_result["job_type"] == "document_version_process"
    conn = storage.connect(tmp_db)
    try:
        claim_id = conn.execute("SELECT id FROM claims ORDER BY id LIMIT 1").fetchone()[0]
    finally:
        conn.close()
    EvidenceService(tmp_db).set_claim_state(claim_id, "supported", "Phase 25 controlled review")
    current = service.get(question["id"])
    assert current["assessment_state"] == "supported"
    assert current["claims"]
    assert current["claims"][0]["relationship"] == "supports"
    assert current["gaps"][0]["status"] == "satisfied"
    assert service.get_task(question["id"], job["task_id"])["status"] == "completed_with_evidence"


def test_concurrent_pursuit_keeps_one_active_task_and_export_preserves_reconstruction(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    _core, ledger, story, version = _ledger_fixture(tmp_db)
    supporting, span = _claim(
        ledger, story["id"], version["id"],
        "The satellite launch occurred", "The satellite launch occurred.",
    )
    question = _question(tmp_db, search_attempt_budget=4, query_budget=4)
    service = ResearchQuestionService(tmp_db)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(service.pursue, question["id"], query="same pursuit", query_units=1) for _ in range(2)]
        results = [future.result() for future in futures if not future.exception()]
    current = service.get(question["id"])
    assert len([item for item in current["tasks"] if item["status"] in {"planned", "running"}]) == 1
    assert len(results) >= 1

    service.link_claim(question["id"], supporting["id"], "supports")
    exported = export_logical(tmp_db, tmp_path / "phase25.jsonl")
    rows = [json.loads(line) for line in exported.read_text(encoding="utf-8").splitlines()]
    tables = {row.get("table") for row in rows}
    assert {"research_questions", "research_question_claims", "research_question_assessments", "research_question_gaps", "research_tasks"} <= tables
    question_record = next(row for row in rows if row.get("table") == "research_questions")
    assert question_record["data"]["assessment_state"] == "supported"
    assert any(row.get("table") == "claims" and row["data"]["id"] == supporting["id"] for row in rows)
    assert any(row.get("table") == "evidence_spans" and row["data"]["id"] == span["id"] for row in rows)


def test_integrity_rejects_a_satisfied_gap_without_canonical_evidence(tmp_db):
    apply_migrations(tmp_db)
    question = _question(tmp_db)
    gap = ResearchQuestionService(tmp_db).get(question["id"])["gaps"][0]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("UPDATE research_question_gaps SET status = 'satisfied' WHERE id = ?", (gap["id"],))
    finally:
        conn.close()
    report = check_database(tmp_db)
    assert not report.ok
    assert any(issue.code == "satisfied_gap_without_evidence" for issue in report.issues)


def test_research_question_workspace_api_exposes_bounded_assessment_gaps_and_tasks(tmp_path):
    client = TestClient(
        create_app(
            config=RuntimeConfig.for_environment("dev", root=tmp_path / "dev"),
            frontend_dist=tmp_path / "missing-dist",
        )
    )
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    response = client.post(
        "/api/v1/research-questions",
        headers=headers,
        json={"question": "Did a controlled test occur?", "search_attempt_budget": 1, "query_budget": 2},
    )
    assert response.status_code == 201, response.text
    identifier = response.json()["id"]
    assert client.get(f"/api/v1/research-questions/{identifier}/assessment").json()["state"] == "open"
    gaps = client.get(f"/api/v1/research-questions/{identifier}/gaps").json()
    assert gaps["total"] == 1
    second_response = client.post(
        "/api/v1/research-questions",
        headers=headers,
        json={"question": "Did another controlled test occur?", "search_attempt_budget": 1},
    )
    second_gap = client.get(f"/api/v1/research-questions/{second_response.json()['id']}/gaps").json()["items"][0]
    cross_question_review = client.post(
        f"/api/v1/research-questions/{identifier}/gaps/{second_gap['id']}/review",
        headers=headers,
        json={"status": "dismissed", "reason": "must remain scoped"},
    )
    assert cross_question_review.status_code == 404
    assert client.get(f"/api/v1/research-questions/{second_response.json()['id']}/gaps").json()["items"][0]["status"] == "open"
    pursued = client.post(
        f"/api/v1/research-questions/{identifier}/gaps/{gaps['items'][0]['id']}/pursue",
        headers=headers,
        json={"mode": "manual", "query_units": 1, "limits": {"max_queries": 2, "max_candidates": 3, "max_documents": 1}},
    )
    assert pursued.status_code == 201, pursued.text
    tasks = client.get(f"/api/v1/research-questions/{identifier}/tasks").json()
    assert tasks["total"] == 1
    assert tasks["items"][0]["limits"]["max_candidates"] == 3


def test_question_first_watch_setup_creates_one_canonical_question_and_open_gap(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")
    payload = {
        "request_id": str(uuid.uuid4()),
        "target_type": "research_question",
        "interest": "Did the satellite launch occur?",
        "question": "Did the satellite launch occur?",
        "name": "Satellite launch question",
        "primary_terms": ["satellite launch"],
    }

    with TestClient(app) as client:
        assert client.post("/api/v1/watches/setup", json=payload).status_code == 401
        assert client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 201
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 200
        csrf = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
        assert client.post("/api/v1/watches/setup", json=payload).status_code == 403

        created = client.post("/api/v1/watches/setup", headers=csrf, json=payload)
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["target_type"] == "research_question"
        assert body["question"]["id"] == body["research_question_id"]
        assert body["question"]["question"] == payload["question"]
        assert body["gap"]["status"] == "open"
        assert body["gap"]["question_id"] == body["research_question_id"]
        assert body["watch"]["target_id"] == body["research_question_id"]

        watch = client.get(f"/api/v1/watches/{body['watch_id']}")
        assert watch.status_code == 200, watch.text
        detail = watch.json()
        assert detail["research_question"]["id"] == body["research_question_id"]
        assert detail["research_question"]["gaps"][0]["status"] == "open"

        retry = client.post("/api/v1/watches/setup", headers=csrf, json=payload)
        assert retry.status_code == 200, retry.text
        assert retry.json()["resumed"] is True
        assert retry.json()["watch_id"] == body["watch_id"]
        assert retry.json()["research_question_id"] == body["research_question_id"]

    conn = storage.connect(config.database_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM research_questions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM research_question_gaps").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM watches").fetchone()[0] == 1
    finally:
        conn.close()


def test_question_first_watch_setup_selects_existing_question_by_normalized_text(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 201
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 200
        csrf = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
        existing = client.post(
            "/api/v1/research-questions",
            headers=csrf,
            json={
                "question": "Did the satellite launch occur?",
                "search_attempt_budget": 2,
                "query_budget": 4,
            },
        )
        assert existing.status_code == 201, existing.text
        question_id = existing.json()["id"]

        selected = client.post(
            "/api/v1/watches/setup",
            headers=csrf,
            json={
                "request_id": str(uuid.uuid4()),
                "target_type": "research_question",
                "interest": "A question selected by its wording",
                "question": "  did   THE satellite launch occur? ",
                "name": "Existing launch question Watch",
                "primary_terms": ["satellite launch"],
            },
        )
        assert selected.status_code == 201, selected.text
        body = selected.json()
        assert body["research_question_id"] == question_id
        assert body["question_created"] is False

    conn = storage.connect(config.database_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM research_questions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM watches").fetchone()[0] == 1
    finally:
        conn.close()


def test_question_first_watch_setup_retries_concurrently_to_one_saved_identity(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")
    payload = {
        "request_id": str(uuid.uuid4()),
        "target_type": "research_question",
        "interest": "Will the controlled launch happen?",
        "question": "Will the controlled launch happen?",
        "name": "Controlled launch question Watch",
        "primary_terms": ["controlled launch"],
    }
    with TestClient(app) as bootstrap:
        assert bootstrap.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 201

    def submit():
        with TestClient(app) as client:
            assert client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "a-long-test-password-12345"},
            ).status_code == 200
            headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
            response = client.post("/api/v1/watches/setup", headers=headers, json=payload)
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: submit(), range(2)))

    assert sorted(status for status, _body in results) == [200, 201]
    assert {body["watch_id"] for _status, body in results} == {payload["request_id"]}
    assert len({body["research_question_id"] for _status, body in results}) == 1
    conn = storage.connect(config.database_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM research_questions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM research_question_gaps").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM watches").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM monitoring_policies").fetchone()[0] == 1
    finally:
        conn.close()


def test_question_first_watch_setup_rejects_ambiguous_duplicate_question_wording(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    app = create_app(config=config, frontend_dist=tmp_path / "missing-dist")
    with TestClient(app) as client:
        assert client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 201
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code == 200
        headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
        for question in ("Is the launch ready?", "  is   the launch ready? "):
            response = client.post(
                "/api/v1/research-questions",
                headers=headers,
                json={"question": question, "search_attempt_budget": 1},
            )
            assert response.status_code == 201, response.text
        response = client.post(
            "/api/v1/watches/setup",
            headers=headers,
            json={
                "request_id": str(uuid.uuid4()),
                "target_type": "research_question",
                "interest": "Is the launch ready?",
                "question": "Is the launch ready?",
                "name": "Ambiguous launch Watch",
                "primary_terms": ["launch"],
            },
        )
        assert response.status_code == 409, response.text
        assert "multiple Research Questions" in response.json()["error"]["message"]

    conn = storage.connect(config.database_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM watches").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM monitoring_policies").fetchone()[0] == 0
    finally:
        conn.close()


def test_question_candidates_and_hypotheses_do_not_create_accepted_claims(tmp_db):
    apply_migrations(tmp_db)
    _core, ledger, story, version = _ledger_fixture(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        source_id = conn.execute("SELECT id FROM sources ORDER BY id LIMIT 1").fetchone()[0]
    finally:
        conn.close()
    pending, _span = _claim(
        ledger,
        story["id"],
        version["id"],
        "The launch may happen",
        "A draft report suggests the launch may happen.",
        state="pending",
    )
    question = _question(tmp_db, question="Will the launch happen?")
    hypothesis = HypothesisService(tmp_db).create(
        question["id"], "The launch is likely after the final readiness review."
    )
    HypothesisService(tmp_db).review(
        hypothesis["id"], "approved", actor="editor", reason="Reviewed as a hypothesis"
    )

    class CandidateSearch:
        def search(self, *args, **kwargs):
            return {
                "items": [
                    {
                        "entity_type": "claim",
                        "entity_id": pending["id"],
                        "source_id": source_id,
                    }
                ]
            }

    service = ResearchQuestionService(tmp_db)
    job = service.pursue(question["id"], query="launch readiness", query_units=1)
    worker = WorkerProcess(
        tmp_db,
        ResearchQuestionExecutionService(tmp_db, search=CandidateSearch()).handlers(),
        worker_id="phase25-candidate-boundary",
        queue=build_worker_queue(tmp_db),
    )
    result = worker.run_once(now=T0)

    assert result["status"] == "succeeded", result
    current = service.get(question["id"])
    assert current["assessment_state"] == "open"
    assert any(item["claim_id"] == pending["id"] for item in current["claims"])
    assert service.get_task(question["id"], job["task_id"])["status"] == "completed_with_candidates"
    assert HypothesisService(tmp_db).get(hypothesis["id"])["status"] == "approved"
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT state FROM claims WHERE id = ?", (pending["id"],)).fetchone()[0] == "pending"
    finally:
        conn.close()


def test_ast41_question_first_watch_ui_keeps_question_and_evidence_context_visible():
    root = Path(__file__).resolve().parents[1]
    view = (root / "frontend" / "src" / "views" / "WatchManagementView.tsx").read_text(encoding="utf-8")
    admin = (root / "frontend" / "src" / "views" / "AdminViews.tsx").read_text(encoding="utf-8")
    types = (root / "frontend" / "src" / "lib" / "types.ts").read_text(encoding="utf-8")

    for label in (
        "Create a new Research Question",
        "Select an existing Research Question",
        "Research Question context",
        "Pursue open Gap",
        "No findings",
        "Evidence boundary",
        "Hypotheses remain review-only",
    ):
        assert label in view or label in admin
    assert "target_type: submission.target_type" in view
    assert "question: submission.question" in view
    assert "target_id: submission" not in view
    assert "QuestionWatchDraft" in types
    assert "WatchResearchContext" in types
