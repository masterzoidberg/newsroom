from __future__ import annotations

import json

import pytest

from newsroom import storage
from newsroom.automatic_story_resolution import (
    MAX_CANDIDATE_STORIES,
    MAX_STORY_CLAIMS,
    AutomaticStoryResolutionService,
    MATCHED_EXISTING,
    NO_MATCH,
    QUALIFIED,
    DEFERRED,
    AMBIGUOUS,
    match_story_candidates,
)
from newsroom.domain import CoreService
from newsroom.evidence import EvidenceService
from newsroom.evidence_promotion import ArticleAnalysisPromotionService
from newsroom.story_evolution import StoryCandidate

from test_phase22_evidence_promotion import _analysis


def _promotion(db, *, proposition: str = "The agency released a UAP report.") -> tuple[str, str]:
    analysis = _analysis(
        db,
        text=proposition,
        excerpt=proposition,
        proposition=proposition,
    )
    outcome = ArticleAnalysisPromotionService(db).promote(analysis["id"])["outcomes"][0]
    return outcome["id"], outcome["claim_id"]


def _story_with_claim(
    db,
    proposition: str,
    *,
    headline: str | None = None,
    lifecycle: str = "developing",
):
    story = CoreService(db).create_story(
        {"headline": headline or proposition, "lifecycle": lifecycle}
    )
    claim = EvidenceService(db).create_claim(
        story["id"], {"proposition": proposition}
    )
    return story, claim


def test_legitimate_verified_pending_automatic_claim_qualifies_and_matches_without_mutation(tmp_db):
    promotion_id, claim_id = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report.")
    before = CoreService(tmp_db).get_story(story["id"], include_deleted=True)

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.qualification == QUALIFIED
    assert result.story_resolution == MATCHED_EXISTING
    assert result.claim_id == claim_id
    assert result.selected_story_id == story["id"]
    assert result.candidate_story_ids == (story["id"],)
    assert result.qualification_reason_code == "verified_pending_automatic_claim"
    assert CoreService(tmp_db).get_story(story["id"], include_deleted=True) == before
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT story_id FROM claims WHERE id = ?", (claim_id,)).fetchone()[0] is None
        assert conn.execute("SELECT COUNT(*) FROM claim_story_assignment_history").fetchone()[0] == 0
    finally:
        conn.close()


