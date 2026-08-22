from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.acquisition import (
    AcquisitionBlocked,
    AcquisitionService,
    AcquisitionTimeout,
    HttpResponse,
)
from newsroom.domain import CoreService, DomainNotFound, DomainValidation
from newsroom.migrations import (
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
    apply_migrations,
)
from newsroom.monitoring import (
    MonitorService,
    MonitorExecutionService,
    MonitoringPolicyService,
    RelevanceCascade,
    RelevanceScope,
    ScopeSuggestionService,
    monitor_job_completion_hook,
)
from newsroom.jobs import (
    BudgetService,
    JobService,
    RESEARCH_QUESTION_JOB_TYPE,
    SchedulerService,
)
from newsroom.research_questions import ResearchQuestionService
from newsroom.runtime import build_worker_queue
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
    assert apply_migrations(tmp_db).applied_versions == tuple(range(1, 23))
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


class SequencedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, *, headers, policy):
        self.requests.append({"url": url, "headers": dict(headers)})
        if not self.responses:
            raise RuntimeError("SequencedTransport has no more responses")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


FEED_V1 = b"""<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Item 1</title><link>https://example.test/item-1</link><description>Description 1</description></item>
</channel></rss>"""

FEED_V2 = b"""<rss version="2.0"><channel><title>Test Feed</title>
<item><title>Item 1 (Updated)</title><link>https://example.test/item-1</link><description>Description 1 updated</description></item>
<item><title>Item 2</title><link>https://example.test/item-2</link><description>Description 2</description></item>
</channel></rss>"""


