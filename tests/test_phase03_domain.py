from __future__ import annotations

from fastapi.testclient import TestClient

from newsroom.app import create_app
from newsroom.config import RuntimeConfig


PASSWORD = "a-long-test-password-12345"


def _authenticated_client(tmp_path):
    root = tmp_path / "dev"
    config = RuntimeConfig.for_environment("dev", root=root)
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    setup = client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": PASSWORD},
    )
    assert setup.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": PASSWORD},
    )
    assert login.status_code == 200
    return client


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}


def test_core_mutations_require_authentication_and_csrf(tmp_path):
    root = tmp_path / "dev"
    config = RuntimeConfig.for_environment("dev", root=root)
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    unauthorized = client.post(
        "/api/v1/categories", json={"slug": "tech", "name": "Tech"}
    )
    assert unauthorized.status_code == 401

    client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": PASSWORD},
    )
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": PASSWORD},
    )
    missing_csrf = client.post(
        "/api/v1/categories", json={"slug": "tech", "name": "Tech"}
    )
    assert missing_csrf.status_code == 403
    assert client.get("/api/v1/categories").json()["total"] == 0


def test_categories_topics_pagination_stable_slug_and_soft_delete(tmp_path):
    client = _authenticated_client(tmp_path)
    headers = _csrf(client)
    for slug in ("alpha", "beta", "gamma"):
        response = client.post(
            "/api/v1/categories",
            json={"slug": slug, "name": slug.title()},
            headers=headers,
        )
        assert response.status_code == 201
    page = client.get("/api/v1/categories?page=2&page_size=2")
    assert page.status_code == 200
    assert page.json()["page"] == 2
    assert page.json()["page_size"] == 2
    assert page.json()["total"] == 3
    category_id = client.get("/api/v1/categories?slug=alpha").json()["items"][0]["id"]

    updated = client.patch(
        f"/api/v1/categories/{category_id}",
        json={"name": "Renamed Alpha"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["slug"] == "alpha"
    assert updated.json()["name"] == "Renamed Alpha"
    cleared = client.patch(
        f"/api/v1/categories/{category_id}",
        json={"max_stories_per_run": None},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["max_stories_per_run"] is None
    assert (
        client.patch(
            f"/api/v1/categories/{category_id}",
            json={"name": None},
            headers=headers,
        ).status_code
        == 422
    )
    deleted = client.delete(f"/api/v1/categories/{category_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/categories?slug=alpha").json()["total"] == 0
    assert (
        client.get("/api/v1/categories?slug=alpha&include_deleted=true").json()["total"]
        == 1
    )

    topic = client.post(
        "/api/v1/topics",
        json={"category_id": category_id, "slug": "alpha-topic", "name": "Alpha Topic"},
        headers=headers,
    )
    assert topic.status_code == 409  # deleted parent cannot receive new children


def test_vocabulary_scope_suggestions_require_explicit_approval(tmp_path):
    client = _authenticated_client(tmp_path)
    headers = _csrf(client)
    category = client.post(
        "/api/v1/categories", json={"slug": "research", "name": "Research"}, headers=headers
    ).json()
    topic = client.post(
        "/api/v1/topics",
        json={"category_id": category["id"], "slug": "ai", "name": "AI"},
        headers=headers,
    ).json()
    term = client.post(
        f"/api/v1/topics/{topic['id']}/vocabulary",
        json={"term": "Open AI", "term_type": "alias", "concept_kind": "acronym"},
        headers=headers,
    )
    assert term.status_code == 201
    suggestion = client.post(
        f"/api/v1/topics/{topic['id']}/scope-suggestions",
        json={
            "suggestion_type": "related_concept",
            "value": "machine learning",
            "rationale": "model proposal",
            "source": "ai",
        },
        headers=headers,
    )
    assert suggestion.status_code == 201
    assert suggestion.json()["status"] == "pending"
    assert client.get(f"/api/v1/topics/{topic['id']}/vocabulary").json()["total"] == 1
    approved = client.post(
        f"/api/v1/topics/{topic['id']}/scope-suggestions/{suggestion.json()['id']}/approve",
        headers=headers,
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    vocabulary = client.get(f"/api/v1/topics/{topic['id']}/vocabulary").json()
    assert vocabulary["total"] == 2
    assert any(item["concept_kind"] == "related_concept" for item in vocabulary["items"])
    removed = client.delete(
        f"/api/v1/topics/{topic['id']}/vocabulary/{term.json()['id']}", headers=headers
    )
    assert removed.status_code == 204


def test_subject_sources_documents_story_tags_and_settings(tmp_path):
    client = _authenticated_client(tmp_path)
    headers = _csrf(client)
    subject = client.post(
        "/api/v1/subjects",
        json={
            "canonical_name": "OpenAI",
            "subject_type": "company",
            "aliases": ["Open AI"],
        },
        headers=headers,
    )
    assert subject.status_code == 201
    assert subject.json()["aliases"] == ["Open AI"]
    source = client.post(
        "/api/v1/sources",
        json={"name": "Example News", "slug": "example-news", "homepage_url": "example.com"},
        headers=headers,
    )
    assert source.status_code == 201
    assert source.json()["homepage_url"] == "https://example.com"
    document = client.post(
        "/api/v1/documents",
        json={
            "source_id": source.json()["id"],
            "canonical_url": "https://example.com/story/?utm_source=test",
            "title": "A story",
        },
        headers=headers,
    )
    assert document.status_code == 201
    assert document.json()["canonical_url"] == "https://example.com/story"
    story = client.post(
        "/api/v1/stories",
        json={
            "headline": "A developing story",
            "summary": "Summary",
            "why_it_matters": "Why",
            "subject_ids": [subject.json()["id"]],
        },
        headers=headers,
    )
    assert story.status_code == 201
    tag = client.post("/api/v1/tags", json={"name": "Important"}, headers=headers)
    assert tag.status_code == 201
    tagged = client.post(
        f"/api/v1/stories/{story.json()['id']}/tags",
        json={"tag_id": tag.json()["id"]},
        headers=headers,
    )
    assert tagged.status_code == 201
    setting = client.put(
        "/api/v1/settings/timezone",
        json={"value": "America/New_York"},
        headers=headers,
    )
    assert setting.status_code == 200
    assert client.get("/api/v1/settings").json()["items"][0]["key"] == "timezone"
    secret = client.put(
        "/api/v1/settings/provider_token",
        json={"value": "do-not-store"},
        headers=headers,
    )
    assert secret.status_code == 422
    revision = client.post(
        f"/api/v1/stories/{story.json()['id']}/revisions",
        json={"headline": "An updated story", "material_change": True},
        headers=headers,
    )
    assert revision.status_code == 201
    assert revision.json()["current_revision"]["revision_number"] == 2


def test_domain_transaction_rolls_back_parent_when_relationship_validation_fails(tmp_path):
    client = _authenticated_client(tmp_path)
    headers = _csrf(client)
    response = client.post(
        "/api/v1/subjects",
        json={
            "canonical_name": "Should Roll Back",
            "subject_type": "company",
            "topic_ids": ["missing-topic"],
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert client.get("/api/v1/subjects").json()["total"] == 0
