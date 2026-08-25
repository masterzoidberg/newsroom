from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.domain import CoreService, DomainConflict
from newsroom.evidence import EvidenceService
from newsroom.migrations import apply_migrations
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.evals.corpus import load_case
from newsroom.evals.replay import load_fixture
from newsroom.story_evolution import (
    StoryCandidate,
    StoryEvolutionService,
    classify_update,
    replay_evolution,
    resolve_candidate,
)


def _candidate(identifier: str, headline: str, **overrides) -> StoryCandidate:
    values = {
        "id": identifier,
        "headline": headline,
        "canonical_url": f"https://{identifier}.test/story",
        "published_at": "2026-08-16T12:00:00Z",
        "event_key": "acme-office-opening",
        "entities": frozenset({"Acme"}),
        "locations": frozenset({"Berlin"}),
    }
    values.update(overrides)
    return StoryCandidate(**values)


def test_resolver_merges_exact_document_identity_but_keeps_distinct_events_separate():
    exact = resolve_candidate(
        _candidate("incoming", "Different headline", canonical_url="https://a.test/story"),
        [_candidate("story-1", "Original headline", canonical_url="https://a.test/story")],
    )
    assert exact.action == "merge"
    assert exact.classification == "duplicate"
    assert exact.via == "url_identity"

    distinct = resolve_candidate(
        _candidate(
            "incoming",
            "Acme opens a Tokyo office",
            canonical_url="https://b.test/story",
            event_key="acme-office-opening",
            locations=frozenset({"Tokyo"}),
        ),
        [
            _candidate(
                "story-1",
                "Acme opens a Berlin office",
                locations=frozenset({"Berlin"}),
            )
        ],
    )
    assert distinct.action == "new"
    assert distinct.ambiguous is True
    assert distinct.adjudicated is False


def test_ambiguous_candidate_uses_adjudication_only_after_deterministic_signals():
    calls = []

    def adjudicator(candidate, existing, signals):
        calls.append((candidate.id, existing.id, signals["location_overlap"]))
        return {"merge": True, "confidence": 0.91}

    result = resolve_candidate(
        _candidate("incoming", "Acme office opening update"),
        [
            _candidate("story-1", "Acme office opening announcement"),
            _candidate("story-2", "Acme office opening announcement"),
        ],
        adjudicator=adjudicator,
    )
    assert result.action == "merge"
    assert result.adjudicated is True
    assert calls == [("incoming", "story-1", 1.0)]


def test_update_classifier_distinguishes_repetition_corroboration_correction_and_material_change():
    prior = [{"proposition": "Acme revenue was $1.2 billion."}]
    same = [{"proposition": "Acme revenue was $1.2 billion."}]
    assert classify_update(prior, same, same_lineage=True) == "duplicate"
    assert classify_update(prior, same, same_lineage=False) == "corroboration"

    correction = [{"proposition": "Acme corrected revenue to $1.1 billion."}]
    assert classify_update(prior, correction, incoming_text="official correction") == "correction"

    changed = [{"proposition": "Acme revenue was $2.4 billion."}]
    assert classify_update(prior, changed) == "material_update"


def test_exact_identity_resolution_is_deterministic_across_candidate_order():
    incoming = {
        "id": "incoming",
        "headline": "Acme release",
        "canonical_url": "https://example.test/releases/acme",
    }
    candidates = [
        {
            "id": "story-z",
            "headline": "Acme release",
            "canonical_url": "https://example.test/releases/acme",
        },
        {
            "id": "story-a",
            "headline": "Acme release",
            "canonical_url": "https://example.test/releases/acme",
        },
    ]

    forward = resolve_candidate(incoming, candidates)
    reversed_result = resolve_candidate(incoming, list(reversed(candidates)))

    assert forward.story_id == reversed_result.story_id == "story-a"
    assert forward.via == reversed_result.via == "url_identity"


def test_frozen_evolution_corpus_has_no_false_merges_or_false_splits():
    root = Path(__file__).resolve().parents[1]
    for fixture_path in sorted((root / "evals" / "fixtures").glob("*.json")):
        fixture = load_fixture(fixture_path)
        result = replay_evolution(
            [
                StoryCandidate(
                    id=document.candidate_id,
                    headline=document.title,
                    text=document.excerpt or "",
                    canonical_url=document.canonical_url,
                    published_at=document.published_at,
                    event_key=document.event_key,
                )
                for document in fixture.documents
            ]
        )
        predicted_pairs = {
            tuple(sorted((left, right)))
            for group in result["story_groups"]
            for index, left in enumerate(group["candidate_ids"])
            for right in group["candidate_ids"][index + 1 :]
        }
        case = load_case(fixture.case_id)
        gold_pairs = {
            tuple(sorted((left, right)))
            for group in case.gold_groups
            for index, left in enumerate(group.candidate_ids)
            for right in group.candidate_ids[index + 1 :]
        }
        assert predicted_pairs - gold_pairs == set(), fixture.case_id
        assert gold_pairs - predicted_pairs == set(), fixture.case_id


