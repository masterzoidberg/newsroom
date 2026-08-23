import json
from pathlib import Path

from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.config import RuntimeConfig
from newsroom.evidence import EvidenceService
from newsroom.jobs import JobService
from newsroom.integrity import check_database
from newsroom.operations import export_logical
from newsroom.migrations import apply_migrations
from newsroom.app import create_app
from newsroom.reports import AlertService
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.story_automation import enqueue_story_stage
from newsroom.worker import WorkerProcess

from test_phase23b_story_automation import _promotion
from test_phase23c_report_automation import _complete_story_stage
from test_phase21_article_analysis import T1, T2, _setup_relevant


PASSWORD = "a-long-test-password-12345"
ROOT = Path(__file__).resolve().parents[1]


def _authenticated_client(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(
        create_app(config=config, frontend_dist=tmp_path / "missing-dist")
    )
    assert client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": PASSWORD},
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": PASSWORD},
    ).status_code == 200
    return client, config.database_path


def test_pending_automatic_claims_are_bounded_and_expose_exact_provenance(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)

    page = EvidenceService(tmp_db).list_all_claims(
        state="pending",
        assignment="unassigned",
        provenance="automatic",
        page=1,
        page_size=1,
    )

    assert page["page"] == page["page_size"] == page["total"] == 1
    claim = page["items"][0]
    assert claim["id"] == claim_id
    assert claim["story_id"] is None
    assert claim["provenance"]["origin"] == "automatic"
    assert claim["provenance"]["promotion_id"] == promotion_id
    assert claim["provenance"]["article_analysis_id"]
    assert claim["provenance"]["candidate_claim_index"] == 0
    evidence = claim["evidence"][0]
    assert evidence["evidence_span_id"]
    assert evidence["evidence_span_id"] != evidence["id"]
    assert evidence["document_version"]["id"]
    assert evidence["document"]["id"]
    assert evidence["source"]["id"]


