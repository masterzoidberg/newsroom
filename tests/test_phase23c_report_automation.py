from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from newsroom import storage
from newsroom.evidence import EvidenceService, claim_set_hash
from newsroom.evidence_promotion import verify_automatic_promotion
from newsroom.integrity import check_database
from newsroom.jobs import JobService
from newsroom.operations import export_logical
from newsroom.report_automation import (
    AUTOMATIC_ACCEPTANCE_REASON_PREFIX,
    AUTOMATIC_REPORT_STAGE_JOB_TYPE,
    REPORT_COMPLETED,
    REPORT_DEFERRED,
    REPORT_NO_CHANGE,
    REPORT_TERMINAL,
    AutomaticReportStageExecutionService,
    enqueue_report_stage,
)
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.story_automation import AutomaticStoryStageExecutionService, enqueue_story_stage

from test_phase23b_story_automation import (
    T0,
    T1,
    _count,
    _promotion,
    _story_with_claim,
    _variant_promotion,
)


def _complete_story_stage(db, promotion_id: str):
    queue = build_worker_queue(db)
    story_job = enqueue_story_stage(db, promotion_id)
    claimed = queue.claim(story_job["id"], "story-worker", now=T0)
    outcome = AutomaticStoryStageExecutionService(db).handle(claimed)
    completed = queue.complete(
        story_job["id"], "story-worker", "succeeded", now=T1, outcome=outcome
    )
    conn = storage.connect(db)
    try:
        report_ids = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM jobs WHERE idempotency_key = ?",
                (f"automatic_report_stage:{story_job['id']}",),
            ).fetchall()
        ]
    finally:
        conn.close()
    report_jobs = [JobService(db).get(identifier) for identifier in report_ids]
    assert len(report_jobs) == 1
    return completed, report_jobs[0]


def _run_report_stage(db, report_job, *, worker="report-worker"):
    queue = JobService(db)
    claimed = queue.claim(report_job["id"], worker, now=T1)
    outcome = AutomaticReportStageExecutionService(db).handle(claimed)
    completed = queue.complete(
        report_job["id"], worker, "succeeded", outcome=outcome
    )
    return outcome, completed


