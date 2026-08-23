from __future__ import annotations

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from newsroom import storage
from newsroom.article_analysis import (
    ANALYSIS_PROMPT_VERSION,
    ANALYSIS_SCHEMA_VERSION,
    ARTIFACT_INPUT_VIEW_VERSION,
    ArticleAnalysisService,
    analysis_identity_hash,
    analysis_input_text,
)
from newsroom.automatic_story_resolution import (
    AMBIGUOUS,
    DEFERRED,
    MATCHED_EXISTING,
    MAX_CANDIDATE_STORIES,
    NO_MATCH,
    QUALIFIED,
)
from newsroom.content_artifacts import ContentArtifactService
from newsroom.domain import CoreService, DomainConflict, DomainValidation
from newsroom.evidence import EvidenceService
from newsroom.evidence_promotion import ArticleAnalysisPromotionService
from newsroom.jobs import JobService
from newsroom.monitoring import (
    DocumentVersionRelevanceService,
    MonitorService,
    MonitoringPolicyService,
    RelevanceResult,
)
from newsroom.migrations import apply_migrations
from newsroom.story_automation import (
    AUTOMATIC_STORY_STAGE_JOB_TYPE,
    STAGE_COMPLETED,
    STAGE_DEFERRED,
    STAGE_TERMINAL,
    AutomaticStoryStageExecutionService,
    enqueue_story_stage,
    automatic_story_stage_completion_hook,
)
from newsroom.worker import RetryableJobFailure


T0 = "2026-08-23T12:00:00Z"
T1 = "2026-08-23T12:01:00Z"


def _promotion(db, *, proposition: str = "The agency released a UAP report") -> tuple[str, str]:
    from test_phase22_evidence_promotion import _analysis

    analysis = _analysis(
        db,
        text=proposition,
        excerpt=proposition,
        proposition=proposition,
    )
    outcome = ArticleAnalysisPromotionService(db).promote(analysis["id"])["outcomes"][0]
    return outcome["id"], outcome["claim_id"]


