from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.domain import CoreService, DomainNotFound, DomainValidation
from newsroom.migrations import apply_migrations
from newsroom.monitoring import (
    MonitorService,
    MonitorExecutionService,
    MonitoringPolicyService,
    RelevanceCascade,
    RelevanceScope,
    ScopeSuggestionService,
)
from newsroom.jobs import SchedulerService
from newsroom.worker import WorkerProcess
from newsroom.app import create_app
from newsroom.config import RuntimeConfig


T0 = "2026-08-16T12:00:00Z"


def _category_and_topic(db_path):
    service = CoreService(db_path)
    category = service.create_category({"slug": "technology", "name": "Technology"})
    topic = service.create_topic(
        {
            "category_id": category["id"],
            "slug": "quantum-computing",
            "name": "Quantum Computing",
        }
    )
    return service, topic


def _policy(db_path, **overrides):
    values = {
        "name": "Local monitor",
        "allowed_channels": ["rss", "direct_http"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
        "query_budget": 5,
        "local_model_budget": 10,
        "paid_budget_usd": 0.0,
        "backoff_rules": {"no_change_multiplier": 2.0, "error_multiplier": 3.0},
        "retirement_criteria": {"max_consecutive_errors": 3},
    }
    values.update(overrides)
    return MonitoringPolicyService(db_path).create(values)


def test_phase08_migration_adds_history_and_suggestion_tables_idempotently(tmp_db):
    assert apply_migrations(tmp_db).applied_versions == (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert apply_migrations(tmp_db).applied_versions == ()

    conn = storage.connect(tmp_db)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"monitor_activity", "monitor_scope_history", "vocabulary_suggestions"} <= tables
    finally:
        conn.close()


def test_monitor_policy_and_targets_are_validated_and_persisted(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "The Wire", "slug": "the-wire"})
    policy = _policy(tmp_db)
    monitors = MonitorService(tmp_db)

    monitor = monitors.create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "next_check_at": T0,
        }
    )
    assert monitor["target_type"] == "source"
    assert monitor["enabled"] == 1
    assert monitors.scope_history(monitor["id"])["items"]

    with pytest.raises(DomainValidation):
        MonitoringPolicyService(tmp_db).create(
            {
                "name": "Invalid",
                "allowed_channels": ["rss"],
                "base_cadence_seconds": 10,
                "min_cadence_seconds": 20,
                "max_cadence_seconds": 30,
            }
        )

    core.delete_source(source["id"])
    with pytest.raises(DomainNotFound):
        monitors.create(
            {
                "target_type": "source",
                "target_id": source["id"],
                "policy_id": policy["id"],
            }
        )


def test_scope_suggestions_are_pending_until_approved_and_history_is_visible(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _category_and_topic(tmp_db)
    suggestions = ScopeSuggestionService(tmp_db)

    pending = suggestions.create(
        topic["id"],
        {
            "suggestion_type": "broader",
            "value": "quantum information science",
            "rationale": "broader concept candidate",
        },
    )
    assert pending["status"] == "pending"
    assert core.list_vocabulary(topic["id"])["items"] == []
    suggestions.review(pending["id"], approved=False, reviewed_by="editor")
    assert core.list_vocabulary(topic["id"])["items"] == []

    approved = suggestions.create(
        topic["id"],
        {"suggestion_type": "alias", "value": "QC", "rationale": "common acronym"},
    )
    suggestions.review(approved["id"], approved=True, reviewed_by="editor")
    terms = core.list_vocabulary(topic["id"])["items"]
    assert [term["term"] for term in terms] == ["QC"]


def test_adaptive_cadence_is_bounded_and_activity_is_append_only(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Activity Source", "slug": "activity-source"})
    policy = _policy(tmp_db)
    monitors = MonitorService(tmp_db)
    monitor = monitors.create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "next_check_at": T0,
        }
    )

    after_quiet = monitors.record_activity(monitor["id"], "no_change", observed_at=T0)
    assert after_quiet["next_check_at"] == "2026-08-16T12:02:00Z"
    after_change = monitors.record_activity(
        monitor["id"], "relevant_change", relevant_items=2, observed_at="2026-08-16T12:02:00Z"
    )
    assert after_change["next_check_at"] == "2026-08-16T12:02:30Z"
    after_error = monitors.record_activity(
        monitor["id"], "error", error_code="upstream_timeout", observed_at="2026-08-16T12:02:30Z"
    )
    assert after_error["next_check_at"] == "2026-08-16T12:04:00Z"
    assert len(monitors.activity(monitor["id"])["items"]) == 3

    conn = storage.connect(tmp_db)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE monitor_activity SET outcome = 'error'")
    finally:
        conn.close()


