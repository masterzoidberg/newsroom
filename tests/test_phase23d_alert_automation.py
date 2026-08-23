from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from newsroom import storage
from newsroom.alert_automation import (
    ALERT_COMPLETED,
    ALERT_NO_ALERT,
    AUTOMATIC_ALERT_STAGE_JOB_TYPE,
    AutomaticAlertStageExecutionService,
    enqueue_alert_stage,
)
from newsroom.integrity import check_database
from newsroom.jobs import JobService
from newsroom.operations import export_logical
from newsroom.reports import AlertService
from newsroom.report_automation import (
    AUTOMATIC_REPORT_STAGE_JOB_TYPE,
    AutomaticReportStageExecutionService,
)
from newsroom.runtime import build_worker_handlers, build_worker_queue

from test_phase23c_report_automation import (
    _complete_story_stage,
    _row,
    _rows,
    _run_report_stage,
)
from test_phase23b_story_automation import T0, T1, _count, _promotion, _variant_promotion
from test_phase11_reports_briefings_alerts import _accepted_story


def _complete_material_report_stage(db):
    promotion_id, _ = _promotion(db)
    _, report_job = _complete_story_stage(db, promotion_id)
    queue = build_worker_queue(db)
    claimed = queue.claim(report_job["id"], "report-worker", now=T1)
    outcome = AutomaticReportStageExecutionService(db).handle(claimed)
    completed = queue.complete(
        report_job["id"],
        "report-worker",
        "succeeded",
        outcome=outcome,
    )
    return completed, outcome


def _alert_stage_job(db, report_job_id: str):
    conn = storage.connect(db)
    try:
        row = conn.execute(
            "SELECT id FROM jobs WHERE idempotency_key = ?",
            (f"automatic_alert_stage:{report_job_id}",),
        ).fetchone()
    finally:
        conn.close()
    return JobService(db).get(row["id"]) if row else None


def _run_alert_stage(db, alert_job, *, worker="alert-worker"):
    queue = build_worker_queue(db)
    claimed = queue.claim(alert_job["id"], worker, now=T1)
    outcome = AutomaticAlertStageExecutionService(db).handle(claimed)
    completed = queue.complete(
        alert_job["id"], worker, "succeeded", outcome=outcome
    )
    return outcome, completed


def test_material_report_completion_enqueues_one_alert_stage_obligation(tmp_db):
    report_job, outcome = _complete_material_report_stage(tmp_db)

    alert_job = _alert_stage_job(tmp_db, report_job["id"])

    assert alert_job is not None
    assert alert_job["job_type"] == AUTOMATIC_ALERT_STAGE_JOB_TYPE
    assert alert_job["idempotency_key"] == f"automatic_alert_stage:{report_job['id']}"
    assert alert_job["payload"] == {
        "report_stage_job_id": report_job["id"],
        "report_id": outcome["report_id"],
        "report_revision_id": outcome["revision_id"],
    }
    assert AUTOMATIC_ALERT_STAGE_JOB_TYPE in build_worker_handlers(tmp_db)


def test_no_change_terminal_and_failed_report_results_do_not_enqueue_alert_work(tmp_db):
    first_job, _ = _complete_material_report_stage(tmp_db)
    first_alert_count = _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_ALERT_STAGE_JOB_TYPE,))
    second_job = JobService(tmp_db).enqueue(
        AUTOMATIC_REPORT_STAGE_JOB_TYPE,
        first_job["payload"],
        idempotency_key="phase23d-no-change-report",
    )
    queue = build_worker_queue(tmp_db)
    claimed = queue.claim(second_job["id"], "report-worker-2", now=T1)
    no_change = AutomaticReportStageExecutionService(tmp_db).handle(claimed)
    queue.complete(second_job["id"], "report-worker-2", "succeeded", outcome=no_change)
    failed_job = JobService(tmp_db).enqueue(
        AUTOMATIC_REPORT_STAGE_JOB_TYPE,
        first_job["payload"],
        idempotency_key="phase23d-failed-report",
    )
    queue.claim(failed_job["id"], "report-worker-3", now=T1)
    queue.complete(
        failed_job["id"],
        "report-worker-3",
        "failed",
        retryable=False,
        outcome={"stage_status": "terminal"},
    )
    for index, stage_status in enumerate(("deferred", "terminal")):
        skipped_job = JobService(tmp_db).enqueue(
            AUTOMATIC_REPORT_STAGE_JOB_TYPE,
            first_job["payload"],
            idempotency_key=f"phase23d-skipped-report-{index}",
        )
        worker = f"report-worker-skipped-{index}"
        queue.claim(skipped_job["id"], worker, now=T1)
        queue.complete(
            skipped_job["id"],
            worker,
            "succeeded",
            outcome={"stage_status": stage_status},
        )

    assert no_change["stage_status"] == "no_change"
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_ALERT_STAGE_JOB_TYPE,)) == first_alert_count