def test_unverifiable_promotion_fails_before_qualification(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER evidence_spans_immutable_update")
            conn.execute(
                "UPDATE evidence_spans SET view_content_hash = 'corrupt'"
            )
    finally:
        conn.close()

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.qualification == DEFERRED
    assert result.story_resolution == DEFERRED
    assert result.qualification_reason_code == "promotion_verification_failed"
    assert result.candidate_story_ids == ()


def test_manual_claim_cannot_enter_automatic_promotion_path(tmp_db):
    _promotion(tmp_db)
    story, manual_claim = _story_with_claim(tmp_db, "A manually entered proposition.")

    result = AutomaticStoryResolutionService(tmp_db).resolve(manual_claim["id"])

    assert result.qualification == DEFERRED
    assert result.story_resolution == DEFERRED
    assert result.claim_id is None
    assert result.qualification_reason_code == "promotion_verification_failed"
    assert CoreService(tmp_db).get_story(story["id"], include_deleted=True)["id"] == story["id"]


def test_missing_candidate_data_fails_closed(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        analysis_id = conn.execute(
            "SELECT article_analysis_id FROM article_analysis_promotions WHERE id = ?",
            (promotion_id,),
        ).fetchone()[0]
        with storage.write_tx(conn):
            conn.execute("DROP TRIGGER article_analyses_immutable_update")
            conn.execute(
                "UPDATE article_analyses SET result_json = ? WHERE id = ?",
                (
                    json.dumps(
                        {
                            "summary": "Missing candidate",
                            "key_developments": ["Missing candidate"],
                            "entities": [],
                            "dates": [],
                            "locations": [],
                            "significance": "Missing candidate",
                            "novelty": "Missing candidate",
                            "candidate_claims": [],
                            "candidate_evidence_excerpts": [],
                            "confidence": 0.9,
                        }
                    ),
                    analysis_id,
                ),
            )
    finally:
        conn.close()

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.qualification == DEFERRED
    assert result.story_resolution == DEFERRED
    assert result.qualification_reason_code == "promotion_verification_failed"


def test_qualification_is_deterministic_on_replay(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report.")
    service = AutomaticStoryResolutionService(tmp_db)

    first = service.resolve(promotion_id)
    second = service.resolve(promotion_id)

    assert first == second
    assert first.selected_story_id == story["id"]


@pytest.mark.parametrize("lifecycle", ["archived"])
def test_archived_strong_match_is_excluded_and_returns_no_match(tmp_db, lifecycle):
    promotion_id, _ = _promotion(tmp_db)
    story, _ = _story_with_claim(
        tmp_db, "The agency released a UAP report.", lifecycle=lifecycle
    )

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.qualification == QUALIFIED
    assert result.story_resolution == NO_MATCH
    assert result.selected_story_id is None
    assert story["id"] not in result.candidate_story_ids


def test_deleted_strong_match_is_excluded(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report.")
    CoreService(tmp_db).delete_story(story["id"])

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.story_resolution == NO_MATCH
    assert story["id"] not in result.candidate_story_ids


def test_retrieval_is_bounded_with_many_unrelated_stories(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    core = CoreService(tmp_db)
    for index in range(MAX_CANDIDATE_STORIES * 5):
        core.create_story({"headline": f"Unrelated event {index}"})

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.story_resolution == NO_MATCH
    assert len(result.candidate_story_ids) <= MAX_CANDIDATE_STORIES
    assert result.candidate_saturated is False


def test_relevant_active_story_enters_candidate_set(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report.")

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert story["id"] in result.candidate_story_ids
    assert result.story_resolution == MATCHED_EXISTING


def test_broad_topic_overlap_alone_does_not_match(tmp_db):
    proposition = "Artificial intelligence is important."
    promotion_id, _ = _promotion(tmp_db, proposition=proposition)
    story, _ = _story_with_claim(
        tmp_db,
        "Artificial intelligence changes society.",
        headline="Artificial intelligence developments",
    )

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert story["id"] in result.candidate_story_ids
    assert result.story_resolution == NO_MATCH
    assert result.selected_story_id is None


def test_same_source_alone_does_not_force_a_match(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story, _ = _story_with_claim(
        tmp_db,
        "The agency released a weather report.",
        headline="Agency releases weather report",
    )

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert story["id"] in result.candidate_story_ids
    assert result.story_resolution == NO_MATCH


def test_generic_term_overlap_alone_does_not_force_a_match(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story, _ = _story_with_claim(
        tmp_db,
        "The agency released a weather report.",
        headline="Weather report",
    )

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert story["id"] in result.candidate_story_ids
    assert result.story_resolution == NO_MATCH


def test_strong_proposition_overlap_matches_exactly_one_story(tmp_db):
    incoming = StoryCandidate(
        id="incoming",
        headline="Acme launched Atlas",
        text="Acme launched Atlas product.",
        claim_keys=frozenset({"Acme launched Atlas product."}),
        entities=frozenset({"Acme"}),
    )
    existing = StoryCandidate(
        id="story-1",
        headline="Acme launches Atlas",
        text="Acme launched Atlas product.",
        claim_keys=frozenset({"Acme launched Atlas product."}),
        entities=frozenset({"Acme"}),
    )

    result = match_story_candidates(incoming, [existing])

    assert result.story_resolution == MATCHED_EXISTING
    assert result.selected_story_id == "story-1"


def test_entity_backed_lexical_overlap_matches_one_story():
    incoming = StoryCandidate(
        id="incoming",
        headline="Acme approved Atlas",
        text="Acme approved Atlas.",
        entities=frozenset({"Acme"}),
    )
    existing = StoryCandidate(
        id="story-1",
        headline="Acme approves Atlas",
        text="Acme approves Atlas.",
        entities=frozenset({"Acme"}),
    )

    result = match_story_candidates(incoming, [existing])

    assert result.story_resolution == MATCHED_EXISTING
    assert result.selected_story_id == "story-1"


def test_two_plausible_stories_return_ambiguous(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    first, _ = _story_with_claim(tmp_db, "The agency released a UAP report.")
    second, _ = _story_with_claim(tmp_db, "The agency released a UAP report.")

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.qualification == QUALIFIED
    assert result.story_resolution == AMBIGUOUS
    assert result.selected_story_id is None
    assert set(result.candidate_story_ids) == {first["id"], second["id"]}


def test_ambiguous_result_is_order_independent():
    incoming = StoryCandidate(
        id="incoming",
        headline="Acme launches Atlas",
        text="Acme launched Atlas product.",
        claim_keys=frozenset({"Acme launched Atlas product."}),
        entities=frozenset({"Acme"}),
    )
    candidates = [
        StoryCandidate(
            id="story-a",
            headline="Acme launches Atlas",
            text="Acme launched Atlas product.",
            claim_keys=frozenset({"Acme launched Atlas product."}),
            entities=frozenset({"Acme"}),
        ),
        StoryCandidate(
            id="story-b",
            headline="Acme launches Atlas",
            text="Acme launched Atlas product.",
            claim_keys=frozenset({"Acme launched Atlas product."}),
            entities=frozenset({"Acme"}),
        ),
    ]

    forward = match_story_candidates(incoming, candidates)
    reversed_result = match_story_candidates(incoming, list(reversed(candidates)))

    assert forward == reversed_result
    assert forward.story_resolution == AMBIGUOUS
    assert forward.selected_story_id is None


def test_archived_strong_match_and_weaker_active_candidate_never_select_archived(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    archived, _ = _story_with_claim(
        tmp_db, "The agency released a UAP report.", lifecycle="archived"
    )
    active, _ = _story_with_claim(
        tmp_db,
        "The agency released a weather report.",
        headline="Weather report",
    )

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert archived["id"] not in result.candidate_story_ids
    assert result.story_resolution == NO_MATCH
    assert result.selected_story_id != archived["id"]
    assert active["id"] in result.candidate_story_ids


def test_candidate_saturation_defers_instead_of_creating_false_confidence(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    for _ in range(MAX_CANDIDATE_STORIES + 1):
        _story_with_claim(tmp_db, "The agency released a UAP report.")

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.qualification == QUALIFIED
    assert result.story_resolution == DEFERRED
    assert result.story_resolution_reason_code == "candidate_set_saturated"
    assert result.selected_story_id is None
    assert len(result.candidate_story_ids) == MAX_CANDIDATE_STORIES
    assert result.candidate_saturated is True


def test_associated_claim_bound_defers_instead_of_using_incomplete_story_data(tmp_db):
    promotion_id, _ = _promotion(tmp_db)
    story, _ = _story_with_claim(tmp_db, "The agency released a UAP report.")
    ledger = EvidenceService(tmp_db)
    for index in range(MAX_STORY_CLAIMS):
        ledger.create_claim(story["id"], {"proposition": f"Additional detail {index}."})

    result = AutomaticStoryResolutionService(tmp_db).resolve(promotion_id)

    assert result.story_resolution == DEFERRED
    assert result.story_resolution_reason_code == "candidate_data_saturated"
    assert result.selected_story_id is None
