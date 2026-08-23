"""Live Test C — unattended fixture Source to durable in-app Alert.

This manual release-gate harness uses the production Scheduler, JobService,
WorkerProcess, runtime handlers, completion hooks, local deterministic analysis,
and SQLite. Only the HTTP boundary is a controlled fixture; no provider or
public-network call occurs.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from newsroom import storage
from newsroom.acquisition import AcquisitionService, HttpResponse
from newsroom.domain import CoreService
from newsroom.integrity import check_database
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorExecutionService, MonitorService, MonitoringPolicyService
from newsroom.reports import AlertService
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.scheduler import SchedulerProcess
from newsroom.worker import WorkerProcess


NOW = "2026-08-23T20:00:00Z"
DUE_AT = "2020-01-01T00:00:00Z"
FIXTURE_URL = "https://live-test-c.example.test/report"
FIXTURE_HTML = (
    b"<html><title>Pentagon UAP report</title><p>The Pentagon released the new "
    b"UAP report today. Officials said five incidents were reviewed. The report "
    b"found no evidence of non-human technology.</p></html>"
)


class FixtureTransport:
    calls = 0

    def get(self, url, *, headers, policy):
        if url != FIXTURE_URL or self.calls:
            raise RuntimeError("Live Test C fixture received unexpected acquisition work")
        self.calls += 1
        return HttpResponse(200, FIXTURE_URL, {"content-type": "text/html"}, FIXTURE_HTML)


def _identity_snapshot(conn) -> dict[str, list]:
    queries = {
        "promotions": "SELECT id, promotion_identity, claim_id FROM article_analysis_promotions ORDER BY id",
        "claims": "SELECT id, story_id, state, accepted_at FROM claims ORDER BY id",
        "assignments": "SELECT id, claim_id, to_story_id, reason FROM claim_story_assignment_history ORDER BY id",
        "stories": "SELECT id, lifecycle, created_at, updated_at, deleted_at FROM stories ORDER BY id",
        "evolution": "SELECT id, story_id, document_id FROM story_evolution_events ORDER BY id",
        "story_revisions": "SELECT id, story_id, claim_set_hash FROM story_revisions ORDER BY id",
        "story_revision_claims": "SELECT revision_id, claim_id, position FROM story_revision_claims ORDER BY revision_id, position",
        "story_revision_documents": "SELECT revision_id, document_id, role FROM story_revision_documents ORDER BY revision_id, document_id",
        "acceptance_history": "SELECT id, claim_id, from_state, to_state, reason FROM claim_state_history ORDER BY id",
        "reports": "SELECT id, target_type, target_id, current_revision_id FROM living_reports ORDER BY id",
        "report_revisions": "SELECT id, report_id, claim_set_hash FROM report_revisions ORDER BY id",
        "report_causes": "SELECT id, revision_id, cause_id, claim_id, evidence_span_id, document_id FROM report_revision_causes ORDER BY id",
        "alerts": "SELECT id, rule_id, report_revision_id, dedupe_key, cause_json, status FROM alerts ORDER BY id",
        "deliveries": "SELECT id, alert_id, channel, status FROM alert_deliveries ORDER BY id",
    }
    return {
        name: [tuple(row) for row in conn.execute(query)]
        for name, query in queries.items()
    }


def run(database: Path) -> dict:
    apply_migrations(database)
    core = CoreService(database)
    category = core.create_category({"slug": "live-test-c", "name": "Live Test C"})
    topic = core.create_topic({"category_id": category["id"], "slug": "uap", "name": "UAP"})
    core.create_vocabulary(topic["id"], {"term": "UAP", "term_type": "include"})
    source = core.create_source(
        {"name": "Live Test C fixture", "slug": "live-test-c", "homepage_url": FIXTURE_URL}
    )
    policy = MonitoringPolicyService(database).create(
        {
            "name": "Live Test C policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        }
    )
    monitor = MonitorService(database).create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "need_type": "topic",
            "need_id": topic["id"],
            "next_check_at": DUE_AT,
        }
    )
    AlertService(database).create_rule(
        {"name": "Live Test C exact causes", "target_type": "all"}
    )

    transport = FixtureTransport()
    queue = build_worker_queue(database)
    SchedulerProcess(database).run_once()
    acquisition_worker = WorkerProcess(
        database,
        MonitorExecutionService(
            database,
            acquisition_service=AcquisitionService(database, transport=transport),
        ).handlers(),
        worker_id="live-test-c-acquisition",
        queue=queue,
    )
    acquired = acquisition_worker.run_once(now=NOW)
    if not acquired or acquired["status"] != "succeeded":
        raise RuntimeError("Live Test C acquisition did not succeed")

    worker = WorkerProcess(
        database,
        build_worker_handlers(database),
        worker_id="live-test-c-pipeline",
        queue=build_worker_queue(database),
    )
    completed = []
    while True:
        item = worker.run_once(now=NOW)
        if item is None:
            break
        completed.append(item)
    required = {
        "document_version_process",
        "automatic_story_stage",
        "automatic_report_stage",
        "automatic_alert_stage",
    }
    if not required <= {item["job_type"] for item in completed}:
        raise RuntimeError("Live Test C did not execute every automatic stage")
    if any(item["status"] != "succeeded" for item in completed):
        raise RuntimeError("Live Test C produced a failed automatic stage")

    conn = storage.connect(database)
    try:
        before = _identity_snapshot(conn)
        chain = conn.execute(
            """
            SELECT d.id AS document_id, dv.id AS document_version_id,
                   dv.artifact_id, aa.id AS analysis_id, p.id AS promotion_id,
                   c.id AS claim_id, es.id AS evidence_span_id, c.story_id,
                   sr.id AS story_revision_id, rr.id AS report_revision_id,
                   a.id AS alert_id, ad.id AS delivery_id,
                   (SELECT id FROM jobs
                    WHERE job_type = 'automatic_story_stage'
                      AND json_extract(result_json, '$.claim_id') = c.id
                      AND json_extract(result_json, '$.revision_id') = sr.id
                    ORDER BY id LIMIT 1) AS story_job_id,
                   (SELECT id FROM jobs
                    WHERE job_type = 'automatic_report_stage'
                      AND json_extract(result_json, '$.claim_id') = c.id
                      AND json_extract(result_json, '$.revision_id') = rr.id
                    ORDER BY id LIMIT 1) AS report_job_id,
                   (SELECT j.id FROM jobs j
                    WHERE j.job_type = 'automatic_alert_stage'
                      AND EXISTS (
                          SELECT 1 FROM json_each(json_extract(j.result_json, '$.alert_ids'))
                          WHERE value = a.id
                      )
                    ORDER BY j.id LIMIT 1) AS alert_job_id
            FROM alerts a
            JOIN alert_deliveries ad ON ad.alert_id = a.id AND ad.channel = 'in_app'
            JOIN report_revisions rr ON rr.id = a.report_revision_id
            JOIN report_revision_claims rrc ON rrc.revision_id = rr.id
            JOIN claims c ON c.id = rrc.claim_id
            JOIN article_analysis_promotions p ON p.claim_id = c.id
            JOIN article_analyses aa ON aa.id = c.article_analysis_id
            JOIN claim_evidence ce ON ce.claim_id = c.id
            JOIN evidence_spans es ON es.id = ce.evidence_span_id
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id AND d.source_id = ?
            JOIN story_revision_claims src ON src.claim_id = c.id
            JOIN story_revisions sr ON sr.id = src.revision_id AND sr.story_id = c.story_id
            ORDER BY a.id, c.id LIMIT 1
            """,
            (source["id"],),
        ).fetchone()
    finally:
        conn.close()
    if (
        chain is None
        or not all(chain[key] for key in ("story_job_id", "report_job_id", "alert_job_id"))
        or len(before["alerts"]) < 1
        or len(before["alerts"]) != len(before["deliveries"])
    ):
        raise RuntimeError("Live Test C exact persisted chain is incomplete")

    processing = next(item for item in completed if item["job_type"] == "document_version_process")
    build_worker_queue(database).rerun(processing["id"])
    while worker.run_once(now=NOW) is not None:
        pass
    conn = storage.connect(database)
    try:
        after = _identity_snapshot(conn)
    finally:
        conn.close()
    if after != before:
        raise RuntimeError("Live Test C replay created duplicate domain effects")
    integrity = check_database(database)
    if not integrity.ok:
        raise RuntimeError(f"Live Test C integrity failed: {[item.code for item in integrity.issues]}")
    return {
        "status": "passed",
        "database": str(database.resolve()),
        "external_network_calls": 0,
        "provider_calls": 0,
        "fixture_acquisition_calls": transport.calls,
        "source_id": source["id"],
        "monitor_id": monitor["id"],
        "chain": dict(chain),
        "stage_job_ids": [item["id"] for item in completed],
        "counts": {name: len(rows) for name, rows in after.items()},
        "replay": "exact_logical_identities_unchanged",
        "integrity": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unattended Live Test C")
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()
    database = args.database or Path(tempfile.mkdtemp(prefix="newsroom-live-test-c-")) / "newsroom.db"
    print(json.dumps(run(database), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