def test_scheduled_monitor_has_local_only_allowlisted_worker_handler(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Worker Source", "slug": "worker-source", "homepage_url": "https://example.test/news"})
    policy = _policy(tmp_db)
    monitor = MonitorService(tmp_db).create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )
    scheduled = SchedulerService(tmp_db).tick(now=T0)
    assert scheduled["job_ids"]

    transport = SequencedTransport([
        HttpResponse(200, "https://example.test/news", {"content-type": "text/html", "etag": '"v1"'}, b"<html><title>News</title><p>Initial text</p></html>"),
        HttpResponse(304, "https://example.test/news", {"etag": '"v1"'}, b""),
    ])
    acq = AcquisitionService(tmp_db, transport=transport)
    exec_service = MonitorExecutionService(tmp_db, acquisition_service=acq)
    worker = WorkerProcess(tmp_db, exec_service.handlers(), worker_id="monitor-worker")

    # First run acquires initial content
    first = worker.run_once(now=T0)
    assert first["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    # Second run checks unchanged content
    SchedulerService(tmp_db).tick(now="2026-08-16T12:01:00Z")
    second = worker.run_once(now="2026-08-16T12:01:00Z")
    assert second["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"

    # Manual candidate_text relevance path still works
    assert exec_service.handle(
        {"payload": {"monitor_id": monitor["id"], "candidate_text": "irrelevant text"}, "updated_at": "2026-08-16T12:02:00Z"}
    )["paid_used"] is False


def test_monitor_source_acquisition_lifecycle_content_a_unchanged_content_b(tmp_db):
    """Release gate test: content A -> changed, content A again -> no_change (no duplicate version), content B -> changed (new version)."""
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({
        "name": "Lifecycle Source",
        "slug": "lifecycle-source",
        "homepage_url": "https://example.test/feed-page",
    })
    policy = _policy(tmp_db, allowed_channels=["direct_http"], base_cadence_seconds=60)
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    transport = SequencedTransport([
        # Tick 1: Content A
        HttpResponse(200, "https://example.test/feed-page", {"content-type": "text/html", "etag": '"v1"'}, b"<html><title>Title A</title><p>Content A</p></html>"),
        # Tick 2: Content A again (304)
        HttpResponse(304, "https://example.test/feed-page", {"etag": '"v1"'}, b""),
        # Tick 3: Content B
        HttpResponse(200, "https://example.test/feed-page", {"content-type": "text/html", "etag": '"v2"'}, b"<html><title>Title B</title><p>Content B (Changed)</p></html>"),
    ])
    acq = AcquisitionService(tmp_db, transport=transport)
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db, acquisition_service=acq).handlers(),
        worker_id="worker-lifecycle",
        queue=queue,
    )

    # 1. Content A
    scheduled_1 = SchedulerService(tmp_db).tick(now=T0)
    assert len(scheduled_1["job_ids"]) == 1
    finished_1 = worker.run_once(now=T0)
    assert finished_1["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    conn = storage.connect(tmp_db)
    try:
        doc = conn.execute("SELECT * FROM documents WHERE source_id = ?", (source["id"],)).fetchone()
        assert doc is not None
        assert doc["title"] == "Title A"
        versions = conn.execute("SELECT * FROM document_versions WHERE document_id = ? ORDER BY retrieved_at", (doc["id"],)).fetchall()
        assert len(versions) == 1
        v1_id = versions[0]["id"]
    finally:
        conn.close()

    # 2. Content A again (unchanged)
    t1 = "2026-08-16T12:01:00Z"
    scheduled_2 = SchedulerService(tmp_db).tick(now=t1)
    assert len(scheduled_2["job_ids"]) == 1
    finished_2 = worker.run_once(now=t1)
    assert finished_2["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"

    conn = storage.connect(tmp_db)
    try:
        versions = conn.execute("SELECT * FROM document_versions WHERE document_id = ?", (doc["id"],)).fetchall()
        assert len(versions) == 1  # No duplicate version created!
    finally:
        conn.close()

    # 3. Content B (changed)
    t2 = "2026-08-16T12:05:00Z"
    scheduled_3 = SchedulerService(tmp_db).tick(now=t2)
    assert len(scheduled_3["job_ids"]) == 1
    finished_3 = worker.run_once(now=t2)
    assert finished_3["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    conn = storage.connect(tmp_db)
    try:
        versions = conn.execute("SELECT * FROM document_versions WHERE document_id = ? ORDER BY retrieved_at", (doc["id"],)).fetchall()
        assert len(versions) == 2  # Exactly 2 versions
        assert versions[1]["id"] != v1_id
        assert versions[1]["content_hash"] != versions[0]["content_hash"]
    finally:
        conn.close()


def test_monitor_feed_acquisition_lifecycle(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({
        "name": "Feed Source",
        "slug": "feed-source",
        "feed_url": "https://example.test/feed.xml",
        "source_kind": "feed",
    })
    policy = _policy(tmp_db, allowed_channels=["rss"], base_cadence_seconds=60)
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    transport = SequencedTransport([
        HttpResponse(200, "https://example.test/feed.xml", {"content-type": "application/rss+xml", "etag": '"f1"'}, FEED_V1),
        HttpResponse(304, "https://example.test/feed.xml", {"etag": '"f1"'}, b""),
        HttpResponse(200, "https://example.test/feed.xml", {"content-type": "application/rss+xml", "etag": '"f2"'}, FEED_V2),
    ])
    acq = AcquisitionService(tmp_db, transport=transport)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db, acquisition_service=acq).handlers(),
        worker_id="worker-feed",
    )

    # 1. First poll -> new items -> changed (relevance unknown)
    SchedulerService(tmp_db).tick(now=T0)
    fin1 = worker.run_once(now=T0)
    assert fin1["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE source_id = ?", (source["id"],)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    finally:
        conn.close()

    # 2. Second poll -> 304 -> no_change
    t1 = "2026-08-16T12:01:00Z"
    SchedulerService(tmp_db).tick(now=t1)
    fin2 = worker.run_once(now=t1)
    assert fin2["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "no_change"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    finally:
        conn.close()

    # 3. Third poll -> new + changed entries -> changed (relevance unknown)
    t2 = "2026-08-16T12:05:00Z"
    SchedulerService(tmp_db).tick(now=t2)
    fin3 = worker.run_once(now=t2)
    assert fin3["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents WHERE source_id = ?", (source["id"],)).fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 3
    finally:
        conn.close()


def test_monitor_acquisition_timeout_causes_retry_and_records_activity(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({
        "name": "Timeout Source",
        "slug": "timeout-source",
        "homepage_url": "https://example.test/timeout",
    })
    policy = _policy(tmp_db)
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    transport = SequencedTransport([AcquisitionTimeout("simulated connection timeout")])
    acq = AcquisitionService(tmp_db, transport=transport)
    queue = JobService(tmp_db, backoff_base_seconds=10)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db, acquisition_service=acq).handlers(),
        worker_id="worker-timeout",
        queue=queue,
    )

    SchedulerService(tmp_db).tick(now=T0)
    finished = worker.run_once(now=T0)
    assert finished["status"] == "queued"
    assert finished["failure_cause"] == "retryable_handler_failure"

    mon = MonitorService(tmp_db).get(monitor["id"])
    assert mon["last_result"] == "error"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert len(activity) == 1
    assert activity[0]["outcome"] == "error"
    assert activity[0]["error_code"] == "AcquisitionTimeout"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 0
    finally:
        conn.close()


def test_monitor_acquisition_blocked_is_terminal_and_records_activity(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({
        "name": "Private Source",
        "slug": "private-source",
        "homepage_url": "http://127.0.0.1/private",
    })
    policy = _policy(tmp_db)
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    queue = JobService(tmp_db)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db).handlers(),
        worker_id="worker-blocked",
        queue=queue,
    )

    SchedulerService(tmp_db).tick(now=T0)
    finished = worker.run_once(now=T0)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "AcquisitionBlocked"

    mon = MonitorService(tmp_db).get(monitor["id"])
    assert mon["last_result"] == "error"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert len(activity) == 1
    assert activity[0]["outcome"] == "error"
    assert activity[0]["error_code"] == "AcquisitionBlocked"

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 0
    finally:
        conn.close()


def test_monitor_missing_source_url_configuration_records_error(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "No URL Source", "slug": "no-url-source"})
    policy = _policy(tmp_db)
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    queue = JobService(tmp_db)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db).handlers(),
        worker_id="worker-nourl",
        queue=queue,
    )

    SchedulerService(tmp_db).tick(now=T0)
    finished = worker.run_once(now=T0)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "DomainValidation"

    mon = MonitorService(tmp_db).get(monitor["id"])
    assert mon["last_result"] == "error"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert len(activity) == 1
    assert activity[0]["outcome"] == "error"
    assert activity[0]["error_code"] == "not_configured"