def test_evolution_records_lineage_independent_corroboration_and_review_attention(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    first_source = core.create_source({"name": "Primary", "slug": "primary"})
    second_source = core.create_source({"name": "Outlet", "slug": "outlet"})
    first_doc = core.create_document(
        {
            "source_id": first_source["id"],
            "canonical_url": "https://primary.test/release",
            "title": "Acme release",
        }
    )
    second_doc = core.create_document(
        {
            "source_id": second_source["id"],
            "canonical_url": "https://outlet.test/release",
            "title": "Acme release reported",
        }
    )
    story = core.create_story({"headline": "Acme release"})
    evolution = StoryEvolutionService(tmp_db)

    evolution.record_observation(
        story["id"],
        first_doc["id"],
        "material_update",
        candidate={"event_key": "acme-release", "entities": ["Acme"], "locations": []},
    )
    evolution.record_observation(
        story["id"],
        second_doc["id"],
        "corroboration",
        candidate={"event_key": "acme-release", "entities": ["Acme"], "locations": []},
    )
    assert evolution.corroboration(story["id"])["publication_count"] == 2
    assert evolution.corroboration(story["id"])["dependency_group_count"] == 2
    assert evolution.corroboration(story["id"])["lineage_group_count"] == 2

    evolution.link_lineage(
        second_doc["id"], first_doc["id"], "syndicated_from", rationale="wire copy"
    )
    assert evolution.corroboration(story["id"])["dependency_group_count"] == 1

    review = evolution.review(story["id"], "saved", story["current_revision"]["id"])
    assert review["review_status"] == "saved"
    assert review["new_update"] is False

    ledger = EvidenceService(tmp_db)
    version = ledger.create_document_version(
        first_doc["id"],
        {"content_hash": "revision-content", "content_kind": "excerpt"},
    )
    span = ledger.create_evidence_span(
        version["id"], {"excerpt": "Acme released the Atlas product."}
    )
    claim = ledger.create_claim(
        story["id"], {"proposition": "Acme released the Atlas product.", "importance": "major"}
    )
    ledger.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"}
    )
    ledger.set_claim_state(claim["id"], "supported")
    ledger.accept_claim(claim["id"])
    revision = ledger.create_story_revision(
        story["id"],
        {
            "headline": "Acme released Atlas",
            "claim_ids": [claim["id"]],
            "propositions": [{"text": "Acme released Atlas", "claim_ids": [claim["id"]]}],
            "material_change": True,
        },
    )["revision"]
    assert evolution.review(story["id"], "saved", story["current_revision"]["id"])["new_update"] is True
    assert evolution.review(story["id"], "saved", revision["id"])["new_update"] is False

    with pytest.raises(DomainConflict):
        evolution.link_lineage(second_doc["id"], first_doc["id"], "syndicated_from")

    timeline = evolution.timeline(story["id"])
    assert timeline["events"]
    assert timeline["events"][0]["document_id"] in {first_doc["id"], second_doc["id"]}
    conn = storage.connect(tmp_db)
    try:
        with pytest.raises(Exception):
            conn.execute(
                "UPDATE story_evolution_events SET update_class = 'duplicate' WHERE story_id = ?",
                (story["id"],),
            )
    finally:
        conn.close()


def test_story_evolution_api_exposes_process_timeline_lineage_and_review(tmp_path):
    client = TestClient(
        create_app(
            config=RuntimeConfig.for_environment("dev", root=tmp_path / "dev"),
            frontend_dist=tmp_path / "missing-dist",
        )
    )
    password = "a-long-test-password-12345"
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": password}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": password}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    source = client.post("/api/v1/sources", headers=headers, json={"name": "Phase 09", "slug": "phase-09"}).json()
    first = client.post(
        "/api/v1/documents",
        headers=headers,
        json={"source_id": source["id"], "canonical_url": "https://phase09.test/one", "title": "Acme release"},
    ).json()
    second = client.post(
        "/api/v1/documents",
        headers=headers,
        json={"source_id": source["id"], "canonical_url": "https://phase09.test/two", "title": "Acme release update"},
    ).json()
    created = client.post(
        "/api/v1/story-evolution/process",
        headers=headers,
        json={
            "id": "candidate-one",
            "document_id": first["id"],
            "headline": "Acme release",
            "event_key": "acme-release",
            "text": "Acme released Atlas.",
        },
    )
    assert created.status_code == 201, created.text
    story_id = created.json()["story"]["id"]
    updated = client.post(
        "/api/v1/story-evolution/process",
        headers=headers,
        json={
            "id": "candidate-two",
            "document_id": second["id"],
            "story_id": story_id,
            "headline": "Acme release update",
            "event_key": "acme-release",
            "text": "Acme released Atlas.",
        },
    )
    assert updated.status_code == 201, updated.text
    assert client.post(
        f"/api/v1/documents/{second['id']}/lineage",
        headers=headers,
        json={"parent_document_id": first["id"], "relationship": "syndicated_from"},
    ).status_code == 201
    timeline = client.get(f"/api/v1/stories/{story_id}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.json()["events"]) == 2
    review = client.post(
        f"/api/v1/stories/{story_id}/review",
        headers=headers,
        json={"review_status": "saved"},
    )
    assert review.status_code == 200
    assert review.json()["new_update"] is False