def test_retirement_after_consecutive_errors_disables_future_work(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Retiring Source", "slug": "retiring-source"})
    policy = _policy(tmp_db, retirement_criteria={"max_consecutive_errors": 2})
    monitors = MonitorService(tmp_db)
    monitor = monitors.create({"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0})
    monitors.record_activity(monitor["id"], "error", error_code="timeout", observed_at=T0)
    retired = monitors.record_activity(monitor["id"], "error", error_code="timeout", observed_at="2026-08-16T12:01:00Z")
    assert (retired["enabled"], retired["last_result"], retired["next_check_at"]) == (0, "retired", None)
    assert SchedulerService(tmp_db).tick(now="2026-08-16T12:02:00Z")["job_ids"] == []


def test_relevance_cascade_exercises_all_levels_and_exclusions():
    fixtures = [
        (
            RelevanceScope(exact_terms=("quantum chip",)),
            "A quantum chip enters production.",
            "exact",
        ),
        (RelevanceScope(vocabulary=("QPU",)), "The QPU market expands.", "vocabulary"),
        (RelevanceScope(entities=("NVIDIA",)), "NVIDIA announces a new lab.", "entity"),
        (RelevanceScope(concepts=("photonic computing",)), "Photonic computing research grows.", "concept"),
    ]
    for scope, text, stage in fixtures:
        result = RelevanceCascade().evaluate(text, scope)
        assert result.relevant is True
        assert result.stage == stage

    semantic = RelevanceCascade(semantic_similarity=lambda _text, _terms: 0.91)
    result = semantic.evaluate("A distant paraphrase", RelevanceScope(semantic_terms=("quantum processor",)))
    assert (result.relevant, result.stage) == (True, "semantic")

    ai = RelevanceCascade(ai_classifier=lambda _text, _scope: (True, 0.84, "local-fixture"))
    result = ai.evaluate("A classified candidate", RelevanceScope())
    assert (result.relevant, result.stage) == (True, "ai")
    assert result.paid_used is False

    low_confidence = RelevanceCascade(ai_classifier=lambda _text, _scope: (True, 0.2, "uncertain"))
    result = low_confidence.evaluate("An uncertain candidate", RelevanceScope())
    assert (result.relevant, result.stage, result.score) == (False, "none", 0.2)

    excluded = RelevanceCascade().evaluate(
        "Quantum chip rumor is a hoax", RelevanceScope(exact_terms=("quantum chip",), exclusions=("hoax",))
    )
    assert (excluded.relevant, excluded.stage) == (False, "excluded")

    false_positive = RelevanceCascade().evaluate("Weather is sunny", RelevanceScope(exact_terms=("quantum",)))
    assert (false_positive.relevant, false_positive.stage) == (False, "none")


def test_disabled_monitor_cannot_schedule_work_and_survives_restart(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Restart Source", "slug": "restart-source"})
    policy = _policy(tmp_db)
    monitors = MonitorService(tmp_db)
    monitor = monitors.create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "next_check_at": T0,
        }
    )
    monitors.disable(monitor["id"])
    assert SchedulerService(tmp_db).tick(now=T0)["job_ids"] == []
    assert MonitorService(tmp_db).get(monitor["id"])["enabled"] == 0

    core.delete_source(source["id"])
    with pytest.raises(DomainNotFound):
        monitors.enable(monitor["id"], next_check_at=T0)


def test_scheduled_monitor_has_local_only_allowlisted_worker_handler(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Worker Source", "slug": "worker-source"})
    policy = _policy(tmp_db)
    monitor = MonitorService(tmp_db).create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )
    scheduled = SchedulerService(tmp_db).tick(now=T0)
    worker = WorkerProcess(tmp_db, MonitorExecutionService(tmp_db).handlers(), worker_id="monitor-worker")
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"
    assert MonitorExecutionService(tmp_db).handle(
        {"payload": {"monitor_id": monitor["id"], "candidate_text": "irrelevant text"}, "updated_at": "2026-08-16T12:01:00Z"}
    )["paid_used"] is False
    assert scheduled["job_ids"]


def test_monitoring_api_exposes_policy_monitor_and_local_relevance(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    password = "a-long-test-password-12345"
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": password}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    source = client.post(
        "/api/v1/sources", headers=headers, json={"name": "API Source", "slug": "api-source"}
    ).json()
    policy = client.post(
        "/api/v1/monitoring-policies",
        headers=headers,
        json={
            "name": "API policy",
            "allowed_channels": ["rss"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        },
    )
    assert policy.status_code == 201
    monitor = client.post(
        "/api/v1/monitors",
        headers=headers,
        json={
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy.json()["id"],
            "next_check_at": T0,
        },
    )
    assert monitor.status_code == 201
    relevance = client.post(
        "/api/v1/relevance/evaluate",
        headers=headers,
        json={"text": "A QPU launch", "vocabulary": ["QPU"]},
    )
    assert relevance.status_code == 200
    assert relevance.json()["stage"] == "vocabulary"

    category = client.post("/api/v1/categories", headers=headers, json={"slug": "science", "name": "Science"}).json()
    topic = client.post(
        "/api/v1/topics",
        headers=headers,
        json={"category_id": category["id"], "slug": "qpu", "name": "QPU"},
    ).json()
    assisted = client.post(
        f"/api/v1/topics/{topic['id']}/scope-suggestions/assist",
        headers=headers,
        json={"text": "QPU fabrication", "limit": 2},
    )
    assert assisted.status_code == 201
    assert assisted.json()["items"]