def test_monitor_unsupported_target_type_records_error(tmp_db):
    apply_migrations(tmp_db)
    core, topic = _category_and_topic(tmp_db)
    policy = _policy(tmp_db)
    monitor = MonitorService(tmp_db).create({
        "target_type": "topic",
        "target_id": topic["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    queue = JobService(tmp_db)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db).handlers(),
        worker_id="worker-topic",
        queue=queue,
    )

    SchedulerService(tmp_db).tick(now=T0)
    finished = worker.run_once(now=T0)
    assert finished["status"] == "failed"
    assert finished["failure_cause"] == "DomainValidation"

    mon = MonitorService(tmp_db).get(monitor["id"])
    assert mon["last_result"] == "error"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert len(activity) == 1
    assert activity[0]["outcome"] == "error"
    assert activity[0]["error_code"] == "unsupported_target"


def test_monitor_budget_exhaustion_records_error_via_completion_hook(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({
        "name": "Budget Source",
        "slug": "budget-source",
        "homepage_url": "https://example.test/budget",
    })
    policy = _policy(tmp_db, query_budget=1)
    monitor = MonitorService(tmp_db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "next_check_at": T0,
    })

    budgets = BudgetService(tmp_db)
    budgets.configure_limit("global", None, "daily", "acquisition_units", 1)

    transport = SequencedTransport([
        HttpResponse(200, "https://example.test/budget", {"content-type": "text/html"}, b"<html><p>Item 1</p></html>"),
    ])
    acq = AcquisitionService(tmp_db, transport=transport)
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db, acquisition_service=acq).handlers(),
        worker_id="worker-budget",
        queue=queue,
    )

    # 1. First run consumes the 1 acquisition unit
    SchedulerService(tmp_db).tick(now=T0)
    fin1 = worker.run_once(now=T0)
    assert fin1["status"] == "succeeded"

    # 1b. Phase 19 leaves the acquired version's durable processing obligation
    # queued; drain it (this worker only registers monitor handlers, so the
    # obligation truthfully fails as unknown_job_type) before step 2.
    processing = worker.run_once(now=T0)
    assert processing is not None
    assert processing["job_type"] == "document_version_process"

    # 2. Second tick schedules another job, but global acquisition budget is now exhausted
    t1 = "2026-08-16T12:01:00Z"
    SchedulerService(tmp_db).tick(now=t1)
    # Attempting to claim the job will fail due to BudgetExhausted
    fin2 = worker.run_once(now=t1)
    assert fin2 is None  # Claim failed, marked failed in DB

    # Verify monitor activity recorded budget_exhausted error via completion hook
    mon = MonitorService(tmp_db).get(monitor["id"])
    assert mon["last_result"] == "error"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert activity[0]["outcome"] == "error"
    assert activity[0]["error_code"] == "budget_exhausted"


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


