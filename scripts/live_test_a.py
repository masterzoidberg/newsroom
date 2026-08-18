"""Live Test A — real-network Source Monitor runtime acceptance (MANUAL).

THIS SCRIPT IS A LIVE/MANUAL ACCEPTANCE HARNESS. It makes real requests to the
public internet through the production Newsroom runtime composition:

    real public Source
      -> SchedulerProcess
      -> SchedulerService (durable monitor_check Job)
      -> WorkerProcess
      -> MonitorExecutionService
      -> real DNS + real HTTP/HTTPS (UrllibHttpTransport)
      -> AcquisitionService
      -> Document / DocumentVersion / acquisition_events
      -> truthful monitor_activity (changed / no_change / error)

It is intentionally NOT part of the offline CI suite: it depends on live
third-party endpoints and must be run explicitly by an operator, never by the
normal test run. It does not weaken any acquisition safety control (SSRF
validation, redirect bounds, response-size limits, timeouts, feed-entry limits,
HTML parsing limits all stay at their production defaults).

No AI, no semantic relevance, no article analysis, no Evidence/Claims, no
Story/report/alert work is invoked or expected.

Usage (Windows PowerShell):

    python scripts/live_test_a.py --dir "$env:TEMP/newsroom_live_test_a"

Every scenario gets its own disposable SQLite database under --dir (a
directory outside the repository by default). No runtime data is written
inside the repository.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from newsroom import storage
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorService, MonitoringPolicyService
from newsroom.runtime import build_worker_handlers, build_worker_queue
from newsroom.scheduler import SchedulerProcess
from newsroom.worker import WorkerProcess


def utc_now_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def seconds_ago(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def query(db_path: Path, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = storage.connect(db_path)
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def count(db_path: Path, table: str, where: str = "1 = 1", params: tuple[Any, ...] = ()) -> int:
    conn = storage.connect(db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
    finally:
        conn.close()


def build_worker(db_path: Path, worker_id: str) -> WorkerProcess:
    """Compose the production handler registry + queue + worker process."""
    return WorkerProcess(db_path, build_worker_handlers(db_path), worker_id=worker_id, queue=build_worker_queue(db_path))


def bootstrap(
    db_path: Path,
    *,
    name: str,
    slug: str,
    homepage: str | None,
    feed_url: str | None,
    source_kind: str,
    channels: list[str],
    due_seconds_ago: int,
) -> dict[str, Any]:
    from newsroom.domain import CoreService

    core = CoreService(db_path)
    payload: dict[str, Any] = {"name": name, "slug": slug}
    if homepage:
        payload["homepage_url"] = homepage
    if feed_url:
        payload["feed_url"] = feed_url
    payload["source_kind"] = source_kind
    source = core.create_source(payload)
    policy = MonitoringPolicyService(db_path).create(
        {
            "name": f"{slug}-policy",
            "allowed_channels": channels,
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 600,
            "backoff_rules": {"error_multiplier": 3.0, "no_change_multiplier": 2.0},
            "retirement_criteria": {"max_consecutive_errors": 5},
        }
    )
    monitor = MonitorService(db_path).create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "next_check_at": seconds_ago(due_seconds_ago),
        }
    )
    return {"source": source, "policy": policy, "monitor": monitor}


def schedule_and_drain(db_path: Path, worker: WorkerProcess) -> dict[str, Any]:
    scheduled = SchedulerProcess(db_path).run_once()
    finished = worker.run_once()
    return {"scheduled": scheduled, "finished": finished}


def force_due(db_path: Path, monitor_id: str, seconds_ago_value: int) -> None:
    MonitorService(db_path).update(monitor_id, {"next_check_at": seconds_ago(seconds_ago_value)})


def evidence(db_path: Path, source_id: str, monitor_id: str) -> dict[str, Any]:
    return {
        "source_documents": count(db_path, "documents", "source_id = ?", (source_id,)),
        "source_document_versions": count(
            db_path,
            "document_versions",
            "document_id IN (SELECT id FROM documents WHERE source_id = ?)",
            (source_id,),
        ),
        "documents": query(db_path, "SELECT id, canonical_url, title FROM documents WHERE source_id = ? ORDER BY created_at, id", (source_id,)),
        "document_versions": query(
            db_path,
            "SELECT dv.id, d.id AS document_id, dv.content_hash, dv.retrieved_at, dv.etag, dv.last_modified "
            "FROM document_versions dv JOIN documents d ON d.id = dv.document_id "
            "WHERE d.source_id = ? ORDER BY dv.retrieved_at, dv.id",
            (source_id,),
        ),
        "acquisition_events": query(
            db_path,
            "SELECT id, channel, request_url, final_url, outcome, status_code, error_code, observed_at "
            "FROM acquisition_events WHERE source_id = ? ORDER BY observed_at, id",
            (source_id,),
        ),
        "monitor_activity": query(
            db_path,
            "SELECT id, outcome, new_items, changed_items, relevant_items, error_code, observed_at "
            "FROM monitor_activity WHERE monitor_id = ? ORDER BY observed_at, id",
            (monitor_id,),
        ),
    }


def monitor_snapshot(db_path: Path, monitor_id: str) -> dict[str, Any]:
    return MonitorService(db_path).get(monitor_id)


def jobs_for_monitor(db_path: Path, monitor_id: str) -> list[dict[str, Any]]:
    return query(
        db_path,
        "SELECT id, status, job_type, failure_cause, attempts, idempotency_key FROM jobs WHERE monitor_id = ? ORDER BY created_at, id",
        (monitor_id,),
    )


def run_rss_scenario(run_dir: Path) -> dict[str, Any]:
    db_path = run_dir / "scenario_a.sqlite3"
    apply_migrations(db_path)
    items = bootstrap(
        db_path,
        name="Live Test A RSS (NPR)",
        slug="live-a-rss",
        homepage="https://www.npr.org/",
        feed_url="https://feeds.npr.org/1001/rss.xml",
        source_kind="feed",
        channels=["rss"],
        due_seconds_ago=7,
    )
    source, monitor = items["source"], items["monitor"]
    worker = build_worker(db_path, "live-worker-rss")

    first = schedule_and_drain(db_path, worker)
    evidence_first = evidence(db_path, source["id"], monitor["id"])
    jobs_first = jobs_for_monitor(db_path, monitor["id"])

    force_due(db_path, monitor["id"], 60)
    second = schedule_and_drain(db_path, worker)
    evidence_second = evidence(db_path, source["id"], monitor["id"])
    jobs_second = jobs_for_monitor(db_path, monitor["id"])

    return {
        "db_path": str(db_path),
        "source": source,
        "monitor_after": monitor_snapshot(db_path, monitor["id"]),
        "first": first,
        "second": second,
        "evidence_first": evidence_first,
        "evidence_second": evidence_second,
        "jobs_first": jobs_first,
        "jobs_second": jobs_second,
    }


def run_html_scenario(run_dir: Path, *, label: str, name: str, slug: str, url: str, due_seconds_ago: int = 7) -> dict[str, Any]:
    db_path = run_dir / f"scenario_{slug}.sqlite3"
    apply_migrations(db_path)
    items = bootstrap(
        db_path,
        name=name,
        slug=slug,
        homepage=url,
        feed_url=None,
        source_kind="web",
        channels=["direct_http"],
        due_seconds_ago=due_seconds_ago,
    )
    source, monitor = items["source"], items["monitor"]
    worker = build_worker(db_path, f"live-worker-{slug}")

    first = schedule_and_drain(db_path, worker)
    evidence_first = evidence(db_path, source["id"], monitor["id"])

    force_due(db_path, monitor["id"], 60)
    second = schedule_and_drain(db_path, worker)
    evidence_second = evidence(db_path, source["id"], monitor["id"])

    return {
        "db_path": str(db_path),
        "source": source,
        "monitor_after": monitor_snapshot(db_path, monitor["id"]),
        "first": first,
        "second": second,
        "evidence_first": evidence_first,
        "evidence_second": evidence_second,
        "jobs": jobs_for_monitor(db_path, monitor["id"]),
    }


def run_failure_scenario(run_dir: Path) -> dict[str, Any]:
    db_path = run_dir / "scenario_failure.sqlite3"
    apply_migrations(db_path)
    items = bootstrap(
        db_path,
        name="Live Test A Failure (404)",
        slug="live-a-failure",
        homepage="https://example.com/definitely-not-a-real-page-xyz",
        feed_url=None,
        source_kind="web",
        channels=["direct_http"],
        due_seconds_ago=9,
    )
    source, monitor = items["source"], items["monitor"]
    worker = build_worker(db_path, "live-worker-failure")
    result = schedule_and_drain(db_path, worker)
    return {
        "db_path": str(db_path),
        "source": source,
        "monitor_after": monitor_snapshot(db_path, monitor["id"]),
        "result": result,
        "evidence": evidence(db_path, source["id"], monitor["id"]),
        "jobs": jobs_for_monitor(db_path, monitor["id"]),
    }


def run_restart_scenario(run_dir: Path) -> dict[str, Any]:
    db_path = run_dir / "scenario_restart.sqlite3"
    apply_migrations(db_path)
    items = bootstrap(
        db_path,
        name="Live Test A Restart (example.org)",
        slug="live-a-restart",
        homepage="https://example.org/",
        feed_url=None,
        source_kind="web",
        channels=["direct_http"],
        due_seconds_ago=11,
    )
    monitor = items["monitor"]

    # Process 1: scheduler only — persist the queued obligation.
    scheduler_1 = SchedulerProcess(db_path)
    scheduled = scheduler_1.run_once()
    del scheduler_1
    queued = count(db_path, "jobs", "status = 'queued' AND monitor_id = ?", (monitor["id"],))

    # Process 2: recreate process objects against the same DB; worker drains.
    worker_2 = build_worker(db_path, "live-worker-restart-2")
    finished = worker_2.run_once()
    return {
        "db_path": str(db_path),
        "source": items["source"],
        "monitor_after": monitor_snapshot(db_path, monitor["id"]),
        "scheduled": scheduled,
        "queued_after_scheduler": queued,
        "finished": finished,
        "evidence": evidence(db_path, items["source"]["id"], monitor["id"]),
        "jobs": jobs_for_monitor(db_path, monitor["id"]),
    }


def run_disabled_scenario(run_dir: Path) -> dict[str, Any]:
    db_path = run_dir / "scenario_disabled.sqlite3"
    apply_migrations(db_path)
    items = bootstrap(
        db_path,
        name="Live Test A Disabled (example.net)",
        slug="live-a-disabled",
        homepage="https://example.net/",
        feed_url=None,
        source_kind="web",
        channels=["direct_http"],
        due_seconds_ago=13,
    )
    monitor = items["monitor"]

    scheduled = SchedulerProcess(db_path).run_once()
    MonitorService(db_path).disable(monitor["id"])

    worker = build_worker(db_path, "live-worker-disabled")
    finished = worker.run_once()
    return {
        "db_path": str(db_path),
        "source": items["source"],
        "monitor_after": monitor_snapshot(db_path, monitor["id"]),
        "scheduled": scheduled,
        "finished": finished,
        "evidence": evidence(db_path, items["source"]["id"], monitor["id"]),
        "jobs": jobs_for_monitor(db_path, monitor["id"]),
    }


def provider_usage_summary(db_path: Path) -> dict[str, Any]:
    return {
        "rows": query(
            db_path,
            "SELECT capability, provider, request_type, COUNT(*) AS n FROM provider_usage GROUP BY capability, provider, request_type ORDER BY capability, provider, request_type",
        ),
        "total": count(db_path, "provider_usage"),
    }


def census(db_path: Path) -> dict[str, Any]:
    return {
        "sources": count(db_path, "sources"),
        "monitors": count(db_path, "monitors"),
        "jobs": count(db_path, "jobs"),
        "jobs_by_status": query(db_path, "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status ORDER BY status"),
        "acquisition_events": count(db_path, "acquisition_events"),
        "documents": count(db_path, "documents"),
        "document_versions": count(db_path, "document_versions"),
        "monitor_activity": count(db_path, "monitor_activity"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live Test A — real-network Source Monitor runtime acceptance (manual).")
    parser.add_argument("--dir", default=None, help="Directory for disposable live-test databases (defaults to TEMP/newsroom_live_test_a).")
    args = parser.parse_args(argv)
    run_dir = Path(args.dir) if args.dir else (Path(tempfile.gettempdir()) / "newsroom_live_test_a")
    run_dir.mkdir(parents=True, exist_ok=True)

    print("LIVE TEST A — real-network Source Monitor runtime acceptance (manual)")
    print(f"run directory: {run_dir}")
    print("production composition: SchedulerProcess -> durable monitor_check -> WorkerProcess -> MonitorExecutionService -> AcquisitionService (real DNS + HTTP/HTTPS)")

    results: dict[str, Any] = {"started_at": utc_now_z(), "run_dir": str(run_dir)}
    results["scenario_a"] = run_rss_scenario(run_dir)
    results["scenario_b"] = run_html_scenario(run_dir, label="B", name="Live Test A HTML (example.com)", slug="live-a-html", url="https://example.com/")
    results["scenario_c"] = run_html_scenario(run_dir, label="C", name="Live Test A Official (usa.gov)", slug="live-a-official", url="https://www.usa.gov/", due_seconds_ago=15)
    results["scenario_d"] = run_failure_scenario(run_dir)
    results["scenario_e"] = run_restart_scenario(run_dir)
    results["scenario_f"] = run_disabled_scenario(run_dir)

    db_paths = [Path(item["db_path"]) for item in results.values() if isinstance(item, dict) and item.get("db_path")]
    results["aggregate"] = {
        "databases": [str(p) for p in db_paths],
        "census_total": {
            "sources": sum(count(p, "sources") for p in db_paths),
            "monitors": sum(count(p, "monitors") for p in db_paths),
            "jobs": sum(count(p, "jobs") for p in db_paths),
            "acquisition_events": sum(count(p, "acquisition_events") for p in db_paths),
            "documents": sum(count(p, "documents") for p in db_paths),
            "document_versions": sum(count(p, "document_versions") for p in db_paths),
            "monitor_activity": sum(count(p, "monitor_activity") for p in db_paths),
        },
        "provider_usage": {p.name: provider_usage_summary(p) for p in db_paths},
    }
    results["finished_at"] = utc_now_z()

    report_path = run_dir / "live_test_a.evidence.json"
    report_path.write_text(json.dumps(results, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\nevidence written to {report_path}")
    return 0


if __name__ == "__main__":  # manual live acceptance only; never imported by the test suite
    raise SystemExit(main())