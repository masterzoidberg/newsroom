from __future__ import annotations

import json

import pytest

from newsroom import storage
from newsroom.domain import CoreService, DomainConflict, DomainNotFound
from newsroom.evidence import EvidenceService
from newsroom.jobs import (
    AUTOMATIC_ALERT_STAGE_JOB_TYPE,
    AUTOMATIC_REPORT_STAGE_JOB_TYPE,
    AUTOMATIC_STORY_STAGE_JOB_TYPE,
    DOCUMENT_VERSION_PROCESS_JOB_TYPE,
    BudgetService,
    JobConflict,
    JobService,
    MONITOR_CHECK_JOB_TYPE,
    RESEARCH_QUESTION_JOB_TYPE,
    SchedulerService,
    compose_completion_hooks,
)
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorService, MonitoringPolicyService
from newsroom.research_questions import (
    ResearchQuestionExecutionService,
    ResearchQuestionService,
    research_job_completion_hook,
    research_job_rerun_factory,
    research_job_recovery_hook,
)
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.scheduler import SchedulerProcess
from newsroom.worker import WorkerProcess, merge_handlers


T0 = "2026-08-16T12:00:00Z"
T1 = "2026-08-16T12:00:30Z"
T2 = "2026-08-16T12:02:00Z"


def _hooked_queue(db_path, *, lease_seconds=120, **kwargs):
    return JobService(
        db_path,
        lease_seconds=lease_seconds,
        recovery_hook=research_job_recovery_hook,
        completion_hook=research_job_completion_hook,
        rerun_factory=research_job_rerun_factory,
        **kwargs,
    )


def _ledger_fixture(db_path):
    core = CoreService(db_path)
    source = core.create_source(
        {"name": "Local Outlet", "slug": "local-outlet", "source_kind": "web", "default_quality": "unknown"}
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://local.test/story",
            "title": "A developing story",
        }
    )
    story = core.create_story({"headline": "A developing story"})
    ledger = EvidenceService(db_path)
    version = ledger.create_document_version(
        document["id"], {"content_hash": "worker-v1", "content_kind": "excerpt"}
    )
    span = ledger.create_evidence_span(
        version["id"], {"excerpt": "The outlet reported an unresolved detail."}
    )
    claim = ledger.create_claim(
        story["id"], {"proposition": "The unresolved detail is true", "importance": "major"}
    )
    return story, claim, span


def _question(db_path, *, question="a question about anything", search_attempt_budget=1, query_budget=2):
    service = ResearchQuestionService(db_path)
    return service.create(
        {
            "question": question,
            "origin_type": "user",
            "search_attempt_budget": search_attempt_budget,
            "query_budget": query_budget,
        }
    )


def test_production_handler_coverage(tmp_db):
    apply_migrations(tmp_db)
    handlers = build_worker_handlers(tmp_db)
    produced = {
        SchedulerService.job_type,
        ResearchQuestionService.job_type,
        DOCUMENT_VERSION_PROCESS_JOB_TYPE,
        AUTOMATIC_STORY_STAGE_JOB_TYPE,
        AUTOMATIC_REPORT_STAGE_JOB_TYPE,
        AUTOMATIC_ALERT_STAGE_JOB_TYPE,
    }
    missing = produced - set(handlers)
    assert not missing, f"enqueue producers without a production handler: {sorted(missing)}"
    assert set(handlers) == produced


def test_merge_handlers_rejects_silent_collision():
    def first(_job):
        return None

    def second(_job):
        return None

    with pytest.raises(ValueError, match="duplicate handler registration"):
        merge_handlers({"shared": first}, {"shared": second})


def test_research_question_success_path(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, question="unresolved detail")
    job = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)
    assert job["job_type"] == RESEARCH_QUESTION_JOB_TYPE

    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    result = worker.run_once(now=T0)

    assert result["status"] == "succeeded"
    current = service.get(question["id"])
    attempt = current["attempts"][0]
    assert attempt["status"] == "succeeded"
    assert attempt["job_id"] == job["id"]
    assert attempt["completed_at"] is not None
    assert attempt["outcome_note"].startswith("pursuit linked")
    assert current["evidence"], "pursuit should link relevant evidence spans"
    assert current["evidence"][0]["relationship"] == "contextualizes"