def test_phase14_migration_widens_outcome_and_preserves_existing_rows(tmp_db):
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
            ):
                for statement in statements:
                    conn.execute(statement)
            for version in range(1, 14):
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, "2026-08-16T00:00:00Z"),
                )
            conn.execute(
                "INSERT INTO monitoring_policies (id, name, allowed_channels, base_cadence_seconds, min_cadence_seconds, max_cadence_seconds, created_at, updated_at) VALUES ('pol-old', 'Old policy', '[]', 60, 30, 300, ?, ?)",
                (T0, T0),
            )
            conn.execute(
                "INSERT INTO monitors (id, target_type, target_id, policy_id, next_check_at, created_at, updated_at) VALUES ('mon-old', 'source', 'src-old', 'pol-old', ?, ?, ?)",
                (T0, T0, T0),
            )
            conn.execute(
                "INSERT INTO monitor_activity (id, monitor_id, outcome, new_items, changed_items, relevant_items, error_code, observed_at, created_at) VALUES ('act-old', 'mon-old', 'no_change', 0, 0, 0, NULL, ?, ?)",
                (T0, T0),
            )
    finally:
        conn.close()

    result = apply_migrations(tmp_db)
    assert result.applied_versions == (14, 15, 16, 17, 18, 19, 20, 21, 22)

    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute("SELECT * FROM monitor_activity").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == "act-old"
        assert rows[0]["outcome"] == "no_change"
        ddl = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'monitor_activity'"
        ).fetchone()[0]
        assert "'changed'" in ddl
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE monitor_activity SET outcome = 'changed'")
    finally:
        conn.close()


def test_scheduler_enqueue_preserves_previous_execution_result(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Preserve Source", "slug": "preserve-source"})
    policy = _policy(tmp_db, base_cadence_seconds=60)
    monitors = MonitorService(tmp_db)
    monitor = monitors.create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )
    monitors.record_activity(monitor["id"], "no_change", observed_at=T0)

    # Force the monitor due so the scheduler actually enqueues the next run
    # while the previous execution result is still the latest result.
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("UPDATE monitors SET next_check_at = ? WHERE id = ?", (T0, monitor["id"]))
    finally:
        conn.close()
    SchedulerService(tmp_db).tick(now=T0)
    current = MonitorService(tmp_db).get(monitor["id"])
    assert current["last_result"] == "no_change"
    assert current["next_check_at"] != T0

    monitors.record_activity(monitor["id"], "error", error_code="timeout", observed_at=T0)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("UPDATE monitors SET next_check_at = ? WHERE id = ?", (T0, monitor["id"]))
    finally:
        conn.close()
    SchedulerService(tmp_db).tick(now=T0)
    current = MonitorService(tmp_db).get(monitor["id"])
    assert current["last_result"] == "error"


def test_scheduler_disables_missing_target_without_overwriting_execution_result(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Vanishing Source", "slug": "vanishing-source"})
    policy = _policy(tmp_db)
    monitors = MonitorService(tmp_db)
    monitor = monitors.create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )
    monitors.record_activity(monitor["id"], "no_change", observed_at=T0)
    core.delete_source(source["id"])
    SchedulerService(tmp_db).tick(now="2026-08-16T12:03:00Z")
    current = MonitorService(tmp_db).get(monitor["id"])
    assert current["enabled"] == 0
    assert current["last_result"] == "no_change"