def test_global_claim_api_filters_assignment_and_preserves_manual_provenance(tmp_path):
    client, db_path = _authenticated_client(tmp_path)
    promotion_id, automatic_claim_id = _promotion(db_path)
    response = client.get(
        "/api/v1/claims",
        params={
            "state": "pending",
            "assignment": "unassigned",
            "provenance": "automatic",
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == automatic_claim_id
    assert body["items"][0]["provenance"]["promotion_id"] == promotion_id


def test_story_revision_exposes_exact_claim_documents_and_automatic_origin(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story_job, _ = _complete_story_stage(tmp_db, promotion_id)
    story_id = story_job["result"]["story_id"]

    revision = EvidenceService(tmp_db).get_story_revisions(story_id)[0]

    assert revision["claim_ids"] == [story_job["result"]["claim_id"]]
    assert len(revision["document_ids"]) == 1
    assert revision["origin"] == "automatic"
    assert revision["story_evolution_event_id"]


def test_phase23_job_api_returns_typed_status_without_raw_internal_payload(tmp_path):
    client, db_path = _authenticated_client(tmp_path)
    promotion_id, _ = _promotion(db_path)
    enqueue_story_stage(db_path, promotion_id)
    story_job = JobService(db_path).get_by_idempotency(
        f"automatic_story_stage:{promotion_id}"
    )

    response = client.get(
        "/api/v1/jobs",
        params={"job_type": "automatic_story_stage", "page_size": 10},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == story_job["id"]
    assert item["job_type"] == "automatic_story_stage"
    assert item["orchestration"]["promotion_id"] == promotion_id
    assert item["orchestration"]["outcome"] == "queued"
    assert "payload" not in item
    assert "result" not in item


def test_logical_export_preserves_story_audit_relationships(tmp_db, tmp_path):
    promotion_id, _ = _promotion(tmp_db)
    story_job, _ = _complete_story_stage(tmp_db, promotion_id)

    path = export_logical(tmp_db, tmp_path / "phase23e.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    by_table = {}
    for row in rows:
        if "table" in row:
            by_table.setdefault(row["table"], []).append(row["data"])

    revision_id = story_job["result"]["revision_id"]
    claim_id = story_job["result"]["claim_id"]
    assert any(
        row["revision_id"] == revision_id and row["claim_id"] == claim_id
        for row in by_table["story_revision_claims"]
    )
    assert any(
        row["revision_id"] == revision_id
        for row in by_table["story_revision_documents"]
    )
    assert any(
        row["story_id"] == story_job["result"]["story_id"]
        for row in by_table["story_evolution_events"]
    )


def test_real_worker_chain_export_and_full_replay_converge_without_duplicates(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    _setup_relevant(tmp_db)
    AlertService(tmp_db).create_rule(
        {"name": "Phase 23E exact causes", "target_type": "all"}
    )
    worker = WorkerProcess(
        tmp_db,
        build_worker_handlers(tmp_db),
        worker_id="phase23e-worker",
        queue=build_worker_queue(tmp_db),
    )
    completed = []
    while True:
        job = worker.run_once(now=T1)
        if job is None:
            break
        completed.append(job)

    assert completed[0]["job_type"] == "document_version_process"
    assert {job["job_type"] for job in completed[1:]} == {
        "automatic_story_stage",
        "automatic_report_stage",
        "automatic_alert_stage",
    }
    assert all(job["status"] == "succeeded" for job in completed)
    expected_counts = {
        table: _table_count(tmp_db, table)
        for table in (
            "article_analysis_promotions",
            "claims",
            "stories",
            "story_revisions",
            "claim_state_history",
            "report_revisions",
            "alerts",
            "alert_deliveries",
        )
    }
    assert expected_counts["alerts"] == expected_counts["alert_deliveries"]
    assert expected_counts["alerts"] >= 1
    assert check_database(tmp_db).ok

    exported = export_logical(tmp_db, tmp_path / "phase23e-chain.jsonl")
    export_rows = [
        json.loads(line)
        for line in exported.read_text(encoding="utf-8").splitlines()
        if '"table"' in line
    ]
    tables = {}
    for row in export_rows:
        tables.setdefault(row["table"], {})[row["data"].get("id") or tuple(row["data"].values())] = row["data"]
    alert = next(iter(tables["alerts"].values()))
    cause = json.loads(alert["cause_json"])[0]
    revision_claims = [
        row for row in tables["report_revision_claims"].values()
        if row["revision_id"] == alert["report_revision_id"]
    ]
    assert cause["claim_id"] in {row["claim_id"] for row in revision_claims}
    claim = tables["claims"][cause["claim_id"]]
    claim_evidence = next(
        row for row in tables["claim_evidence"].values()
        if row["claim_id"] == claim["id"] and row["evidence_span_id"] == cause["evidence_span_id"]
    )
    span = tables["evidence_spans"][claim_evidence["evidence_span_id"]]
    version = tables["document_versions"][span["document_version_id"]]
    document = tables["documents"][version["document_id"]]
    assert tables["sources"][document["source_id"]]
    assert any(
        row["claim_id"] == claim["id"]
        for row in tables["story_revision_claims"].values()
    )

    processing = completed[0]
    rerun = build_worker_queue(tmp_db).rerun(processing["id"])
    assert rerun["status"] == "queued"
    while worker.run_once(now=T2) is not None:
        pass

    assert {
        table: _table_count(tmp_db, table) for table in expected_counts
    } == expected_counts
    assert check_database(tmp_db).ok


def test_integrity_detects_broken_completed_story_checkpoint(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story_job, _ = _complete_story_stage(tmp_db, promotion_id)
    broken = dict(story_job["result"])
    broken["revision_id"] = "rev_missing"
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE jobs SET result_json = ? WHERE id = ?",
                (json.dumps(broken), story_job["id"]),
            )
    finally:
        conn.close()

    assert any(
        issue.code == "invalid_automatic_story_checkpoint"
        for issue in check_database(tmp_db).issues
    )


def _table_count(db_path, table):
    conn = storage.connect(db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def test_frontend_models_and_retrieves_unassigned_automatic_claims():
    types = (ROOT / "frontend" / "src" / "lib" / "types.ts").read_text(
        encoding="utf-8"
    )
    workbench = (
        ROOT / "frontend" / "src" / "views" / "WorkbenchView.tsx"
    ).read_text(encoding="utf-8")

    assert "story_id: string | null" in types
    assert "promotion_id: string | null" in types
    assert "/claims?state=pending&assignment=unassigned&provenance=automatic" in workbench
    assert "Pending automatic Claims" in workbench