def _variant_promotion(db, suffix: str, *, proposition: str) -> tuple[str, str]:
    apply_migrations(db)
    core = CoreService(db)
    category = core.create_category({"slug": f"science-{suffix}", "name": f"Science {suffix}"})
    topic = core.create_topic(
        {"category_id": category["id"], "slug": f"uap-{suffix}", "name": f"UAP {suffix}"}
    )
    core.create_vocabulary(topic["id"], {"term": "UAP", "term_type": "include"})
    source = core.create_source(
        {
            "name": f"Example {suffix}",
            "slug": f"example-{suffix}",
            "homepage_url": f"https://{suffix}.example.test",
        }
    )
    policy = MonitoringPolicyService(db).create(
        {
            "name": f"Policy {suffix}",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
        }
    )
    monitor = MonitorService(db).create(
        {
            "target_type": "source",
            "target_id": source["id"],
            "policy_id": policy["id"],
            "need_type": "topic",
            "need_id": topic["id"],
            "next_check_at": T0,
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": f"https://{suffix}.example.test/report",
            "title": proposition,
        }
    )
    artifact = ContentArtifactService(db).create(
        normalized_text=proposition,
        content_kind="visible_text",
    )
    version_id = f"dv_phase23b_{suffix}"
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO document_versions
                    (id, document_id, retrieved_at, content_hash, content_kind,
                     artifact_id, normalized_json, created_at)
                VALUES (?, ?, ?, 'raw-phase23b', 'full_text', ?, '{}', ?)
                """,
                (version_id, document["id"], T0, artifact["id"], T0),
            )
    finally:
        conn.close()
    job = JobService(db).enqueue(
        "document_version_process",
        {
            "document_version_id": version_id,
            "document_id": document["id"],
            "source_id": source["id"],
            "monitor_id": monitor["id"],
            "scope_version": 1,
        },
        document_version_id=version_id,
        idempotency_key=f"phase23b:{suffix}",
    )
    relevance = DocumentVersionRelevanceService(db).persist_decision(
        job_id=job["id"],
        document_version_id=version_id,
        monitor_id=monitor["id"],
        scope_version=1,
        scope=MonitorService(db).scope_at_version(monitor["id"], 1),
        result=RelevanceResult(True, "exact", 1.0, ("UAP",), "match"),
        observed_at=T0,
    )
    loaded = ContentArtifactService(db).load_normalized_content(version_id)
    view = analysis_input_text(loaded)[1]
    input_hash = hashlib.sha256(view.encode()).hexdigest()
    analyzed_hash = hashlib.sha256(view.encode()).hexdigest()
    identity = analysis_identity_hash(
        document_version_id=version_id,
        relevance_id=relevance["id"],
        scope_version=1,
        schema_version=ANALYSIS_SCHEMA_VERSION,
        prompt_version=ANALYSIS_PROMPT_VERSION,
        provider="local",
        model="deterministic-local-v1",
        artifact_id=artifact["id"],
        normalized_content_hash=artifact["normalized_content_hash"],
        input_view_version=ARTIFACT_INPUT_VIEW_VERSION,
        input_content_hash=input_hash,
        analyzed_content_hash=analyzed_hash,
    )
    analysis = ArticleAnalysisService(db).persist(
        document_version_id=version_id,
        relevance_id=relevance["id"],
        monitor_id=monitor["id"],
        scope_version=1,
        job_id=job["id"],
        artifact_id=artifact["id"],
        normalized_content_hash=artifact["normalized_content_hash"],
        schema_version=ANALYSIS_SCHEMA_VERSION,
        prompt_version=ANALYSIS_PROMPT_VERSION,
        identity_hash=identity,
        provider="local",
        model="deterministic-local-v1",
        paid=False,
        confidence=0.9,
        input_char_count=len(view),
        analyzed_char_count=len(view),
        truncated=False,
        input_view_version=ARTIFACT_INPUT_VIEW_VERSION,
        input_content_hash=input_hash,
        analyzed_content_hash=analyzed_hash,
        result={
            "summary": "The agency reported an update.",
            "key_developments": ["The agency reported an update."],
            "entities": [],
            "dates": [],
            "locations": [],
            "significance": "The report is relevant.",
            "novelty": "The report is new.",
            "candidate_claims": [{"index": 0, "proposition": proposition}],
            "candidate_evidence_excerpts": [
                {"candidate_claim_index": 0, "excerpt": proposition}
            ],
            "confidence": 0.9,
        },
    )
    outcome = ArticleAnalysisPromotionService(db).promote(analysis["id"])["outcomes"][0]
    return outcome["id"], outcome["claim_id"]


def _story_with_claim(db, proposition: str, *, lifecycle: str = "developing"):
    story = CoreService(db).create_story({"headline": proposition, "lifecycle": lifecycle})
    claim = EvidenceService(db).create_claim(story["id"], {"proposition": proposition})
    return story, claim


def _claim_row(db, claim_id: str):
    conn = storage.connect(db)
    try:
        return conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    finally:
        conn.close()


def _count(db, table: str, where: str = "1=1", params: tuple = ()) -> int:
    conn = storage.connect(db)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
    finally:
        conn.close()


def _stage_job(db, promotion_id: str):
    return enqueue_story_stage(db, promotion_id)


def _processing_row(db, promotion_id: str):
    conn = storage.connect(db)
    try:
        return conn.execute(
            """
            SELECT j.*
            FROM jobs j
            JOIN article_analyses a ON a.job_id = j.id
            JOIN article_analysis_promotions p ON p.article_analysis_id = a.id
            WHERE p.id = ?
            """,
            (promotion_id,),
        ).fetchone()
    finally:
        conn.close()


def _run_stage(db, promotion_id: str):
    queue = JobService(db)
    job = _stage_job(db, promotion_id)
    service = AutomaticStoryStageExecutionService(db)
    claimed = queue.claim(job["id"], "phase23b-worker", now=T0)
    result = service.handle(claimed)
    return job, queue.complete(job["id"], "phase23b-worker", "succeeded", now=T1, outcome=result)


def test_verified_promotion_creates_one_durable_story_obligation_and_duplicate_reuses_it(tmp_db):
    promotion_id, _ = _promotion(tmp_db)

    first = _stage_job(tmp_db, promotion_id)
    second = _stage_job(tmp_db, promotion_id)

    assert first["id"] == second["id"]
    assert first["idempotency_key"] == f"automatic_story_stage:{promotion_id}"
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_STORY_STAGE_JOB_TYPE,)) == 1


def test_concurrent_duplicate_enqueue_produces_one_obligation(tmp_db):
    promotion_id, _ = _promotion(tmp_db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: _stage_job(tmp_db, promotion_id), range(2)))

    assert {job["id"] for job in jobs}.__len__() == 1
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_STORY_STAGE_JOB_TYPE,)) == 1


def test_corrupted_or_unverified_promotion_cannot_be_enqueued(tmp_db):
    from test_phase22_evidence_promotion import _analysis

    analysis = _analysis(
        tmp_db,
        text="The agency released a UAP report",
        excerpt="fabricated evidence",
        proposition="The agency released a UAP report",
    )
    promotion_id = ArticleAnalysisPromotionService(tmp_db).promote(analysis["id"])["outcomes"][0]["id"]

    with pytest.raises(DomainValidation):
        _stage_job(tmp_db, promotion_id)
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_STORY_STAGE_JOB_TYPE,)) == 0


def test_completion_hook_enqueues_verified_promotions_without_story_mutation(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    before = _count(tmp_db, "stories")
    hook = automatic_story_stage_completion_hook(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        row = _processing_row(tmp_db, promotion_id)
        with storage.write_tx(conn):
            hook(
                conn,
                row,
                "succeeded",
                {
                    "outcome": {
                        "promotion": {
                            "outcomes": [
                                {"code": "verified", "promotion_id": promotion_id, "claim_id": claim_id}
                            ]
                        }
                    }
                },
            )
    finally:
        conn.close()

    assert _count(tmp_db, "stories") == before
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_STORY_STAGE_JOB_TYPE,)) == 1
    assert _claim_row(tmp_db, claim_id)["story_id"] is None


def test_completion_hook_replay_and_partial_promotions_are_independent(tmp_db):
    first, _ = _variant_promotion(tmp_db, "a", proposition="The agency released a UAP report")
    second, _ = _variant_promotion(tmp_db, "b", proposition="The agency released a UAP report")
    hook = automatic_story_stage_completion_hook(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        row = _processing_row(tmp_db, first)
        context = {
            "outcome": {
                "promotion": {
                    "outcomes": [
                        {"code": "verified", "promotion_id": first},
                        {"code": "failed", "promotion_id": "not-enqueued"},
                        {"code": "verified", "promotion_id": second},
                    ]
                }
            }
        }
        with storage.write_tx(conn):
            hook(conn, row, "succeeded", context)
        with storage.write_tx(conn):
            hook(conn, row, "succeeded", context)
    finally:
        conn.close()

    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_STORY_STAGE_JOB_TYPE,)) == 2


def test_failed_processing_completion_does_not_enqueue_story_work(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    hook = automatic_story_stage_completion_hook(tmp_db)
    row = _processing_row(tmp_db, promotion_id)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            hook(
                conn,
                row,
                "failed",
                {"outcome": {"promotion": {"outcomes": [{"code": "verified", "promotion_id": promotion_id}]}}},
            )
    finally:
        conn.close()

    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_STORY_STAGE_JOB_TYPE,)) == 0


def test_matched_existing_story_assigns_once_records_event_and_evidence_bound_revision(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report")

    job, completed = _run_stage(tmp_db, promotion_id)
    assert completed["status"] == "succeeded"
    assert completed["result"]["stage_status"] == STAGE_COMPLETED
    assert completed["result"]["story_resolution"] == MATCHED_EXISTING
    assert _claim_row(tmp_db, claim_id)["story_id"] == story["id"]
    assert _count(tmp_db, "claim_story_assignment_history", "claim_id = ?", (claim_id,)) == 1
    assert _count(tmp_db, "story_evolution_events", "story_id = ?", (story["id"],)) == 1
    assert _count(tmp_db, "story_revisions", "story_id = ?", (story["id"],)) == 2

    conn = storage.connect(tmp_db)
    try:
        revision = conn.execute(
            "SELECT id FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC LIMIT 1",
            (story["id"],),
        ).fetchone()[0]
        row = conn.execute(
            """
                SELECT s.id AS source_id, src.claim_id, d.id AS document_id, dv.id AS version_id,
                   c.id AS claim_id, ce.evidence_span_id
            FROM story_revision_claims src
            JOIN claims c ON c.id = src.claim_id
            JOIN claim_evidence ce ON ce.claim_id = c.id
            JOIN evidence_spans es ON es.id = ce.evidence_span_id
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE src.revision_id = ?
            """,
            (revision,),
        ).fetchone()
        event = conn.execute(
            "SELECT decision_json FROM story_evolution_events WHERE story_id = ?",
            (story["id"],),
        ).fetchone()
        assert row["claim_id"] == claim_id
        assert row["source_id"] is not None
        assert row["document_id"] is not None
        assert row["version_id"] is not None
        assert row["evidence_span_id"] is not None
        context = json.loads(event["decision_json"])
        assert context["automatic_story_stage"]["promotion_id"] == promotion_id
        assert context["automatic_story_stage"]["claim_id"] == claim_id
        assert context["automatic_story_stage"]["job_id"] == job["id"]
    finally:
        conn.close()


def test_retry_after_successful_domain_mutation_reuses_checkpoint_and_does_not_duplicate_effects(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report")
    job = _stage_job(tmp_db, promotion_id)
    queue = JobService(tmp_db)
    claimed = queue.claim(job["id"], "worker-a", now=T0)
    assert claimed is not None
    service = AutomaticStoryStageExecutionService(tmp_db)
    first = service.handle(claimed)
    assert first["stage_status"] == STAGE_COMPLETED
    recovered = queue.recover_expired(now="2026-08-23T12:03:00Z")
    assert recovered == 1
    claimed_again = queue.claim(job["id"], "worker-b", now="2026-08-23T12:04:00Z")
    replay = service.handle(claimed_again)
    finished = queue.complete(
        job["id"],
        "worker-b",
        "succeeded",
        now="2026-08-23T12:04:00Z",
        outcome=replay,
    )

    assert finished["result"]["stage_status"] == STAGE_COMPLETED
    assert _claim_row(tmp_db, claim_id)["story_id"] == story["id"]
    assert _count(tmp_db, "claim_story_assignment_history", "claim_id = ?", (claim_id,)) == 1
    assert _count(tmp_db, "story_evolution_events", "story_id = ?", (story["id"],)) == 1
    assert _count(tmp_db, "story_revisions", "story_id = ?", (story["id"],)) == 2


def test_no_match_creates_one_story_with_cited_initial_revision(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)

    job, completed = _run_stage(tmp_db, promotion_id)

    assert completed["result"]["stage_status"] == STAGE_COMPLETED
    assert completed["result"]["story_resolution"] == NO_MATCH
    story_id = completed["result"]["story_id"]
    assert story_id
    assert _count(tmp_db, "stories") == 1
    assert _count(tmp_db, "story_revisions", "story_id = ?", (story_id,)) == 1
    assert _claim_row(tmp_db, claim_id)["story_id"] == story_id
    assert _count(tmp_db, "story_evolution_events", "story_id = ?", (story_id,)) == 1
    assert _count(tmp_db, "story_revision_claims", "claim_id = ?", (claim_id,)) == 1
    assert _count(tmp_db, "story_revision_documents", "revision_id = ?", (completed["result"]["revision_id"],)) == 1
    assert _claim_row(tmp_db, claim_id)["accepted_at"] is None
    assert job["id"] == completed["result"]["job_id"]


def test_new_story_retry_does_not_create_another_story_or_revision(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    job, first = _run_stage(tmp_db, promotion_id)
    assert first["result"]["stage_status"] == STAGE_COMPLETED

    replay = AutomaticStoryStageExecutionService(tmp_db).handle(JobService(tmp_db).get(job["id"]))

    assert replay == first["result"]
    assert _count(tmp_db, "stories") == 1
    assert _count(tmp_db, "story_revisions") == 1
    assert _count(tmp_db, "story_evolution_events") == 1


def test_explicit_story_stage_rerun_reuses_the_same_job_identity(tmp_db):
    from newsroom.story_automation import automatic_story_stage_rerun_factory

    promotion_id, _ = _promotion(tmp_db)
    job, completed = _run_stage(tmp_db, promotion_id)
    assert completed["status"] == "succeeded"

    rerun = automatic_story_stage_rerun_factory(tmp_db, job)

    assert rerun["id"] == job["id"]
    assert _count(tmp_db, "jobs", "job_type = ?", (AUTOMATIC_STORY_STAGE_JOB_TYPE,)) == 1


@pytest.mark.parametrize("lifecycle_action", ["archive", "delete"])
def test_lifecycle_race_never_assigns_archived_or_deleted_story(tmp_db, monkeypatch, lifecycle_action):
    promotion_id, claim_id = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report")
    service = AutomaticStoryStageExecutionService(tmp_db)
    original = service.resolver.resolve_verified_graph
    invalidated = False

    def resolve_then_invalidate(identifier, graph, **kwargs):
        nonlocal invalidated
        result = original(identifier, graph, **kwargs)
        if not invalidated:
            invalidated = True
            if lifecycle_action == "archive":
                CoreService(tmp_db).update_story(story["id"], {"lifecycle": "archived"})
            else:
                CoreService(tmp_db).delete_story(story["id"])
        return result

    monkeypatch.setattr(service.resolver, "resolve_verified_graph", resolve_then_invalidate)
    job = _stage_job(tmp_db, promotion_id)
    claimed = JobService(tmp_db).claim(job["id"], "worker", now=T0)
    result = service.handle(claimed)

    assert result["stage_status"] == STAGE_COMPLETED
    assert _claim_row(tmp_db, claim_id)["story_id"] != story["id"]
    assert _count(tmp_db, "stories") == 2


def test_claim_assigned_to_another_story_fails_closed(tmp_db, monkeypatch):
    promotion_id, claim_id = _promotion(tmp_db)
    first, _ = _story_with_claim(tmp_db, "The agency released a UAP report")
    other = CoreService(tmp_db).create_story({"headline": "Other Story"})
    service = AutomaticStoryStageExecutionService(tmp_db)
    original = service.resolver.resolve_verified_graph
    assigned = False

    def resolve_then_assign(identifier, graph, **kwargs):
        nonlocal assigned
        result = original(identifier, graph, **kwargs)
        if not assigned:
            assigned = True
            EvidenceService(tmp_db).assign_claim_to_story(claim_id, other["id"])
        return result

    monkeypatch.setattr(service.resolver, "resolve_verified_graph", resolve_then_assign)
    job = _stage_job(tmp_db, promotion_id)
    claimed = JobService(tmp_db).claim(job["id"], "worker", now=T0)
    result = service.handle(claimed)

    assert result["stage_status"] == STAGE_DEFERRED
    assert result["reason_code"] == "claim_already_assigned"
    assert _claim_row(tmp_db, claim_id)["story_id"] == other["id"]
    assert _count(tmp_db, "story_revisions", "story_id = ?", (first["id"],)) == 1


def test_ambiguous_resolution_is_terminal_defer_without_story_mutation(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    _story_with_claim(tmp_db, "The agency released a UAP report")
    _story_with_claim(tmp_db, "The agency released a UAP report")
    before = (_count(tmp_db, "stories"), _claim_row(tmp_db, claim_id)["story_id"])

    _, completed = _run_stage(tmp_db, promotion_id)

    assert completed["result"]["stage_status"] == STAGE_DEFERRED
    assert completed["result"]["story_resolution"] == AMBIGUOUS
    assert (_count(tmp_db, "stories"), _claim_row(tmp_db, claim_id)["story_id"]) == before


def test_candidate_saturation_defers_without_story_mutation(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    for _ in range(MAX_CANDIDATE_STORIES + 1):
        _story_with_claim(tmp_db, "The agency released a UAP report")
    before = _count(tmp_db, "stories")

    _, completed = _run_stage(tmp_db, promotion_id)

    assert completed["result"]["stage_status"] == STAGE_DEFERRED
    assert completed["result"]["reason_code"] == "candidate_set_saturated"
    assert _count(tmp_db, "stories") == before
    assert _claim_row(tmp_db, claim_id)["story_id"] is None


def test_deferred_checkpoint_replay_does_not_retry_deterministic_ambiguity(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    _story_with_claim(tmp_db, "The agency released a UAP report")
    _story_with_claim(tmp_db, "The agency released a UAP report")
    job, completed = _run_stage(tmp_db, promotion_id)

    replay = AutomaticStoryStageExecutionService(tmp_db).handle(JobService(tmp_db).get(job["id"]))

    assert completed["result"]["stage_status"] == STAGE_DEFERRED
    assert replay == completed["result"]
    assert _count(tmp_db, "stories") == 2


def test_production_runtime_registers_story_stage_handler_and_completion_hook(tmp_db):
    from newsroom.runtime import build_worker_handlers, build_worker_queue

    handlers = build_worker_handlers(tmp_db)
    queue = build_worker_queue(tmp_db)

    assert AUTOMATIC_STORY_STAGE_JOB_TYPE in handlers
    assert queue.completion_hook is not None


def test_same_obligation_concurrent_handlers_converge_on_one_result(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    job = _stage_job(tmp_db, promotion_id)
    queue = JobService(tmp_db)
    claimed = queue.claim(job["id"], "worker-a", now=T0)
    service = AutomaticStoryStageExecutionService(tmp_db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.handle(claimed), range(2)))

    assert all(result["stage_status"] == STAGE_COMPLETED for result in results)
    assert results[0] == results[1]
    assert _claim_row(tmp_db, claim_id)["story_id"] is not None
    assert _count(tmp_db, "stories") == 1
    assert _count(tmp_db, "story_evolution_events") == 1
    assert _count(tmp_db, "story_revisions") == 1


def test_cross_promotion_concurrency_re_resolves_after_first_story_creation(tmp_db):
    first_promotion, first_claim = _variant_promotion(
        tmp_db, "first", proposition="The agency released a UAP report"
    )
    second_promotion, second_claim = _variant_promotion(
        tmp_db, "second", proposition="The agency released a UAP report"
    )
    first_job = _stage_job(tmp_db, first_promotion)
    second_job = _stage_job(tmp_db, second_promotion)
    queue = JobService(tmp_db)
    first_claimed = queue.claim(first_job["id"], "worker-a", now=T0)
    second_claimed = queue.claim(second_job["id"], "worker-b", now=T0)
    service = AutomaticStoryStageExecutionService(tmp_db)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.handle, [first_claimed, second_claimed]))

    assert all(result["stage_status"] == STAGE_COMPLETED for result in results)
    assert _count(tmp_db, "stories") == 1
    assert _claim_row(tmp_db, first_claim)["story_id"] == _claim_row(tmp_db, second_claim)["story_id"]
    assert _count(tmp_db, "story_evolution_events") == 2
    assert _count(tmp_db, "story_revisions") == 2


def test_terminal_integrity_result_is_durable_and_not_retried_forever(tmp_db, monkeypatch):
    promotion_id, _ = _promotion(tmp_db)
    job = _stage_job(tmp_db, promotion_id)
    queue = JobService(tmp_db)
    claimed = queue.claim(job["id"], "worker", now=T0)
    service = AutomaticStoryStageExecutionService(tmp_db)

    def fail_verification(*_args):
        from newsroom.evidence_promotion import AutomaticPromotionIntegrityError

        raise AutomaticPromotionIntegrityError("corrupt", issues=("corrupt",))

    monkeypatch.setattr("newsroom.story_automation.verify_automatic_promotion", fail_verification)
    result = service.handle(claimed)

    assert result["stage_status"] == STAGE_TERMINAL
    assert result["reason_code"] == "corrupt"
    completed = queue.complete(job["id"], "worker", "succeeded", now=T1, outcome=result)
    assert completed["status"] == "succeeded"
    assert completed["result"]["stage_status"] == STAGE_TERMINAL


def test_transient_database_failure_uses_existing_retryable_job_path(tmp_db, monkeypatch):
    promotion_id, _ = _promotion(tmp_db)
    job = _stage_job(tmp_db, promotion_id)
    queue = JobService(tmp_db)
    claimed = queue.claim(job["id"], "worker", now=T0)
    service = AutomaticStoryStageExecutionService(tmp_db)

    def transient(*_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    # Keep the test at the worker boundary: a transient verifier failure is
    # surfaced to WorkerProcess as RetryableJobFailure by the service.
    monkeypatch.setattr("newsroom.story_automation.verify_automatic_promotion", transient)
    with pytest.raises(RetryableJobFailure):
        service.handle(claimed)
    retried = queue.complete(
        job["id"],
        "worker",
        "failed",
        error_code="retryable_handler_failure",
        retryable=True,
        now=T1,
    )

    assert retried["status"] == "queued"
    assert retried["result"] is None
