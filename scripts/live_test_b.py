"""Live Test B — one real provider article analysis through the production pipeline.

Manual, opt-in operator harness for the Phase 21 live-provider gate. It is NOT
part of the offline test suite and is never run by CI.

Pipeline exercised (all real services, real HTTP, real provider call):

    Source (public URL)
      → Monitor bound to an approved information need
      → Scheduler → monitor_check Job → Worker
      → Acquisition → DocumentVersion + Phase 18 artifact
      → document_version_process Job → Worker
      → automatic relevance=true
      → real OpenAI-compatible ArticleAnalysis call (bounded: exactly one page)
      → validated structured output → durable article_analyses row
      → STOP (no EvidenceSpans, no Claims, no Story/Report/Alert work)

Secrets policy: this file never contains an API key. The credential is read
from ``NEWSROOM_ANALYSIS_API_KEY`` or the conventional ``OPENAI_API_KEY``
environment variable; it is never printed, logged, persisted, or exported.

Cost safety: analysis runs only for the disposable test database, under an
explicit tiny lifetime budget (default USD $0.10, 2 paid requests), with one
HTML page (one required analysis call) and bounded output tokens.

Usage:

    python scripts/live_test_b.py --root <runtime-root> [options]

    --root            runtime root OUTSIDE the repository (a disposable
                      ``dev`` root under it receives the test database)
    --url             public article URL (default: NASA UAP page)
    --terms           comma-separated approved scope terms
                      (default: UAP,UFO,unidentified anomalous phenomena,
                      anomalous phenomena,unidentified flying object,flying saucer)
    --model           model override for NEWSROOM_ANALYSIS_MODEL
                      (default: gpt-4o-mini)
    --max-tokens      output token cap for NEWSROOM_ANALYSIS_MAX_TOKENS
                      (default 1200)
    --timeout         timeout seconds for NEWSROOM_ANALYSIS_TIMEOUT_SECONDS
                      (default 90)
    --max-retries     SDK retries for NEWSROOM_ANALYSIS_MAX_RETRIES (default 0)
    --budget-usd      lifetime USD cap in the disposable DB (default 0.10)

Exit codes: 0 PASS, 2 BLOCKED (no credential), 3 FAIL (classified message).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from newsroom import storage  # noqa: E402
from newsroom.acquisition import AcquisitionError, AcquisitionService  # noqa: E402
from newsroom.article_analysis import (  # noqa: E402
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_SCHEMA_VERSION,
    ArticleAnalysisService,
    OpenAICompatibleArticleAnalysisProvider,
)
from newsroom.config import RuntimeConfig  # noqa: E402
from newsroom.document_processing import DocumentProcessingExecutionService  # noqa: E402
from newsroom.domain import CoreService  # noqa: E402
from newsroom.jobs import BudgetService, DOCUMENT_VERSION_PROCESS_JOB_TYPE, MONITOR_CHECK_JOB_TYPE  # noqa: E402
from newsroom.migrations import apply_migrations  # noqa: E402
from newsroom.monitoring import (  # noqa: E402
    MonitorExecutionService,
    MonitorService,
    MonitoringPolicyService,
)
from newsroom.runtime import build_worker_queue  # noqa: E402
from newsroom.scheduler import SchedulerProcess  # noqa: E402
from newsroom.worker import WorkerProcess  # noqa: E402

DEFAULT_URL = "https://science.nasa.gov/uap/"
DEFAULT_TERMS = (
    "UAP",
    "UFO",
    "unidentified anomalous phenomena",
    "anomalous phenomena",
    "unidentified flying object",
    "flying saucer",
)
DEFAULT_MODEL = "gpt-4o-mini"


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _count(db, table: str) -> int:
    conn = storage.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _query(db, sql: str, params: tuple = ()):
    conn = storage.connect(db)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="runtime root outside the repository")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--terms", default=",".join(DEFAULT_TERMS))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--budget-usd", type=float, default=0.10)
    return parser


def main(argv: list[str] | None = None) -> int:
    options = build_parser().parse_args(argv)

    api_key = os.environ.get("NEWSROOM_ANALYSIS_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("LIVE TEST B BLOCKED — NEWSROOM_ANALYSIS_API_KEY / OPENAI_API_KEY absent")
        return 2

    # Explicit opt-in for the disposable test context only.
    os.environ["NEWSROOM_ANALYSIS_PROVIDER"] = "openai"
    os.environ["NEWSROOM_ANALYSIS_MODEL"] = options.model
    os.environ["NEWSROOM_ANALYSIS_TIMEOUT_SECONDS"] = str(options.timeout)
    os.environ["NEWSROOM_ANALYSIS_CONNECT_TIMEOUT_SECONDS"] = "10"
    os.environ["NEWSROOM_ANALYSIS_MAX_TOKENS"] = str(options.max_tokens)
    os.environ["NEWSROOM_ANALYSIS_MAX_RETRIES"] = str(options.max_retries)
    os.environ["NEWSROOM_ANALYSIS_MAX_PAID_CALLS"] = "1"
    os.environ["NEWSROOM_ANALYSIS_MAX_PAID_CALLS_PER_WORK"] = "1"
    os.environ["NEWSROOM_ANALYSIS_MAX_PAID_COST_USD"] = str(options.budget_usd)
    os.environ["NEWSROOM_ANALYSIS_MAX_PAID_COST_USD_PER_WORK"] = str(options.budget_usd)

    try:
        runtime = RuntimeConfig.for_environment("dev", root=options.root)
    except ValueError as exc:
        print(f"LIVE TEST B FAIL — CONFIGURATION: {exc}")
        return 3
    runtime.ensure_runtime_dirs()
    db = runtime.database_path
    if db.exists():
        db.unlink()
    apply_migrations(db)

    terms = [term.strip() for term in options.terms.split(",") if term.strip()]
    if not terms:
        print("LIVE TEST B FAIL — CONFIGURATION: at least one scope term is required")
        return 3

    t0 = _now()
    core = CoreService(db)
    category = core.create_category({"slug": "livetest", "name": "Live Test B"})
    topic = core.create_topic({"category_id": category["id"], "slug": "uap", "name": "UAP"})
    for term in terms:
        core.create_vocabulary(topic["id"], {"term": term, "term_type": "include"})
    source = core.create_source({
        "name": "NASA UAP",
        "slug": "nasa-uap",
        "homepage_url": options.url,
        "source_kind": "official",
        "default_quality": "primary",
    })
    policy = MonitoringPolicyService(db).create({
        "name": "livetest-policy",
        "allowed_channels": ["direct_http"],
        "base_cadence_seconds": 60,
        "min_cadence_seconds": 30,
        "max_cadence_seconds": 300,
    })
    monitor = MonitorService(db).create({
        "target_type": "source",
        "target_id": source["id"],
        "policy_id": policy["id"],
        "need_type": "topic",
        "need_id": topic["id"],
        "next_check_at": t0,
    })

    budgets = BudgetService(db)
    budgets.configure_limit("global", None, "lifetime", "usd", options.budget_usd)
    budgets.configure_limit("global", None, "lifetime", "paid_requests", 2)
    budgets.set_paid_enabled(True)

    queue = build_worker_queue(db)
    monitor_worker = WorkerProcess(
        db,
        MonitorExecutionService(db, acquisition_service=AcquisitionService(db)).handlers(),
        worker_id="live-test-b-monitor",
        queue=queue,
    )
    SchedulerProcess(db).run_once()
    acquisition_job = monitor_worker.run_once(now=t0)
    if acquisition_job is None or acquisition_job["status"] != "succeeded":
        failure = acquisition_job.get("failure_cause") if acquisition_job else "no job claimed"
        print(f"LIVE TEST B FAIL — SOURCE-SPECIFIC: acquisition failed ({failure})")
        return 3
    version = _query(db, "SELECT * FROM document_versions")[0] if _query(db, "SELECT 1 FROM document_versions") else None
    if version is None:
        print("LIVE TEST B FAIL — SOURCE-SPECIFIC: no DocumentVersion was created")
        return 3
    print(f"[live-test-b] acquisition ok: version={version['id']} outcome={acquisition_job.get('result', {}).get('outcome')}")

    captured: dict[str, OpenAICompatibleArticleAnalysisProvider] = {}

    def provider_factory(config):
        provider = OpenAICompatibleArticleAnalysisProvider(config)
        captured["provider"] = provider
        return provider

    analysis_service = ArticleAnalysisService(db, paid_provider_factory=provider_factory)
    processing_worker = WorkerProcess(
        db,
        DocumentProcessingExecutionService(db, analysis_service=analysis_service).handlers(),
        worker_id="live-test-b-processing",
        queue=build_worker_queue(db),
    )
    started = time.monotonic()
    processing_job = processing_worker.run_once(now=_now())
    wall_seconds = time.monotonic() - started
    if processing_job is None or processing_job["status"] != "succeeded":
        failure = processing_job.get("failure_cause") if processing_job else "no job claimed"
        detail = (processing_job.get("attempts_detail") or [{}])[-1].get("error_detail", "") if processing_job else ""
        print(f"LIVE TEST B FAIL — NEWSROOM DEFECT: processing failed ({failure}) {detail[:300]}")
        return 3

    result = processing_job["result"] or {}
    relevance = result.get("relevance") or {}
    analysis = result.get("analysis") or {}
    if relevance.get("status") != "evaluated" or relevance.get("relevant") is not True:
        print(f"LIVE TEST B FAIL — SOURCE-SPECIFIC: relevance was {relevance.get('status')} relevant={relevance.get('relevant')}")
        return 3
    if not analysis:
        print("LIVE TEST B FAIL — NEWSROOM DEFECT: no analysis in processing result")
        return 3

    provider = captured.get("provider")
    usage = provider.last_usage if provider is not None else {}
    usage_rows = _query(
        db,
        "SELECT id, provider, request_type, token_units, latency_ms, estimated_cost_usd, outcome, created_at "
        "FROM provider_usage WHERE capability = 'article_analysis' ORDER BY created_at, id",
    )
    latency_ms = None
    if usage_rows:
        latency_ms = usage_rows[0]["latency_ms"] or int(wall_seconds * 1000)

    article = _query(db, "SELECT * FROM article_analyses WHERE id = ?", (analysis["id"],))[0]

    print("\n=== LIVE TEST B RESULT ===")
    print(f"source url            : {options.url}")
    print(f"information need      : topic={topic['id']} ({topic['name']})")
    print(f"approved scope terms  : {terms}")
    print(f"relevance             : {relevance.get('status')} relevant={relevance.get('relevant')} "
          f"stage={relevance.get('stage')} score={relevance.get('score')}")
    print(f"analysis id           : {analysis['id']}")
    print(f"provider/model        : {analysis.get('provider')}/{analysis.get('model')} paid={analysis.get('paid')}")
    print(f"schema/prompt version : {article['schema_version']} / {article['prompt_version']}")
    print(f"confidence            : {article['confidence']}")
    print(f"relevance_id          : {article['relevance_id']}")
    print(f"monitor_id            : {article['monitor_id']}")
    print(f"scope_version         : {article['scope_version']}")
    print(f"artifact id/hash      : {article['artifact_id']} / {article['normalized_content_hash'][:16]}...")
    print(f"input/analyzed chars  : {article['input_char_count']} / {article['analyzed_char_count']} truncated={article['truncated']}")
    print(f"latency (wall ms)     : {int(wall_seconds * 1000)}; telemetry ms: {latency_ms}")
    print(f"usage tokens          : in={usage.get('input_tokens')} out={usage.get('output_tokens')} total={usage.get('token_units')}")
    print(f"cost                  : provider billing metadata unavailable; Newsroom estimate "
          f"recorded = ${usage_rows[0]['estimated_cost_usd'] if usage_rows else 0.0:.4f}")
    print(f"provider_usage rows   : {len(usage_rows)}")
    for row in usage_rows:
        outcome = json.loads(row["outcome"]) if row["outcome"] else {}
        print(f"  usage {row['id']}: route={outcome.get('route')} provider={row['provider']} "
              f"tokens={row['token_units']} latency_ms={row['latency_ms']} status={outcome.get('status')}")
    print(f"structured fields     : summary/developments/entities/dates/locations/significance/"
          f"novelty/claims/excerpts/confidence all validated")
    print(f"candidate claims      : {len((article['result_json'] and json.loads(article['result_json']).get('candidate_claims')) or [])}")
    print(f"candidate excerpts    : {len((article['result_json'] and json.loads(article['result_json']).get('candidate_evidence_excerpts')) or [])}")

    summary = json.loads(article["result_json"]).get("summary", "")
    print(f"analysis summary      : {summary[:220]}")
    if len(summary) > 220:
        print("  (truncated for display; full validated result persisted)")

    print("\n=== EVIDENCE BOUNDARY (must all be zero) ===")
    tables = ("evidence_spans", "claims", "claim_evidence", "stories", "story_revisions",
              "story_evolution_events", "living_reports", "alerts", "briefings")
    counts = {table: _count(db, table) for table in tables}
    for table in tables:
        print(f"  {table:24s} = {counts[table]}")
    if any(counts.values()):
        print("LIVE TEST B FAIL — NEWSROOM DEFECT: accepted-evidence automation occurred")
        return 3
    if counts["evidence_spans"] != 0 or counts["claims"] != 0:
        print("LIVE TEST B FAIL — NEWSROOM DEFECT: EvidenceSpans/Claims were created")
        return 3

    print("\nLIVE TEST B PASS — real provider analysis persisted; candidates only; no evidence created.")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual operator harness
    raise SystemExit(main())