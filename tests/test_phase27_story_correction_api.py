from __future__ import annotations

from fastapi.testclient import TestClient

from newsroom.app import create_app
from newsroom.config import RuntimeConfig


PASSWORD = "a-long-test-password-12345"


def _client(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 200
    return client, {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}


def test_story_correction_api_exposes_controlled_workflows(tmp_path):
    client, headers = _client(tmp_path)
    first = client.post("/api/v1/stories", json={"headline": "First"}, headers=headers).json()
    second = client.post("/api/v1/stories", json={"headline": "Second"}, headers=headers).json()
    claim = client.post(
        f"/api/v1/stories/{first['id']}/claims",
        json={"proposition": "A claim to move"},
        headers=headers,
    ).json()

    moved = client.post(
        f"/api/v1/claims/{claim['id']}/reassign",
        json={"story_id": second["id"], "expected_from_story_id": first["id"], "reason": "API correction"},
        headers=headers,
    )
    assert moved.status_code == 200
    assert moved.json()["claim"]["story_id"] == second["id"]
    history = client.get(f"/api/v1/stories/{second['id']}/corrections")
    assert history.status_code == 200
    assert history.json()["items"][0]["operation_type"] == "reassign"

    preview = client.post(
        f"/api/v1/stories/{second['id']}/merge-preview",
        json={"destination_story_id": first["id"]},
    )
    assert preview.status_code == 200
    merged = client.post(
        f"/api/v1/stories/{second['id']}/merge",
        json={"destination_story_id": first["id"], "expected_source_updated_at": preview.json()["source"]["updated_at"], "reason": "duplicate"},
        headers=headers,
    )
    assert merged.status_code == 200
    assert merged.json()["source"]["lifecycle"] == "archived"

    split_source = client.post("/api/v1/stories", json={"headline": "Combined"}, headers=headers).json()
    claims = [
        client.post(
            f"/api/v1/stories/{split_source['id']}/claims",
            json={"proposition": proposition},
            headers=headers,
        ).json()
        for proposition in ("Development A", "Development B")
    ]
    split_preview = client.get(f"/api/v1/stories/{split_source['id']}/split-preview")
    assert split_preview.status_code == 200
    split = client.post(
        f"/api/v1/stories/{split_source['id']}/split",
        json={
            "groups": [[claims[0]["id"]], [claims[1]["id"]]],
            "expected_claim_ids": split_preview.json()["expected_claim_ids"],
            "expected_source_updated_at": split_preview.json()["source"]["updated_at"],
            "reason": "separate developments",
        },
        headers=headers,
    )
    assert split.status_code == 200
    assert split.json()["source"]["lifecycle"] == "archived"
    lineage = client.get(f"/api/v1/stories/{split_source['id']}/lineage")
    assert lineage.status_code == 200
    assert len(lineage.json()["outgoing"]) == 2


def test_story_correction_previews_name_affected_records_without_mutating(tmp_path):
    client, headers = _client(tmp_path)
    source = client.post("/api/v1/stories", json={"headline": "Source story"}, headers=headers).json()
    destination = client.post("/api/v1/stories", json={"headline": "Destination story"}, headers=headers).json()
    source_claim = client.post(
        f"/api/v1/stories/{source['id']}/claims",
        json={"proposition": "Source development"},
        headers=headers,
    ).json()
    destination_claim = client.post(
        f"/api/v1/stories/{destination['id']}/claims",
        json={"proposition": "Destination development"},
        headers=headers,
    ).json()

    merge_preview = client.post(
        f"/api/v1/stories/{source['id']}/merge-preview",
        json={"destination_story_id": destination["id"]},
    )
    assert merge_preview.status_code == 200, merge_preview.text
    merge_payload = merge_preview.json()
    assert merge_payload["source"]["headline"] == "Source story"
    assert merge_payload["destination"]["headline"] == "Destination story"
    assert merge_payload["source_claims"] == [
        {"id": source_claim["id"], "proposition": "Source development", "importance": "relevant", "state": "pending"}
    ]
    assert merge_payload["destination_claims"] == [
        {"id": destination_claim["id"], "proposition": "Destination development", "importance": "relevant", "state": "pending"}
    ]

    split_preview = client.get(f"/api/v1/stories/{source['id']}/split-preview")
    assert split_preview.status_code == 200
    assert split_preview.json()["claims"][0]["proposition"] == "Source development"

    history = client.get(f"/api/v1/stories/{source['id']}/corrections")
    assert history.status_code == 200
    assert history.json()["items"] == []
    assert client.get(f"/api/v1/stories/{source['id']}").json()["lifecycle"] == "developing"
    assert client.get(f"/api/v1/stories/{source['id']}/claims").json()["items"][0]["story_id"] == source["id"]