def test_duplicate_and_concurrent_alert_enqueue_coalesce(tmp_db):
    report_job, _ = _complete_material_report_stage(tmp_db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: enqueue_alert_stage(tmp_db, report_job["id"]), range(2)))

    assert {job["id"] for job in jobs}.__len__() == 1
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_ALERT_STAGE_JOB_TYPE,)) == 1


def test_alert_worker_creates_stable_alert_delivery_and_checkpoint(tmp_db):
    report_job, report_outcome = _complete_material_report_stage(tmp_db)
    rule = AlertService(tmp_db).create_rule(
        {
            "name": "Automatic exact causes",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
            "event_types": [],
            "dedupe_window_seconds": 86400,
        }
    )
    alert_job = _alert_stage_job(tmp_db, report_job["id"])

    outcome, completed = _run_alert_stage(tmp_db, alert_job)
    replay = AutomaticAlertStageExecutionService(tmp_db).handle(
        JobService(tmp_db).get(alert_job["id"])
    )

    assert outcome["stage_status"] == ALERT_COMPLETED
    assert outcome == completed["result"] == replay
    assert outcome["report_revision_id"] == report_outcome["revision_id"]
    assert outcome["evaluated_rule_ids"] == [rule["id"]]
    assert len(outcome["alert_ids"]) == len(outcome["delivery_ids"]) == 1
    assert _count(tmp_db, "alerts") == 1
    assert _count(tmp_db, "alert_deliveries", "channel = 'in_app'") == 1
    assert _count(tmp_db, "alert_deliveries", "channel = 'browser'") == 0


def test_nonmatching_disabled_and_deleted_rules_complete_without_alert(tmp_db):
    report_job, report_outcome = _complete_material_report_stage(tmp_db)
    alerts = AlertService(tmp_db)
    disabled = alerts.create_rule(
        {
            "name": "Disabled",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
            "enabled": False,
        }
    )
    deleted = alerts.create_rule(
        {
            "name": "Deleted before execution",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
        }
    )
    nonmatching = alerts.create_rule(
        {
            "name": "Nonmatching event",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
            "event_types": ["correction"],
        }
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DELETE FROM alert_rules WHERE id = ?", (deleted["id"],))
    finally:
        conn.close()

    outcome, _ = _run_alert_stage(
        tmp_db, _alert_stage_job(tmp_db, report_job["id"])
    )

    assert outcome["stage_status"] == ALERT_NO_ALERT
    assert outcome["evaluated_rule_ids"] == [nonmatching["id"]]
    assert disabled["id"] not in outcome["evaluated_rule_ids"]
    assert _count(tmp_db, "alerts") == 0


def test_two_database_backed_alert_workers_converge_and_preserve_acknowledgement(tmp_db):
    report_job, report_outcome = _complete_material_report_stage(tmp_db)
    AlertService(tmp_db).create_rule(
        {
            "name": "Concurrent exact alert",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
            "dedupe_window_seconds": 0,
        }
    )
    alert_job = _alert_stage_job(tmp_db, report_job["id"])
    claimed = JobService(tmp_db).claim(alert_job["id"], "alert-worker", now=T1)
    service = AutomaticAlertStageExecutionService(tmp_db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: service.handle(claimed), range(2)))

    assert {tuple(item["alert_ids"]) for item in outcomes}.__len__() == 1
    assert _count(tmp_db, "alerts") == 1
    assert _count(tmp_db, "alert_deliveries", "channel = 'in_app'") == 1
    alert_id = outcomes[0]["alert_ids"][0]
    AlertService(tmp_db).acknowledge(alert_id, "human-reviewer")
    replay = service.handle(claimed)
    alert = AlertService(tmp_db).get_alert(alert_id)
    assert replay == outcomes[0]
    assert alert["status"] == "acknowledged"
    assert alert["acknowledged_by"] == "human-reviewer"


def test_corrupt_report_cause_chain_fails_closed_before_alert_mutation(tmp_db):
    report_job, report_outcome = _complete_material_report_stage(tmp_db)
    AlertService(tmp_db).create_rule(
        {
            "name": "Must fail closed",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
        }
    )
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER report_revision_causes_immutable_update")
            conn.execute(
                "UPDATE report_revision_causes SET document_id = NULL WHERE revision_id = ?",
                (report_outcome["revision_id"],),
            )
    finally:
        conn.close()

    outcome, _ = _run_alert_stage(
        tmp_db, _alert_stage_job(tmp_db, report_job["id"])
    )

    assert outcome["stage_status"] == "terminal"
    assert outcome["reason_code"] == "report_cause_chain_invalid"
    assert _count(tmp_db, "alerts") == 0
    assert _count(tmp_db, "alert_deliveries") == 0