def test_acquisition_change_records_changed_without_claiming_relevance(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source(
        {
            "name": "Relevance Boundary Source",
            "slug": "relevance-boundary-source",
            "homepage_url": "https://example.test/boundary",
        }
    )
    policy = _policy(tmp_db, allowed_channels=["direct_http"])
    monitor = MonitorService(tmp_db).create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )

    transport = SequencedTransport([
        HttpResponse(200, "https://example.test/boundary", {"content-type": "text/html", "etag": '"b1"'}, b"<html><title>Boundary</title><p>New content</p></html>"),
    ])
    acq = AcquisitionService(tmp_db, transport=transport)
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(
        tmp_db,
        MonitorExecutionService(tmp_db, acquisition_service=acq).handlers(),
        worker_id="worker-boundary",
        queue=queue,
    )

    SchedulerService(tmp_db).tick(now=T0)
    finished = worker.run_once(now=T0)
    assert finished["status"] == "succeeded"
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] == "changed"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert len(activity) == 1
    assert activity[0]["outcome"] == "changed"
    assert activity[0]["relevant_items"] == 0
    assert activity[0]["new_items"] == 1 or activity[0]["changed_items"] == 1


def test_explicit_relevance_path_still_records_relevant_change(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Relevance Source", "slug": "relevance-source"})
    policy = _policy(tmp_db)
    monitor = MonitorService(tmp_db).create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )
    exec_service = MonitorExecutionService(tmp_db)

    irrelevant = exec_service.handle(
        {"payload": {"monitor_id": monitor["id"], "candidate_text": "unrelated weather"}, "updated_at": T0}
    )
    assert irrelevant["outcome"] == "no_change"
    assert irrelevant["relevance"]["relevant"] is False

    relevant = exec_service.handle(
        {"payload": {"monitor_id": monitor["id"], "candidate_text": source["name"]}, "updated_at": "2026-08-16T12:01:00Z"}
    )
    assert relevant["outcome"] == "relevant_change"
    activity = MonitorService(tmp_db).activity(monitor["id"])["items"]
    assert activity[0]["outcome"] == "relevant_change"
    assert activity[0]["relevant_items"] == 1


def test_changed_cadence_keeps_interval_without_acceleration(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Cadence Source", "slug": "cadence-source"})
    policy = _policy(tmp_db)  # base 60, min 30, max 300, no_change_multiplier 2.0
    monitors = MonitorService(tmp_db)
    monitor = monitors.create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )
    after_quiet = monitors.record_activity(monitor["id"], "no_change", observed_at=T0)
    assert after_quiet["next_check_at"] == "2026-08-16T12:02:00Z"
    after_changed = monitors.record_activity(
        monitor["id"], "changed", new_items=1, observed_at="2026-08-16T12:02:00Z"
    )
    assert after_changed["next_check_at"] == "2026-08-16T12:04:00Z"
    assert after_changed["last_result"] == "changed"


def test_monitor_hook_ignores_research_question_jobs(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = service.create(
        {
            "question": "hook no-op",
            "origin_type": "user",
            "search_attempt_budget": 1,
            "query_budget": 1,
        }
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO jobs (id, job_type, status, payload_json, research_question_id, priority, max_attempts, created_at, updated_at)
                VALUES (?, ?, 'failed', ?, ?, 0, 1, ?, ?)
                """,
                (
                    "job-rq-hook",
                    RESEARCH_QUESTION_JOB_TYPE,
                    json.dumps({"research_question_id": question["id"]}),
                    question["id"],
                    T0,
                    T0,
                ),
            )
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", ("job-rq-hook",)).fetchone()
            monitor_job_completion_hook(conn, row, "failed", {"trigger": "budget", "error_code": "budget_exhausted"})
    finally:
        conn.close()
    assert MonitorService(tmp_db).list()["items"] == []
    assert service.get(question["id"])["attempts"] == []
