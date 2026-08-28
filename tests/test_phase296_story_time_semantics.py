from __future__ import annotations

from newsroom import storage
from newsroom.automatic_story_resolution import (
    MATCHED_EXISTING,
    AutomaticStoryResolutionService,
)
from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.evidence_promotion import verify_automatic_promotion
from newsroom.jobs import JobService
from newsroom.migrations import apply_migrations
from newsroom.story_automation import (
    AutomaticStoryStageExecutionService,
    enqueue_story_stage,
)
from newsroom.story_context import current_story_documents
from newsroom.story_evolution import StoryEvolutionService

from test_phase23b_story_automation import T0, _variant_promotion


STORY_PROCESSED_AT = "2026-08-28T12:00:00Z"
FIRST_RETRIEVED_AT = "2026-08-20T12:00:00Z"
SECOND_RETRIEVED_AT = "2026-08-24T12:00:00Z"
PUBLISHED_AT = "2026-05-01T12:00:00Z"


def _run_story_stage(db, promotion_id: str, worker: str):
    job = enqueue_story_stage(db, promotion_id)
    queue = JobService(db)
    claimed = queue.claim(job["id"], worker, now=T0)
    return AutomaticStoryStageExecutionService(db).handle(claimed)


def _set_story_created_at(db, story_id: str, timestamp: str) -> None:
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE stories SET created_at = ?, updated_at = ? WHERE id = ?",
                (timestamp, timestamp, story_id),
            )
    finally:
        conn.close()


def _set_document_published_at(db, document_id: str, published_at: str) -> None:
    conn = storage.connect(db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                "UPDATE documents SET published_at = ? WHERE id = ?",
                (published_at, document_id),
            )
    finally:
        conn.close()


def test_story_processing_delay_does_not_break_source_time_matching(tmp_db):
    first_promotion, _ = _variant_promotion(
        tmp_db,
        "phase296-delay-first",
        proposition="The agency released a UAP report",
    )
    second_promotion, _ = _variant_promotion(
        tmp_db,
        "phase296-delay-second",
        proposition="The agency released a UAP report",
    )

    first = _run_story_stage(tmp_db, first_promotion, "phase296-first-worker")
    _set_story_created_at(tmp_db, first["story_id"], STORY_PROCESSED_AT)

    second = _run_story_stage(tmp_db, second_promotion, "phase296-second-worker")

    assert second["story_resolution"] == MATCHED_EXISTING
    assert second["story_id"] == first["story_id"]
    signal = next(
        item for item in second["match_signals"] if item["story_id"] == first["story_id"]
    )
    assert signal["signals"]["claim_exact_match"] is True
    assert signal["signals"]["time_compatible"] is True


def test_multiple_versions_use_first_retrieval_without_duplicate_story_documents(tmp_db):
    apply_migrations(tmp_db)
    proposition = "The agency released a UAP report"
    core = CoreService(tmp_db)
    source = core.create_source(
        {"name": "Phase 29.6 source", "slug": "phase296-source"}
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://phase296.example.test/report",
            "title": proposition,
        }
    )
    evidence = EvidenceService(tmp_db)
    first_version = evidence.create_document_version(
        document["id"],
        {
            "retrieved_at": FIRST_RETRIEVED_AT,
            "content_hash": "phase296-version-one",
            "content_kind": "full_text",
            "normalized_json": "{}",
        },
    )
    second_version = evidence.create_document_version(
        document["id"],
        {
            "retrieved_at": SECOND_RETRIEVED_AT,
            "content_hash": "phase296-version-two",
            "content_kind": "full_text",
            "normalized_json": "{}",
        },
    )
    story = core.create_story({"headline": proposition})
    _set_story_created_at(tmp_db, story["id"], STORY_PROCESSED_AT)
    claim = evidence.create_claim(story["id"], {"proposition": proposition})
    for version in (first_version, second_version):
        span = evidence.create_evidence_span(
            version["id"], {"excerpt": proposition}
        )
        evidence.link_claim_evidence(
            claim["id"],
            {"evidence_span_id": span["id"], "relationship": "supports"},
        )

    second_promotion, _ = _variant_promotion(
        tmp_db,
        "phase296-versions-incoming",
        proposition=proposition,
    )
    resolver = AutomaticStoryResolutionService(tmp_db)
    resolution = resolver.resolve(second_promotion)

    assert resolution.story_resolution == MATCHED_EXISTING
    assert resolution.selected_story_id == story["id"]
    candidate = resolver._retrieve_candidates(
        resolver._incoming_candidate(verify_automatic_promotion(tmp_db, second_promotion))
    ).candidates
    assert len(candidate) == 1
    assert candidate[0].published_at == FIRST_RETRIEVED_AT

    conn = storage.connect(tmp_db)
    try:
        documents = current_story_documents(conn, story["id"])
    finally:
        conn.close()
    assert len(documents) == 1
    assert documents[0]["retrieved_at"] == SECOND_RETRIEVED_AT
    assert documents[0]["first_retrieved_at"] == FIRST_RETRIEVED_AT
    evolution_conn = storage.connect(tmp_db)
    try:
        candidates = StoryEvolutionService(tmp_db)._story_candidates(evolution_conn)
    finally:
        evolution_conn.close()
    assert len(candidates) == 1
    assert candidates[0].published_at == FIRST_RETRIEVED_AT


def test_published_at_precedes_first_retrieval_for_story_time(tmp_db):
    first_promotion, _ = _variant_promotion(
        tmp_db,
        "phase296-publication-first",
        proposition="The agency released a UAP report",
    )
    first_graph = verify_automatic_promotion(tmp_db, first_promotion)
    _set_document_published_at(tmp_db, first_graph["document"]["id"], PUBLISHED_AT)
    first = _run_story_stage(tmp_db, first_promotion, "phase296-publication-first-worker")

    second_promotion, _ = _variant_promotion(
        tmp_db,
        "phase296-publication-incoming",
        proposition="The agency released a UAP report",
    )
    second_graph = verify_automatic_promotion(tmp_db, second_promotion)
    _set_document_published_at(tmp_db, second_graph["document"]["id"], PUBLISHED_AT)

    resolver = AutomaticStoryResolutionService(tmp_db)
    resolution = resolver.resolve(second_promotion)
    candidates = resolver._retrieve_candidates(
        resolver._incoming_candidate(verify_automatic_promotion(tmp_db, second_promotion))
    ).candidates

    assert resolution.story_resolution == MATCHED_EXISTING
    assert resolution.selected_story_id == first["story_id"]
    assert len(candidates) == 1
    assert candidates[0].published_at == PUBLISHED_AT