def test_research_question_failure_path(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db)
    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)

    class FailingSearch:
        def search(self, *args, **kwargs):
            raise RuntimeError("deterministic search failure")

    execution = ResearchQuestionExecutionService(tmp_db, search=FailingSearch())
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, execution.handlers(), worker_id="worker-a", queue=queue)
    result = worker.run_once(now=T0)

    assert result["status"] == "failed"
    assert result["failure_cause"] == "RuntimeError"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["completed_at"] is not None
    assert "deterministic search failure" in attempt["outcome_note"]


def test_unknown_job_type_fails_explicitly(tmp_db):
    apply_migrations(tmp_db)
    queue = JobService(tmp_db)
    job = queue.enqueue("fabricated_job_type", {})
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    result = worker.run_once(now=T0)

    assert result["status"] == "failed"
    assert result["failure_cause"] == "unknown_job_type"
    assert result["attempts_detail"][0]["error_code"] == "unknown_job_type"
    assert result["attempts_detail"][0]["error_detail"] == "fabricated_job_type"


def test_scheduler_integration_consumed_by_production_worker(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    due = service.create(
        {
            "question": "unresolved detail",
            "origin_type": "user",
            "search_attempt_budget": 1,
            "query_budget": 2,
            "next_attempt_at": "2026-08-16T11:00:00Z",
        }
    )

    process = SchedulerProcess(tmp_db)
    scheduled = process.run_once()
    assert scheduled["research_pursuit"]["scheduled_count"] == 1
    job_id = scheduled["research_pursuit"]["job_ids"][0]

    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    outcome = worker.run_once(now=T0)

    assert outcome["status"] == "succeeded"
    assert outcome["job_type"] == RESEARCH_QUESTION_JOB_TYPE
    attempt = service.get(due["id"])["attempts"][0]
    assert attempt["status"] == "succeeded"
    assert attempt["job_id"] == job_id


def _claimed_running(db_path, question, *, lease_seconds=10, query="anything"):
    service = ResearchQuestionService(db_path)
    job = service.pursue(question["id"], mode="manual", query=query, query_units=1)
    queue = _hooked_queue(db_path, lease_seconds=lease_seconds)
    queue.claim(job["id"], "worker-a", now=T0)
    attempt = service.get(question["id"])["attempts"][0]
    service.record_attempt(attempt["id"], "running", started_at=T0)
    return service, job, queue


def test_production_worker_queue_composes_domain_completion_hooks(tmp_db):
    apply_migrations(tmp_db)
    queue = build_worker_queue(tmp_db)
    assert queue.recovery_hook is research_job_recovery_hook
    # Phase 19 chains the Research Question and DocumentVersion processing
    # rerun factories; the composed factory still routes research jobs through
    # the research factory and declines unknown job types (generic fallback).
    assert queue.rerun_factory is not None
    assert queue.rerun_factory is not research_job_rerun_factory
    # Completion hooks are centrally composed; the Research Question hook is no
    # longer responsible for Monitor reconciliation.
    assert queue.completion_hook is not research_job_completion_hook


def test_compose_completion_hooks_runs_each_domain_hook(tmp_db):
    apply_migrations(tmp_db)
    calls = []

    def first(conn, job_row, status, context=None):
        calls.append(("first", status, dict(context or {}) if context else None))

    def second(conn, job_row, status, context=None):
        calls.append(("second", status))

    composed = compose_completion_hooks(first, second)
    assert composed is not None
    composed(None, None, "failed", {"trigger": "budget", "error_code": "budget_exhausted"})
    assert calls == [("first", "failed", {"trigger": "budget", "error_code": "budget_exhausted"}), ("second", "failed")]


def test_compose_completion_hooks_filters_none_and_rejects_duplicates():
    def one(conn, job_row, status, context=None):
        pass

    assert compose_completion_hooks(None, None) is None
    assert compose_completion_hooks(one) is one
    with pytest.raises(ValueError, match="duplicate completion hook"):
        compose_completion_hooks(one, one)
    with pytest.raises(TypeError):
        compose_completion_hooks("not-a-callable")


def test_research_hook_ignores_monitor_jobs(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    source = core.create_source({"name": "Hook Source", "slug": "hook-source"})
    policy = MonitoringPolicyService(tmp_db).create(
        {
            "name": "Hook policy",
            "allowed_channels": ["rss", "direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        }
    )
    monitor = MonitorService(tmp_db).create(
        {"target_type": "source", "target_id": source["id"], "policy_id": policy["id"], "next_check_at": T0}
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO jobs (id, job_type, status, payload_json, monitor_id, priority, max_attempts, created_at, updated_at)
                VALUES (?, ?, 'failed', ?, ?, 0, 3, ?, ?)
                """,
                (
                    "job-monitor-hook",
                    MONITOR_CHECK_JOB_TYPE,
                    json.dumps({"monitor_id": monitor["id"]}),
                    monitor["id"],
                    T0,
                    T0,
                ),
            )
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", ("job-monitor-hook",)).fetchone()
            research_job_completion_hook(conn, row, "failed", {"trigger": "budget", "error_code": "budget_exhausted"})
    finally:
        conn.close()
    assert MonitorService(tmp_db).activity(monitor["id"])["items"] == []
    assert MonitorService(tmp_db).get(monitor["id"])["last_result"] is None


def test_terminal_lease_expiry_reconciles_attempt_to_failed(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2)
    _, job, queue = _claimed_running(tmp_db, question)

    assert queue.recover_expired(now=T1) == 1

    state = queue.get(job["id"])
    assert state["status"] == "failed"
    assert state["failure_cause"] == "lease_expired"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "failed"
    assert "lease expired" in attempt["outcome_note"]
    assert attempt["completed_at"] is not None


def test_retryable_lease_expiry_requeues_without_terminally_failing_attempt(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2, question="unresolved detail")
    _, job, queue = _claimed_running(tmp_db, question, query="unresolved detail")
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("UPDATE jobs SET max_attempts = 2 WHERE id = ?", (job["id"],))
    finally:
        conn.close()

    assert queue.recover_expired(now=T1) == 1

    state = queue.get(job["id"])
    assert state["status"] == "queued"
    assert state["next_attempt_at"] is not None
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "planned"
    assert attempt["completed_at"] is None

    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-b", queue=queue)
    outcome = worker.run_once(now=T2)
    assert outcome["status"] == "succeeded"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "succeeded"


def test_lease_recovery_is_idempotent(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2)
    _, job, queue = _claimed_running(tmp_db, question)

    assert queue.recover_expired(now=T1) == 1
    assert queue.recover_expired(now=T1) == 0

    current = service.get(question["id"])
    assert len(current["attempts"]) == 1
    assert current["attempts"][0]["status"] == "failed"
    assert queue.get(job["id"])["status"] == "failed"


def test_recovery_aligns_owned_terminal_attempt_to_job_outcome(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2)
    _, job, queue = _claimed_running(tmp_db, question)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE research_question_attempts SET status = 'succeeded', outcome_note = 'stale handler write', completed_at = ? WHERE job_id = ?",
                (T0, job["id"]),
            )
    finally:
        conn.close()

    assert queue.recover_expired(now=T1) == 1
    assert queue.get(job["id"])["status"] == "failed"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["status"] not in {"succeeded", "partial"}
    assert "lease expired" in attempt["outcome_note"]


def test_recovery_does_not_overwrite_unrelated_terminal_attempt(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2)
    first = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    attempt_id = service.get(question["id"])["attempts"][0]["id"]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE research_question_attempts SET status = 'succeeded', outcome_note = 'historical result', completed_at = ? WHERE id = ?",
                (T0, attempt_id),
            )
            conn.execute(
                """
                INSERT INTO jobs
                    (id, job_type, status, payload_json, research_question_id,
                     lease_owner, lease_expires_at, attempts, max_attempts, created_at, updated_at)
                VALUES (?, ?, 'running', ?, ?, 'worker-a', ?, 1, 1, ?, ?)
                """,
                (
                    "job_rerun",
                    RESEARCH_QUESTION_JOB_TYPE,
                    json.dumps({"research_question_id": question["id"], "attempt_id": attempt_id}),
                    question["id"],
                    T1,
                    T0,
                    T0,
                ),
            )
    finally:
        conn.close()

    queue = _hooked_queue(tmp_db, lease_seconds=10)
    assert queue.recover_expired(now=T2) == 1
    assert queue.get(first["id"])["status"] == "queued"
    assert queue.get("job_rerun")["status"] == "failed"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "succeeded"
    assert attempt["outcome_note"] == "historical result"


def test_lease_loss_during_completion_cannot_leave_succeeded_attempt(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, question="unresolved detail")
    job = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)
    queue = _hooked_queue(tmp_db, lease_seconds=10)
    queue.claim(job["id"], "worker-a", now=T0)
    attempt = service.get(question["id"])["attempts"][0]
    service.record_attempt(attempt["id"], "running", started_at=T0)

    outcome = ResearchQuestionExecutionService(tmp_db).handle(queue.get(job["id"]))
    assert outcome["attempt_status"] == "succeeded"
    assert outcome["outcome_note"].startswith("pursuit linked")

    assert queue.recover_expired(now=T1) == 1
    with pytest.raises(JobConflict):
        queue.complete(job["id"], "worker-a", "succeeded", outcome=outcome, now=T1)

    assert queue.get(job["id"])["status"] == "failed"
    final = service.get(question["id"])["attempts"][0]
    assert final["status"] not in {"succeeded", "partial"}
    assert final["status"] == "failed"
    assert "lease expired" in final["outcome_note"]


def test_stale_terminal_failed_attempt_cannot_leave_succeeded_job(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, question="unresolved detail")
    job = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)
    queue = _hooked_queue(tmp_db)
    queue.claim(job["id"], "worker-a", now=T0)
    attempt = service.get(question["id"])["attempts"][0]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE research_question_attempts SET status = 'failed', outcome_note = 'stale handler failure', completed_at = ? WHERE id = ?",
                (T0, attempt["id"]),
            )
    finally:
        conn.close()

    from newsroom.domain import DomainConflict

    with pytest.raises(DomainConflict):
        ResearchQuestionExecutionService(tmp_db).handle(queue.get(job["id"]))

    completed = queue.complete(
        job["id"],
        "worker-a",
        "failed",
        error_code="DomainConflict",
        error_detail="terminal research question attempt cannot change status",
        retryable=False,
        now=T0,
    )
    assert completed["status"] == "failed"
    assert queue.get(job["id"])["status"] == "failed"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "failed"


def test_cancel_queued_research_job_reconciles_attempt_to_cancelled(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db)
    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    queue = build_worker_queue(tmp_db)

    cancelled = queue.cancel(job["id"], reason="user_request")
    assert cancelled["status"] == "cancelled"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "cancelled"
    assert attempt["completed_at"] is not None
    assert "user_request" in attempt["outcome_note"]


def test_cancel_running_research_job_completion_maps_attempt_to_cancelled(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db)
    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    queue = build_worker_queue(tmp_db)
    queue.claim(job["id"], "worker-a", now=T0)
    attempt = service.get(question["id"])["attempts"][0]
    service.record_attempt(attempt["id"], "running", started_at=T0)

    queue.cancel(job["id"], reason="user_request")
    completed = queue.complete(job["id"], "worker-a", "succeeded", now=T0)
    assert completed["status"] == "cancelled"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "cancelled"
    assert "user_request" in attempt["outcome_note"]


def test_budget_exhaustion_at_claim_terminalizes_job_and_attempt(tmp_db):
    apply_migrations(tmp_db)
    budgets = BudgetService(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db)
    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    budgets.configure_limit("research_question", question["id"], "daily", "acquisition_units", 0)

    queue = _hooked_queue(tmp_db, budget_service=budgets)
    assert queue.claim(job["id"], "worker-a", now=T0) is None

    state = queue.get(job["id"])
    assert state["status"] == "failed"
    assert state["failure_cause"] == "budget_exhausted"
    assert state["attempts_detail"] == []
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["completed_at"] is not None
    assert "budget" in attempt["outcome_note"]

    assert queue.claim(job["id"], "worker-b", now=T0) is None
    assert queue.get(job["id"])["status"] == "failed"


def test_retryable_completion_failure_requeues_attempt_and_retry_succeeds(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2, question="unresolved detail")
    job = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("UPDATE jobs SET max_attempts = 2 WHERE id = ?", (job["id"],))
    finally:
        conn.close()

    queue = _hooked_queue(tmp_db, backoff_base_seconds=20)
    queue.claim(job["id"], "worker-a", now=T0)
    attempt = service.get(question["id"])["attempts"][0]
    service.record_attempt(attempt["id"], "running", started_at=T0)

    requeued = queue.complete(
        job["id"], "worker-a", "failed", error_code="transient", error_detail="temporary blip", retryable=True, now=T0
    )
    assert requeued["status"] == "queued"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "planned"
    assert attempt["completed_at"] is None

    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-b", queue=queue)
    outcome = worker.run_once(now=T2)
    assert outcome["status"] == "succeeded"
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "succeeded"


def test_terminal_job_and_attempt_stable_under_repeat_events(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, question="unresolved detail")
    job = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    result = worker.run_once(now=T0)
    assert result["status"] == "succeeded"
    assert queue.get(job["id"])["status"] == "succeeded"
    assert queue.recover_expired(now=T2) == 0
    with pytest.raises(JobConflict):
        queue.complete(job["id"], "worker-a", "succeeded", now=T2)
    attempt = service.get(question["id"])["attempts"][0]
    assert attempt["status"] == "succeeded"
    assert attempt["outcome_note"].startswith("pursuit linked")


def _run_to_terminal(tmp_db, *, now):
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    return worker.run_once(now=now), queue


def test_rerun_creates_fresh_owned_attempt_that_executes_successfully(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2, query_budget=2, question="unresolved detail")
    original = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)
    first, queue = _run_to_terminal(tmp_db, now=T0)
    assert first["status"] == "succeeded"

    historical = service.get(question["id"])["attempts"][0]
    assert historical["job_id"] == original["id"]
    assert historical["status"] == "succeeded"
    assert historical["completed_at"] == T0
    assert historical["outcome_note"].startswith("pursuit linked")

    rerun = queue.rerun(original["id"])
    assert rerun["id"] != original["id"]
    assert rerun["status"] == "queued"
    assert rerun["job_type"] == RESEARCH_QUESTION_JOB_TYPE

    current = service.get(question["id"])
    attempts = current["attempts"]
    assert len(attempts) == 2
    old, new = attempts
    assert old["id"] != new["id"]
    assert old["status"] == "succeeded"
    assert old["completed_at"] == T0
    assert old["outcome_note"] == historical["outcome_note"]
    assert old["job_id"] == original["id"]
    assert new["status"] == "planned"
    assert new["attempt_no"] == 2
    assert new["job_id"] == rerun["id"]
    assert rerun["payload"]["attempt_id"] == new["id"]
    assert rerun["payload"]["research_question_id"] == question["id"]
    assert rerun["research_question_id"] == question["id"]

    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-b", queue=queue)
    outcome = worker.run_once(now=T1)
    assert outcome is not None
    assert outcome["status"] == "succeeded"
    final = service.get(question["id"])
    assert final["attempts"][0]["status"] == "succeeded"
    assert final["attempts"][0]["job_id"] == original["id"]
    assert final["attempts"][1]["status"] == "succeeded"
    assert final["attempts"][1]["job_id"] == rerun["id"]
    assert final["attempts"][1]["completed_at"] == T1
    assert final["attempts_used"] == 2


def test_rerun_after_failed_attempt_creates_fresh_runnable_job(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2, query_budget=2, question="unresolved detail")
    original = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)

    class FailingSearch:
        def search(self, *args, **kwargs):
            raise RuntimeError("deterministic search failure")

    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, ResearchQuestionExecutionService(tmp_db, search=FailingSearch()).handlers(), worker_id="worker-a", queue=queue)
    first = worker.run_once(now=T0)
    assert first["status"] == "failed"

    rerun = queue.rerun(original["id"])
    assert rerun["status"] == "queued"
    current = service.get(question["id"])
    assert len(current["attempts"]) == 2
    old, new = current["attempts"]
    assert old["status"] == "failed"
    assert old["completed_at"] is not None
    assert "deterministic search failure" in old["outcome_note"]
    assert new["status"] == "planned"
    assert new["job_id"] == rerun["id"]

    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-b", queue=queue)
    outcome = worker.run_once(now=T1)
    assert outcome["status"] == "succeeded"
    final = service.get(question["id"])["attempts"]
    assert final[0]["status"] == "failed"
    assert final[0]["outcome_note"] == old["outcome_note"]
    assert final[1]["status"] == "succeeded"
    assert final[1]["job_id"] == rerun["id"]


def test_rerun_keeps_historical_attempt_immutable(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=3, query_budget=3, question="unresolved detail")
    original = service.pursue(question["id"], mode="manual", query="unresolved detail", query_units=1)
    first, queue = _run_to_terminal(tmp_db, now=T0)
    assert first["status"] == "succeeded"

    before = service.get(question["id"])["attempts"][0]
    queue.rerun(original["id"])
    queue.rerun(original["id"])

    current = service.get(question["id"])
    assert len(current["attempts"]) == 3
    old = current["attempts"][0]
    assert old == before
    assert old["status"] == "succeeded"
    assert old["completed_at"] == T0
    assert old["outcome_note"] == before["outcome_note"]
    assert old["job_id"] == original["id"]


def _job_count(db_path):
    conn = storage.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    finally:
        conn.close()


def test_rerun_invalid_owner_fails_without_doomed_job(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    queue = build_worker_queue(tmp_db)

    question = _question(tmp_db, search_attempt_budget=2, query_budget=2)
    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    assert worker.run_once(now=T0)["status"] == "succeeded"

    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("UPDATE research_questions SET deleted_at = ? WHERE id = ?", (T1, question["id"]))
    finally:
        conn.close()
    before = _job_count(tmp_db)
    with pytest.raises(DomainNotFound):
        queue.rerun(job["id"])
    assert _job_count(tmp_db) == before

    question_b = _question(
        tmp_db,
        search_attempt_budget=2,
        query_budget=2,
        question="unresolved detail b",
    )
    job_b = service.pursue(question_b["id"], mode="manual", query="unresolved detail b", query_units=1)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    assert worker.run_once(now=T1)["status"] in {"succeeded", "partial"}
    service.resolve(question_b["id"], "answered")
    before = _job_count(tmp_db)
    with pytest.raises(DomainConflict, match="only open research questions can be pursued"):
        queue.rerun(job_b["id"])
    assert _job_count(tmp_db) == before


def test_rerun_attempt_budget_exhaustion_fails_without_doomed_job(tmp_db):
    apply_migrations(tmp_db)
    _ledger_fixture(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=1, query_budget=2)
    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    queue = build_worker_queue(tmp_db)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    assert worker.run_once(now=T0)["status"] == "succeeded"

    before = _job_count(tmp_db)
    with pytest.raises(DomainConflict, match="attempt budget exhausted"):
        queue.rerun(job["id"])
    assert _job_count(tmp_db) == before
    attempts = service.get(question["id"])["attempts"]
    assert len(attempts) == 1


def test_rerun_pair_covered_by_lease_recovery(tmp_db):
    apply_migrations(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2, query_budget=2)
    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    queue = _hooked_queue(tmp_db, lease_seconds=10)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    assert worker.run_once(now=T0)["status"] == "succeeded"

    rerun = queue.rerun(job["id"])
    queue.claim(rerun["id"], "worker-a", now=T1)
    attempt = service.get(question["id"])["attempts"][1]
    service.record_attempt(attempt["id"], "running", started_at=T1)

    assert queue.recover_expired(now=T2) == 1
    state = queue.get(rerun["id"])
    assert state["status"] == "failed"
    assert state["failure_cause"] == "lease_expired"
    final = service.get(question["id"])["attempts"]
    assert final[0]["status"] in {"succeeded", "partial"}
    assert final[1]["status"] == "failed"
    assert "lease expired" in final[1]["outcome_note"]
    assert final[1]["job_id"] == rerun["id"]


def test_rerun_pair_covered_by_budget_exhaustion(tmp_db):
    apply_migrations(tmp_db)
    budgets = BudgetService(tmp_db)
    service = ResearchQuestionService(tmp_db)
    question = _question(tmp_db, search_attempt_budget=2, query_budget=2)
    queue = _hooked_queue(tmp_db, budget_service=budgets, lease_seconds=10)

    job = service.pursue(question["id"], mode="manual", query="anything", query_units=1)
    worker = WorkerProcess(tmp_db, build_worker_handlers(tmp_db), worker_id="worker-a", queue=queue)
    assert worker.run_once(now=T0)["status"] == "succeeded"

    budgets.configure_limit("research_question", question["id"], "daily", "acquisition_units", 0)
    rerun = queue.rerun(job["id"])
    assert queue.claim(rerun["id"], "worker-b", now=T1) is None
    assert queue.get(rerun["id"])["status"] == "failed"
    assert queue.get(rerun["id"])["failure_cause"] == "budget_exhausted"
    final = service.get(question["id"])["attempts"]
    assert final[0]["status"] in {"succeeded", "partial"}
    assert final[1]["status"] == "failed"
    assert "budget" in final[1]["outcome_note"]
    assert final[1]["job_id"] == rerun["id"]


def test_generic_rerun_unchanged_by_research_factory(tmp_db):
    apply_migrations(tmp_db)
    queue = _hooked_queue(tmp_db)
    first = queue.enqueue("fixture", {"value": 7}, idempotency_key="fixture-1")
    queue.claim(first["id"], "worker-a", now=T0)
    queue.complete(first["id"], "worker-a", "succeeded", now=T0)

    rerun = queue.rerun(first["id"])
    assert rerun["id"] != first["id"]
    assert rerun["status"] == "queued"
    assert rerun["job_type"] == "fixture"
    assert rerun["payload"] == {"value": 7}
    assert rerun["idempotency_key"] is not None
    assert rerun["idempotency_key"] != first["idempotency_key"]


def _api_client(tmp_path):
    from fastapi.testclient import TestClient

    from newsroom.app import create_app
    from newsroom.config import RuntimeConfig

    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert (
        client.post(
            "/api/v1/auth/setup",
            json={"username": "admin", "password": "a-long-test-password-12345"},
        ).status_code
        == 201
    )
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "a-long-test-password-12345"}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    return config, client, headers


def test_api_rerun_uses_normal_production_mechanism(tmp_path):
    config, client, headers = _api_client(tmp_path)
    created = client.post(
        "/api/v1/research-questions",
        headers=headers,
        json={
            "question": "unresolved detail",
            "origin_type": "user",
            "search_attempt_budget": 2,
            "query_budget": 100,
        },
    )
    assert created.status_code == 201
    question_id = created.json()["id"]

    pursued = client.post(
        f"/api/v1/research-questions/{question_id}/pursue",
        headers=headers,
        json={"mode": "manual", "query": "unresolved detail", "query_units": 1},
    )
    assert pursued.status_code == 201
    original_job = pursued.json()

    queue = build_worker_queue(config.database_path)
    worker = WorkerProcess(config.database_path, build_worker_handlers(config.database_path), worker_id="worker-a", queue=queue)
    assert worker.run_once(now=T0)["status"] in {"succeeded", "partial"}

    historical = client.get(f"/api/v1/research-questions/{question_id}").json()["attempts"][0]

    rerun = client.post(f"/api/v1/jobs/{original_job['id']}/rerun", headers=headers)
    assert rerun.status_code == 201
    rerun_job = rerun.json()
    assert rerun_job["id"] != original_job["id"]
    assert rerun_job["status"] == "queued"
    assert rerun_job["payload"]["attempt_id"] != original_job["payload"]["attempt_id"]

    current = client.get(f"/api/v1/research-questions/{question_id}").json()
    assert len(current["attempts"]) == 2
    old, new = current["attempts"]
    assert old["job_id"] == original_job["id"]
    assert new["job_id"] == rerun_job["id"]
    assert rerun_job["payload"]["attempt_id"] == new["id"]
    assert new["status"] == "planned"
    assert new["query_units"] == 1

    worker = WorkerProcess(config.database_path, build_worker_handlers(config.database_path), worker_id="worker-b", queue=queue)
    outcome = worker.run_once(now=T1)
    assert outcome["status"] in {"succeeded", "partial"}

    final = client.get(f"/api/v1/research-questions/{question_id}").json()
    final_old, final_new = final["attempts"]
    assert final_old == historical
    assert final_old["status"] in {"succeeded", "partial"}
    assert final_new["status"] in {"succeeded", "partial"}
    assert final_new["job_id"] == rerun_job["id"]