def _row(db, sql: str, params=()):
    conn = storage.connect(db)
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def _rows(db, sql: str, params=()):
    conn = storage.connect(db)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_completed_story_stage_auto_accepts_with_audited_history_and_exact_report_causes(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    story_job, report_job = _complete_story_stage(tmp_db, promotion_id)

    outcome, completed = _run_report_stage(tmp_db, report_job)

    claim = EvidenceService(tmp_db).get_claim(claim_id)
    automatic = [
        item
        for item in claim["state_history"]
        if item["reason"].startswith(AUTOMATIC_ACCEPTANCE_REASON_PREFIX)
    ]
    assert claim["state"] == "supported"
    assert claim["accepted"] is True
    assert len(automatic) == 1
    assert automatic[0]["from_state"] == "pending"
    assert automatic[0]["to_state"] == "supported"
    assert automatic[0]["reason"] == f"{AUTOMATIC_ACCEPTANCE_REASON_PREFIX}{story_job['id']}"
    assert outcome["stage_status"] == REPORT_COMPLETED
    assert completed["result"] == outcome
    revision = _row(
        tmp_db,
        "SELECT rr.* FROM report_revisions rr JOIN living_reports lr ON lr.current_revision_id = rr.id",
    )
    assert revision is not None
    audit = json.loads(revision["audit_json"])
    changes = json.loads(revision["what_changed"])
    propositions = json.loads(revision["propositions_json"])
    assert audit["input_identity"] == outcome["input_identity"]
    assert audit["passed"] is True
    assert propositions == [
        {"claim_ids": [claim_id], "text": "The agency released a UAP report"}
    ]
    assert _count(tmp_db, "report_revision_claims", "revision_id = ?", (revision["id"],)) == 1
    cause = _row(tmp_db, "SELECT * FROM report_revision_causes WHERE revision_id = ?", (revision["id"],))
    chain = _row(
        tmp_db,
        """
        SELECT ce.claim_id, es.id AS evidence_span_id, dv.id AS document_version_id,
               d.id AS document_id, s.id AS source_id
        FROM claim_evidence ce
        JOIN evidence_spans es ON es.id = ce.evidence_span_id
        JOIN document_versions dv ON dv.id = es.document_version_id
        JOIN documents d ON d.id = dv.document_id
        JOIN sources s ON s.id = d.source_id
        WHERE ce.claim_id = ? AND ce.evidence_span_id = ?
        """,
        (cause["claim_id"], cause["evidence_span_id"]),
    )
    assert cause["claim_id"] == claim_id
    assert cause["document_id"] == chain["document_id"]
    persisted_cause_ids = {
        item[0]
        for item in _rows(
            tmp_db,
            "SELECT id FROM report_revision_causes WHERE revision_id = ?",
            (revision["id"],),
        )
    }
    assert changes
    assert all(set(item["cause_ids"]) <= persisted_cause_ids for item in changes)
    assert chain["source_id"]
    assert check_database(tmp_db).ok


def test_acceptance_and_revision_replay_are_idempotent(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    first, _ = _run_report_stage(tmp_db, report_job)
    before_history = _count(tmp_db, "claim_state_history", "claim_id = ?", (claim_id,))

    replay = AutomaticReportStageExecutionService(tmp_db).handle(
        JobService(tmp_db).get(report_job["id"])
    )

    assert replay == first
    assert _count(tmp_db, "claim_state_history", "claim_id = ?", (claim_id,)) == before_history
    assert _count(tmp_db, "report_revisions") == 1


def test_manual_claim_decision_is_never_overwritten(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    EvidenceService(tmp_db).set_claim_state(claim_id, "unsubstantiated", "human rejected")

    outcome, _ = _run_report_stage(tmp_db, report_job)

    claim = EvidenceService(tmp_db).get_claim(claim_id)
    assert outcome["stage_status"] == REPORT_DEFERRED
    assert outcome["reason_code"] == "claim_human_override"
    assert claim["state"] == "unsubstantiated"
    assert claim["accepted_at"] is None
    assert _count(tmp_db, "report_revisions") == 0


def test_story_completion_enqueues_one_report_obligation_and_runtime_registers_handler(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story_completed, report_job = _complete_story_stage(tmp_db, promotion_id)

    duplicate = enqueue_report_stage(tmp_db, story_completed["id"])

    assert duplicate["id"] == report_job["id"]
    assert report_job["idempotency_key"] == f"automatic_report_stage:{story_completed['id']}"
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_REPORT_STAGE_JOB_TYPE,)) == 1
    assert AUTOMATIC_REPORT_STAGE_JOB_TYPE in build_worker_handlers(tmp_db)


def test_concurrent_report_enqueue_coalesces_and_deferred_story_does_not_enqueue(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story_completed, report_job = _complete_story_stage(tmp_db, promotion_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        duplicates = list(
            pool.map(lambda _: enqueue_report_stage(tmp_db, story_completed["id"]), range(2))
        )

    assert {item["id"] for item in duplicates} == {report_job["id"]}

    other_promotion, _ = _variant_promotion(
        tmp_db, "deferred", proposition="A deliberately ambiguous report"
    )
    _story_with_claim(tmp_db, "A deliberately ambiguous report")
    _story_with_claim(tmp_db, "A deliberately ambiguous report")
    queue = build_worker_queue(tmp_db)
    story_job = enqueue_story_stage(tmp_db, other_promotion)
    claimed = queue.claim(story_job["id"], "deferred-worker", now=T0)
    outcome = AutomaticStoryStageExecutionService(tmp_db).handle(claimed)
    queue.complete(story_job["id"], "deferred-worker", "succeeded", outcome=outcome)

    assert outcome["stage_status"] == "deferred"
    assert _count(
        tmp_db,
        "jobs",
        "idempotency_key = ?",
        (f"automatic_report_stage:{story_job['id']}",),
    ) == 0


def test_unchanged_report_input_is_no_change_without_new_revision_or_provider_usage(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story_job, report_job = _complete_story_stage(tmp_db, promotion_id)
    first, _ = _run_report_stage(tmp_db, report_job)
    provider_usage_before_no_change = _count(tmp_db, "provider_usage")
    second_job = JobService(tmp_db).enqueue(
        AUTOMATIC_REPORT_STAGE_JOB_TYPE,
        report_job["payload"],
        idempotency_key="phase23c-explicit-no-change",
    )

    second, _ = _run_report_stage(tmp_db, second_job, worker="report-worker-2")

    assert first["stage_status"] == REPORT_COMPLETED
    assert second["stage_status"] == REPORT_NO_CHANGE
    assert second["revision_id"] == first["revision_id"]
    assert _count(tmp_db, "report_revisions") == 1
    assert _count(tmp_db, "provider_usage") == provider_usage_before_no_change
    assert story_job["result"]["stage_status"] == "completed"


def test_two_database_backed_workers_persist_one_revision_for_the_same_input(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    claimed = JobService(tmp_db).claim(report_job["id"], "report-worker", now=T1)
    service = AutomaticReportStageExecutionService(tmp_db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: service.handle(claimed), range(2)))

    assert {item["revision_id"] for item in outcomes}.__len__() == 1
    assert {item["stage_status"] for item in outcomes} <= {REPORT_COMPLETED, REPORT_NO_CHANGE}
    assert _count(tmp_db, "report_revisions") == 1


def test_second_accepted_claim_creates_one_revision_with_exact_sorted_claim_set(tmp_db):
    first_promotion, first_claim = _variant_promotion(
        tmp_db, "material-first", proposition="The agency released a UAP report"
    )
    _, first_report_job = _complete_story_stage(tmp_db, first_promotion)
    first, _ = _run_report_stage(tmp_db, first_report_job)
    second_promotion, second_claim = _variant_promotion(
        tmp_db, "material-second", proposition="The agency released a UAP report"
    )
    _, second_report_job = _complete_story_stage(tmp_db, second_promotion)

    second, _ = _run_report_stage(tmp_db, second_report_job, worker="second-report-worker")

    assert second["stage_status"] == REPORT_COMPLETED
    assert second["revision_id"] != first["revision_id"]
    rows = _row(
        tmp_db,
        "SELECT claim_set_hash, revision_number FROM report_revisions WHERE id = ?",
        (second["revision_id"],),
    )
    assert rows["claim_set_hash"] == claim_set_hash([second_claim, first_claim])
    assert rows["revision_number"] == 2
    assert _count(
        tmp_db,
        "report_revision_claims",
        "revision_id = ?",
        (second["revision_id"],),
    ) == 2
    assert claim_set_hash([first_claim, second_claim]) == claim_set_hash(
        [second_claim, first_claim]
    )


def test_retry_after_revision_commit_reuses_existing_revision(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    story_completed, report_job = _complete_story_stage(tmp_db, promotion_id)
    acceptance_reason = f"{AUTOMATIC_ACCEPTANCE_REASON_PREFIX}{story_completed['id']}"
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            evidence = EvidenceService(tmp_db)
            evidence._set_claim_state_tx(conn, claim_id, "supported", acceptance_reason)
            evidence._accept_claim_tx(conn, claim_id)
            graph = verify_automatic_promotion(tmp_db, promotion_id)
            report_id = AutomaticReportStageExecutionService._ensure_report_tx(
                conn, story_completed["result"]["story_id"], graph
            )
            committed = AutomaticReportStageExecutionService(tmp_db).reports.generate_tx(
                conn, report_id
            )
    finally:
        conn.close()

    resumed, _ = _run_report_stage(tmp_db, report_job)

    assert resumed["stage_status"] == REPORT_NO_CHANGE
    assert resumed["revision_id"] == committed["revision_id"]
    assert _count(tmp_db, "report_revisions") == 1


def test_corrupted_promotion_and_unexpected_story_fail_closed(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analysis_promotions_immutable_update")
            conn.execute(
                "UPDATE article_analysis_promotions SET promotion_identity = 'corrupt' WHERE id = ?",
                (promotion_id,),
            )
    finally:
        conn.close()

    corrupt, _ = _run_report_stage(tmp_db, report_job)

    assert corrupt["stage_status"] == REPORT_TERMINAL
    assert EvidenceService(tmp_db).get_claim(claim_id)["accepted_at"] is None


def test_report_payload_for_an_unexpected_story_fails_closed(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    other_story = _story_with_claim(tmp_db, "Unrelated Story")[0]
    payload = dict(report_job["payload"])
    payload["story_id"] = other_story["id"]
    corrupted_delivery = JobService(tmp_db).enqueue(
        AUTOMATIC_REPORT_STAGE_JOB_TYPE,
        payload,
        idempotency_key="phase23c-wrong-story",
    )

    outcome, _ = _run_report_stage(
        tmp_db, corrupted_delivery, worker="wrong-story-worker"
    )

    assert outcome["stage_status"] == REPORT_TERMINAL
    assert outcome["reason_code"] == "story_stage_result_mismatch"
    assert EvidenceService(tmp_db).get_claim(claim_id)["accepted_at"] is None
    assert _count(tmp_db, "report_revisions") == 0


def test_archived_story_defers_before_acceptance(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    story_completed, report_job = _complete_story_stage(tmp_db, promotion_id)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE stories SET lifecycle = 'archived' WHERE id = ?",
                (story_completed["result"]["story_id"],),
            )
    finally:
        conn.close()

    outcome, _ = _run_report_stage(tmp_db, report_job)

    assert outcome["stage_status"] == REPORT_DEFERRED
    assert outcome["reason_code"] == "story_not_reportable"
    assert EvidenceService(tmp_db).get_claim(claim_id)["accepted_at"] is None


def test_story_change_between_provenance_read_and_mutation_is_revalidated(tmp_db, monkeypatch):
    promotion_id, claim_id = _promotion(tmp_db)
    story_completed, report_job = _complete_story_stage(tmp_db, promotion_id)
    from newsroom.evidence_promotion import verify_automatic_promotion as real_verify

    changed = False

    def verify_then_archive(db, identifier):
        nonlocal changed
        graph = real_verify(db, identifier)
        if not changed:
            changed = True
            conn = storage.connect(db)
            try:
                with storage.write_tx(conn):
                    conn.execute(
                        "UPDATE stories SET lifecycle = 'archived' WHERE id = ?",
                        (story_completed["result"]["story_id"],),
                    )
            finally:
                conn.close()
        return graph

    monkeypatch.setattr("newsroom.report_automation.verify_automatic_promotion", verify_then_archive)
    outcome, _ = _run_report_stage(tmp_db, report_job)

    assert outcome["stage_status"] == REPORT_DEFERRED
    assert outcome["reason_code"] == "story_not_reportable"
    assert EvidenceService(tmp_db).get_claim(claim_id)["accepted_at"] is None
    assert _count(tmp_db, "report_revisions") == 0


def test_report_logical_export_preserves_revision_claim_and_exact_cause_links(tmp_db, tmp_path):
    promotion_id, _ = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    _run_report_stage(tmp_db, report_job)

    exported = export_logical(tmp_db, tmp_path / "phase23c.jsonl")
    rows = [json.loads(line) for line in exported.read_text(encoding="utf-8").splitlines()]
    tables = {row.get("table") for row in rows}

    assert "report_revision_claims" in tables
    assert "report_revision_causes" in tables
    cause = next(row["data"] for row in rows if row.get("table") == "report_revision_causes")
    assert cause["claim_id"] and cause["evidence_span_id"] and cause["document_id"]


def test_wrong_evidence_or_document_cause_is_detected(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    outcome, _ = _run_report_stage(tmp_db, report_job)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER report_revision_causes_immutable_update")
            conn.execute(
                "UPDATE report_revision_causes SET document_id = NULL WHERE revision_id = ?",
                (outcome["revision_id"],),
            )
    finally:
        conn.close()

    report = check_database(tmp_db)

    assert any(issue.code == "invalid_report_cause_chain" for issue in report.issues)


def test_unrelated_claim_and_evidence_cannot_satisfy_report_cause_chain(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    _, report_job = _complete_story_stage(tmp_db, promotion_id)
    outcome, _ = _run_report_stage(tmp_db, report_job)
    unrelated_promotion, unrelated_claim = _variant_promotion(
        tmp_db, "unrelated-cause", proposition="An unrelated exact Claim"
    )
    unrelated = verify_automatic_promotion(tmp_db, unrelated_promotion)
    unrelated_span = unrelated["evidence_spans"][0]
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER report_revision_causes_immutable_update")
            conn.execute(
                """
                UPDATE report_revision_causes
                SET claim_id = ?, evidence_span_id = ?, document_id = ?
                WHERE revision_id = ?
                """,
                (
                    unrelated_claim,
                    unrelated_span["id"],
                    unrelated["document"]["id"],
                    outcome["revision_id"],
                ),
            )
    finally:
        conn.close()

    report = check_database(tmp_db)

    assert any(issue.code == "invalid_report_cause_chain" for issue in report.issues)