def test_mismatched_report_revision_in_alert_job_fails_closed(tmp_db):
    report_job, report_outcome = _complete_material_report_stage(tmp_db)
    AlertService(tmp_db).create_rule(
        {
            "name": "Pinned revision only",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
        }
    )
    alert_job = _alert_stage_job(tmp_db, report_job["id"])
    payload = dict(alert_job["payload"])
    payload["report_revision_id"] = "rptrev_wrong"
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE jobs SET payload_json = ? WHERE id = ?",
                (json.dumps(payload, sort_keys=True), alert_job["id"]),
            )
    finally:
        conn.close()

    outcome, _ = _run_alert_stage(
        tmp_db, JobService(tmp_db).get(alert_job["id"])
    )

    assert outcome["stage_status"] == "terminal"
    assert outcome["reason_code"] == "report_stage_result_mismatch"
    assert _count(tmp_db, "alerts") == 0


def test_retry_after_alert_commit_before_job_completion_reuses_domain_rows(tmp_db):
    report_job, report_outcome = _complete_material_report_stage(tmp_db)
    AlertService(tmp_db).create_rule(
        {
            "name": "Crash-safe",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
            "dedupe_window_seconds": 0,
        }
    )
    alert_job = _alert_stage_job(tmp_db, report_job["id"])
    queue = build_worker_queue(tmp_db)
    claimed = queue.claim(alert_job["id"], "crashed-worker", now=T0)
    committed = AutomaticAlertStageExecutionService(tmp_db).handle(claimed)

    assert JobService(tmp_db).get(alert_job["id"])["status"] == "running"
    assert queue.recover_expired(now="2026-08-23T13:00:00Z") == 1
    recovered = JobService(tmp_db).get(alert_job["id"])
    retried = queue.claim(
        alert_job["id"], "replacement-worker", now=recovered["next_attempt_at"]
    )
    replay = AutomaticAlertStageExecutionService(tmp_db).handle(retried)
    completed = queue.complete(
        alert_job["id"], "replacement-worker", "succeeded", outcome=replay
    )

    assert replay == committed == completed["result"]
    assert _count(tmp_db, "alerts") == 1
    assert _count(tmp_db, "alert_deliveries", "channel = 'in_app'") == 1


def test_multiple_rules_and_later_revision_remain_distinct_while_revision_n_isolated(tmp_db):
    first_report_job, first = _complete_material_report_stage(tmp_db)
    alerts = AlertService(tmp_db)
    first_rule = alerts.create_rule(
        {
            "name": "First independent rule",
            "target_type": "report",
            "target_id": first["report_id"],
            "dedupe_window_seconds": 86400,
        }
    )
    second_rule = alerts.create_rule(
        {
            "name": "Second independent rule",
            "target_type": "report",
            "target_id": first["report_id"],
            "dedupe_window_seconds": 86400,
        }
    )
    second_promotion, _ = _variant_promotion(
        tmp_db,
        "phase23d-later",
        proposition="The agency released a second material UAP report",
    )
    _, second_report_job = _complete_story_stage(tmp_db, second_promotion)
    queue = build_worker_queue(tmp_db)
    claimed = queue.claim(second_report_job["id"], "later-report-worker", now=T1)
    second = AutomaticReportStageExecutionService(tmp_db).handle(claimed)
    second_completed = queue.complete(
        second_report_job["id"],
        "later-report-worker",
        "succeeded",
        outcome=second,
    )

    first_alert_outcome, _ = _run_alert_stage(
        tmp_db, _alert_stage_job(tmp_db, first_report_job["id"]), worker="alert-n"
    )
    second_alert_outcome, _ = _run_alert_stage(
        tmp_db,
        _alert_stage_job(tmp_db, second_completed["id"]),
        worker="alert-n-plus-1",
    )
    first_cause_ids = {
        row[0]
        for row in _rows(
            tmp_db,
            "SELECT id FROM report_revision_causes WHERE revision_id = ?",
            (first["revision_id"],),
        )
    }

    assert second["revision_id"] != first["revision_id"]
    assert len(first_alert_outcome["alert_ids"]) == 2
    assert len(second_alert_outcome["alert_ids"]) == 2
    assert set(first_alert_outcome["alert_ids"]).isdisjoint(second_alert_outcome["alert_ids"])
    assert {first_rule["id"], second_rule["id"]} == {
        AlertService(tmp_db).get_alert(identifier)["rule_id"]
        for identifier in first_alert_outcome["alert_ids"]
    }
    for identifier in first_alert_outcome["alert_ids"]:
        alert = AlertService(tmp_db).get_alert(identifier)
        assert alert["report_revision_id"] == first["revision_id"]
        assert {cause["id"] for cause in alert["cause"]} <= first_cause_ids


