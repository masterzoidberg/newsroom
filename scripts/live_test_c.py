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


def _count(conn, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


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
        before = {
            table: _count(conn, table)
            for table in (
                "article_analysis_promotions", "claims", "stories", "story_revisions",
                "claim_state_history", "report_revisions", "alerts", "alert_deliveries",
            )
        }
        chain = conn.execute(
            """
            SELECT d.id AS document_id, dv.id AS document_version_id,
                   dv.artifact_id, aa.id AS analysis_id, p.id AS promotion_id,
                   c.id AS claim_id, es.id AS evidence_span_id, c.story_id,
                   sr.id AS story_revision_id, rr.id AS report_revision_id,
                   a.id AS alert_id, ad.id AS delivery_id
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
    if chain is None or before["alerts"] < 1 or before["alerts"] != before["alert_deliveries"]:
        raise RuntimeError("Live Test C exact persisted chain is incomplete")

    processing = next(item for item in completed if item["job_type"] == "document_version_process")
    build_worker_queue(database).rerun(processing["id"])
    while worker.run_once(now=NOW) is not None:
        pass
    conn = storage.connect(database)
    try:
        after = {table: _count(conn, table) for table in before}
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
        "counts": after,
        "replay": "no_duplicate_domain_effects",
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
