from __future__ import annotations

import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainValidation
from newsroom import storage


PASSWORD = "a-long-test-password-12345"


def _authenticated_client(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": PASSWORD},
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": PASSWORD},
    ).status_code == 200
    return client


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}


def _manual_fixture(client: TestClient, *, with_revision: bool = True):
    payload = {
        "source": {
            "name": "Fixture Gazette",
            "slug": "fixture-gazette",
            "homepage_url": "https://fixture.test",
            "source_kind": "official",
            "default_quality": "primary",
        },
        "document": {
            "canonical_url": "https://fixture.test/events/launch",
            "title": "Fixture launch announcement",
        },
        "document_version": {
            "retrieved_at": "2026-08-16T12:00:00Z",
            "content_hash": "fixture-content-v1",
            "content_kind": "excerpt",
            "normalized_json": {"fixture": "launch-v1"},
        },
        "story": {"headline": "Fixture launch"},
        "claims": [
            {
                "proposition": "Acme launched the Atlas product",
                "importance": "major",
                "evidence": [
                    {
                        "excerpt": "Acme launched the Atlas product on August 16.",
                        "locator_type": "paragraph",
                        "locator_value": "p1",
                        "relationship": "supports",
                    }
                ],
                "state": "supported",
                "accept": True,
            },
            {
                "proposition": "The launch date was August 17",
                "importance": "relevant",
                "evidence": [
                    {
                        "excerpt": "A later correction says the launch date was August 17.",
                        "locator_type": "paragraph",
                        "locator_value": "p2",
                        "relationship": "contradicts",
                    }
                ],
                "state": "disputed",
                "accept": False,
            },
        ],
    }
    if with_revision:
        payload["revision"] = {
            "headline": "Acme launched Atlas",
            "summary": "Acme launched the Atlas product.",
            "why_it_matters": "The launch establishes a new product milestone.",
            "material_change": True,
            "claim_indexes": [0],
            "propositions": [
                {"text": "Acme launched the Atlas product.", "claim_indexes": [0]}
            ],
        }
    response = client.post("/api/v1/runs/manual", json=payload, headers=_csrf(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_manual_run_persists_complete_evidence_chain_and_survives_restart(tmp_path):
    client = _authenticated_client(tmp_path)
    result = _manual_fixture(client)

    assert result["source"]["slug"] == "fixture-gazette"
    assert result["document"]["canonical_url"] == "https://fixture.test/events/launch"
    assert result["document_version"]["content_hash"] == "fixture-content-v1"
    assert len(result["claims"]) == 2
    assert result["claims"][0]["accepted_at"] is not None
    assert result["claims"][1]["state"] == "disputed"
    assert result["revision"]["audit"]["passed"] is True

    claim_ids = [claim["id"] for claim in result["claims"]]
    expected_hash = hashlib.sha256("\n".join(sorted([claim_ids[0]])).encode()).hexdigest()
    assert result["revision"]["claim_set_hash"] == expected_hash
    assert result["revision"]["claim_ids"] == [claim_ids[0]]

    evidence = client.get(
        f"/api/v1/stories/{result['story']['id']}/evidence"
    )
    assert evidence.status_code == 200
    body = evidence.json()
    assert body["claims"][0]["evidence"][0]["document_version"]["id"] == result["document_version"]["id"]
    assert body["claims"][0]["evidence"][0]["source"]["name"] == "Fixture Gazette"
    assert body["revisions"][0]["claim_ids"] == [claim_ids[0]]

    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    restarted = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert restarted.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": PASSWORD},
    ).status_code == 200
    after_restart = restarted.get(
        f"/api/v1/stories/{result['story']['id']}/evidence"
    )
    assert after_restart.status_code == 200
    assert after_restart.json()["revisions"][0]["claim_set_hash"] == expected_hash


def test_contradiction_unsubstantiated_history_and_supersession_are_distinct(tmp_path):
    client = _authenticated_client(tmp_path)
    result = _manual_fixture(client, with_revision=False)
    headers = _csrf(client)
    story_id = result["story"]["id"]
    claim = result["claims"][0]

    state = client.post(
        f"/api/v1/claims/{claim['id']}/state",
        json={"state": "unsubstantiated", "reason": "support removed for review"},
        headers=headers,
    )
    assert state.status_code == 200
    assert state.json()["state"] == "unsubstantiated"
    assert state.json()["evidence"][0]["relationship"] == "supports"

    correction = client.post(
        f"/api/v1/stories/{story_id}/claims",
        json={
            "proposition": "Acme launched the Atlas product on August 16",
            "importance": "major",
            "supersedes_claim_id": claim["id"],
        },
        headers=headers,
    )
    assert correction.status_code == 201
    assert correction.json()["supersedes_claim_id"] == claim["id"]
    old = client.get(f"/api/v1/claims/{claim['id']}")
    assert old.status_code == 200
    assert old.json()["state"] == "superseded"
    assert old.json()["proposition"] == claim["proposition"]
    assert old.json()["state_history"][-1]["to_state"] == "superseded"

    evidence = client.get(f"/api/v1/stories/{story_id}/evidence")
    assert evidence.status_code == 200
    claims = {item["id"]: item for item in evidence.json()["claims"]}
    assert claims[claim["id"]]["state"] == "superseded"
    assert any(
        evidence["relationship"] == "contradicts"
        for item in claims.values()
        for evidence in item["evidence"]
    )


def test_closed_world_audit_rejects_pending_claims_and_unknown_citations(tmp_path):
    client = _authenticated_client(tmp_path)
    result = _manual_fixture(client, with_revision=False)
    headers = _csrf(client)
    story_id = result["story"]["id"]
    pending = client.post(
        f"/api/v1/stories/{story_id}/claims",
        json={"proposition": "A pending proposition"},
        headers=headers,
    ).json()
    accepted = result["claims"][0]

    unsupported = client.post(
        f"/api/v1/stories/{story_id}/revisions",
        json={
            "headline": "Unsupported revision",
            "claim_ids": [pending["id"]],
            "propositions": [
                {"text": "A pending proposition", "claim_ids": [pending["id"]]}
            ],
        },
        headers=headers,
    )
    assert unsupported.status_code == 422
    assert "accepted" in unsupported.json()["error"]["message"]

    unknown_citation = client.post(
        f"/api/v1/stories/{story_id}/revisions",
        json={
            "headline": "Unknown citation revision",
            "claim_ids": [accepted["id"]],
            "propositions": [
                {"text": "A fact without a known citation", "claim_ids": ["missing-claim"]}
            ],
        },
        headers=headers,
    )
    assert unknown_citation.status_code == 422
    assert "audit" in unknown_citation.json()["error"]["message"]

    revisions = client.get(f"/api/v1/stories/{story_id}/evidence").json()["revisions"]
    assert len(revisions) == 1
    db_path = RuntimeConfig.for_environment("dev", root=tmp_path / "dev").database_path
    with pytest.raises(DomainValidation, match="accepted Claims"):
        CoreService(db_path).create_story_revision(
            story_id,
            {
                "headline": "Bypass attempt",
                "claim_ids": [pending["id"]],
                "propositions": [{"text": "A pending proposition", "claim_ids": [pending["id"]]}],
            },
        )


def test_sqlite_guards_keep_frozen_versions_evidence_and_accepted_claim_text_immutable(tmp_path):
    client = _authenticated_client(tmp_path)
    result = _manual_fixture(client)
    db_path = RuntimeConfig.for_environment("dev", root=tmp_path / "dev").database_path
    span_id = result["claims"][0]["evidence"][0]["evidence_span_id"]
    claim_id = result["claims"][0]["id"]
    version_id = result["document_version"]["id"]
    conn = storage.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="document versions are immutable"):
            conn.execute(
                "UPDATE document_versions SET content_hash = 'changed' WHERE id = ?",
                (version_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="evidence spans are immutable"):
            conn.execute(
                "UPDATE evidence_spans SET excerpt = 'changed' WHERE id = ?",
                (span_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="accepted claim text is immutable"):
            conn.execute(
                "UPDATE claims SET proposition = 'changed' WHERE id = ?",
                (claim_id,),
            )
    finally:
        conn.close()