def test_alert_logical_export_and_integrity_preserve_exact_delivery_audit(tmp_db, tmp_path):
    report_job, report_outcome = _complete_material_report_stage(tmp_db)
    AlertService(tmp_db).create_rule(
        {
            "name": "Export exact Alert",
            "target_type": "report",
            "target_id": report_outcome["report_id"],
        }
    )
    outcome, _ = _run_alert_stage(
        tmp_db, _alert_stage_job(tmp_db, report_job["id"])
    )

    exported = export_logical(tmp_db, tmp_path / "phase23d.jsonl")
    rows = [json.loads(line) for line in exported.read_text(encoding="utf-8").splitlines()]
    alert_row = next(row["data"] for row in rows if row.get("table") == "alerts")
    delivery_row = next(
        row["data"] for row in rows if row.get("table") == "alert_deliveries"
    )

    assert alert_row["report_revision_id"] == report_outcome["revision_id"]
    assert {cause["id"] for cause in json.loads(alert_row["cause_json"])}
    assert delivery_row["alert_id"] == outcome["alert_ids"][0]
    assert delivery_row["channel"] == "in_app"
    assert check_database(tmp_db).ok

    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE alerts SET cause_json = ? WHERE id = ?",
                (json.dumps([{"id": "cause_missing"}]), outcome["alert_ids"][0]),
            )
    finally:
        conn.close()
    assert any(
        issue.code == "invalid_alert_cause_reference"
        for issue in check_database(tmp_db).issues
    )


def test_regression_alert_persists_only_matching_report_causes(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    outcome, _ = _run_report_stage(tmp_db, report_job)
    matching = _row(
        tmp_db,
        "SELECT * FROM report_revision_causes WHERE revision_id = ?",
        (outcome["revision_id"],),
    )
    _, _, unrelated_story, unrelated_claim, unrelated_span, unrelated_document = (
        _accepted_story(tmp_db)
    )
    unrelated_type = (
        "material_update"
        if matching["cause_type"] != "material_update"
        else "correction"
    )
    unrelated_id = "cause_phase23d_unrelated"
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO report_revision_causes
                    (id, revision_id, cause_type, cause_id, story_id, claim_id,
                     evidence_span_id, document_id, rationale, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unrelated_id,
                    outcome["revision_id"],
                    unrelated_type,
                    unrelated_claim["id"],
                    unrelated_story["id"],
                    unrelated_claim["id"],
                    unrelated_span["id"],
                    unrelated_document["id"],
                    "Unrelated same-report change that does not match this rule.",
                    matching["created_at"],
                ),
            )
    finally:
        conn.close()

    alerts = AlertService(tmp_db)
    rule = alerts.create_rule(
        {
            "name": "Exact event only",
            "target_type": "report",
            "target_id": outcome["report_id"],
            "event_types": [matching["cause_type"]],
            "dedupe_window_seconds": 0,
        }
    )

    emitted = alerts.emit_for_report_revision(
        outcome["report_id"], outcome["revision_id"]
    )
    alert = emitted["items"][0]
    expected_ids = {
        row[0]
        for row in _rows(
            tmp_db,
            """
            SELECT id FROM report_revision_causes
            WHERE revision_id = ? AND cause_type = ?
            """,
            (outcome["revision_id"], matching["cause_type"]),
        )
    }

    assert alert["rule_id"] == rule["id"]
    assert alert["report_revision_id"] == outcome["revision_id"]
    assert {cause["id"] for cause in alert["cause"]} == expected_ids
    assert unrelated_id not in json.dumps(alert, sort_keys=True)
    assert unrelated_claim["id"] not in json.dumps(alert, sort_keys=True)
    assert unrelated_story["id"] not in json.dumps(alert["cause"], sort_keys=True)
    assert unrelated_span["id"] not in json.dumps(alert, sort_keys=True)
    assert unrelated_document["id"] not in json.dumps(alert, sort_keys=True)
    assert "Unrelated same-report change" not in alert["body"]
    expected_key = hashlib.sha256(
        json.dumps(
            {
                "rule_id": rule["id"],
                "report_revision_id": outcome["revision_id"],
                "causes": sorted(
                    (
                        cause["id"],
                        cause["evidence_span_id"],
                        cause["claim_id"],
                    )
                    for cause in alert["cause"]
                ),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert alert["dedupe_key"] == expected_key
    repeated = alerts.emit_for_report_revision(
        outcome["report_id"], outcome["revision_id"]
    )
    assert repeated["created_count"] == 0
    assert alerts.list_alerts()["total"] == 1
