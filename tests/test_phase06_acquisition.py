from __future__ import annotations

import socket
import sqlite3

import pytest

from newsroom.acquisition import (
    AcquisitionBlocked,
    AcquisitionService,
    AcquisitionPolicy,
    AcquisitionTimeout,
    AcquisitionTooLarge,
    FeedParseError,
    FeedParser,
    HttpResponse,
    SafeHTMLExtractor,
    SourceProfileService,
    SourceSuggestionService,
    raw_content_hash,
    normalized_content_hash,
)
from newsroom import storage
from newsroom.domain import CoreService
from newsroom.migrations import apply_migrations, migration_status
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from fastapi.testclient import TestClient


PASSWORD = "a-long-test-password-12345"


RSS_FIXTURE = b"""
<rss version="2.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>Launch update</title>
      <link>https://www.example.test/news/launch?utm_source=feed</link>
      <pubDate>Mon, 16 Aug 2026 12:00:00 GMT</pubDate>
      <description><![CDATA[<p>Acme launched Atlas.</p>]]></description>
    </item>
  </channel>
</rss>
"""

ATOM_FIXTURE = b"""
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom fixture</title>
  <entry>
    <title>Atom update</title>
    <id>https://example.test/news/atom</id>
    <link rel="alternate" href="https://example.test/news/atom?fbclid=123" />
    <updated>2026-08-16T12:00:00Z</updated>
    <summary>Atom summary</summary>
  </entry>
</feed>
"""


def test_phase06_migration_is_idempotent_and_adds_acquisition_tables(tmp_db):
    assert apply_migrations(tmp_db).applied_versions == (1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert apply_migrations(tmp_db).applied_versions == ()
    assert migration_status(tmp_db) == (1, 2, 3, 4, 5, 6, 7, 8, 9)

    conn = storage.connect(tmp_db)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        conn.close()
    assert {"acquisition_events", "source_profiles", "source_suggestions"} <= tables


def test_policy_denies_disallowed_hosts_and_bounds_response_size():
    policy = AcquisitionPolicy(
        allowed_domains=frozenset({"example.test"}),
        denied_domains=frozenset({"blocked.example.test"}),
        max_response_bytes=10,
    )

    policy.check_url("https://news.example.test/item")
    with pytest.raises(AcquisitionBlocked):
        policy.check_url("https://blocked.example.test/item")
    with pytest.raises(AcquisitionBlocked):
        policy.check_url("https://other.test/item")
    with pytest.raises(AcquisitionBlocked):
        AcquisitionPolicy().check_url("http://127.0.0.1/private")
    with pytest.raises(AcquisitionBlocked):
        AcquisitionPolicy().check_url("https://service.internal/item")
    with pytest.raises(AcquisitionTooLarge):
        policy.check_content_length(11)


def test_policy_blocks_hostnames_resolving_to_non_public_addresses(monkeypatch):
    def private_resolution(*_args, **_kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", private_resolution)

    with pytest.raises(AcquisitionBlocked, match="non-public address"):
        AcquisitionPolicy().check_resolved_url("https://apparently-public.example/item")


def test_safe_html_extractor_removes_active_content_and_bounds_text():
    document = SafeHTMLExtractor(max_text_chars=100).extract(
        """
        <html><head><title>Safe title</title><script>alert('x')</script></head>
        <body><h1>Headline</h1><p>First <b>paragraph</b>.</p>
        <style>.secret { display:none }</style><p>Second paragraph.</p></body></html>
        """
    )

    assert document.title == "Safe title"
    assert document.text == "Headline First paragraph. Second paragraph."
    assert "alert" not in document.text
    assert "secret" not in document.text

    with pytest.raises(AcquisitionTooLarge):
        SafeHTMLExtractor(max_text_chars=5).extract("<p>abcdef</p>")


def test_feed_parser_supports_rss_and_atom_and_normalizes_links():
    rss = FeedParser().parse(RSS_FIXTURE, "https://example.test/feed.xml")
    atom = FeedParser().parse(ATOM_FIXTURE, "https://example.test/atom.xml")

    assert rss.title == "Fixture Feed"
    assert rss.entries[0].title == "Launch update"
    assert rss.entries[0].url == "https://example.test/news/launch"
    assert rss.entries[0].summary == "Acme launched Atlas."
    assert atom.entries[0].url == "https://example.test/news/atom"
    assert atom.entries[0].published_at == "2026-08-16T12:00:00Z"

    relative = FeedParser().parse(
        b"<rss><channel><item><title>Relative</title><link>/news/relative</link></item></channel></rss>",
        "https://example.test/feeds/main.xml",
    )
    assert relative.entries[0].url == "https://example.test/news/relative"


def test_feed_parser_rejects_external_entity_declarations_and_malformed_xml():
    hostile = b'<!DOCTYPE feed [<!ENTITY xxe SYSTEM "file:///secret">]><feed></feed>'
    with pytest.raises(FeedParseError):
        FeedParser().parse(hostile, "https://example.test/feed.xml")
    hostile_late = b"<feed>" + (b" " * 5000) + b"<!DOCTYPE feed><entry /></feed>"
    with pytest.raises(FeedParseError):
        FeedParser().parse(hostile_late, "https://example.test/feed.xml")
    with pytest.raises(FeedParseError):
        FeedParser().parse(b"<rss>", "https://example.test/feed.xml")


def test_normalized_hash_ignores_html_whitespace_and_raw_hash_does_not():
    first = b"<p>First   paragraph</p>"
    second = b"<p>First paragraph</p>"
    assert normalized_content_hash(first, "text/html") == normalized_content_hash(second, "text/html")
    assert raw_content_hash(first) != raw_content_hash(second)


class SequencedTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def get(self, url, *, headers, policy):
        self.requests.append({"url": url, "headers": dict(headers)})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_conditional_document_acquisition_versions_only_changed_content_and_records_provenance(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source(
        {"name": "Fixture Web", "slug": "fixture-web", "homepage_url": "https://example.test"}
    )
    transport = SequencedTransport(
        [
            HttpResponse(
                200,
                "https://example.test/final",
                {"content-type": "text/html", "etag": '"v1"', "last-modified": "Mon, 16 Aug 2026 12:00:00 GMT"},
                b"<html><title>Launch</title><p>Atlas launched.</p></html>",
            ),
            HttpResponse(304, "https://example.test/final", {"etag": '"v1"'}, b""),
            HttpResponse(
                200,
                "https://example.test/final",
                {"content-type": "text/html", "etag": '"v2"'},
                b"<html><title>Launch</title><p>Atlas launched. It is available.</p></html>",
            ),
        ]
    )
    service = AcquisitionService(tmp_db, transport=transport)

    first = service.acquire_document(source["id"], "https://example.test/redirect", channel="direct_http")
    second = service.acquire_document(source["id"], "https://example.test/redirect", channel="direct_http")
    third = service.acquire_document(source["id"], "https://example.test/redirect", channel="direct_http")

    assert first.outcome == "retrieved"
    assert first.extracted.title == "Launch"
    assert first.extracted.text == "Atlas launched."
    assert second.outcome == "not_modified"
    assert third.outcome == "retrieved"
    assert third.document_version_id != first.document_version_id
    assert transport.requests[1]["headers"]["If-None-Match"] == '"v1"'

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 2
        event_outcomes = [row[0] for row in conn.execute("SELECT outcome FROM acquisition_events ORDER BY rowid")]
        assert event_outcomes == ["retrieved", "not_modified", "retrieved"]
        assert conn.execute("SELECT normalized_json FROM document_versions ORDER BY created_at LIMIT 1").fetchone()[0].find("Atlas launched") == -1
    finally:
        conn.close()

    profile = SourceProfileService(tmp_db).get(source["id"])
    assert profile["activity"]["success_count"] == 3
    assert "direct_http" in profile["acquisition_methods"]
    assert profile["duplication"]["unchanged_count"] == 0


def test_failed_acquisition_is_bounded_and_observable_without_partial_document_version(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "Failing Web", "slug": "failing-web"})
    service = AcquisitionService(
        tmp_db,
        transport=SequencedTransport([AcquisitionTimeout("fixture timeout")]),
    )

    with pytest.raises(AcquisitionTimeout):
        service.acquire_document(source["id"], "https://example.test/failure", channel="direct_http")

    conn = storage.connect(tmp_db)
    try:
        event = conn.execute("SELECT * FROM acquisition_events").fetchone()
        assert event["outcome"] == "failed"
        assert event["error_code"] == "AcquisitionTimeout"
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 0
    finally:
        conn.close()
    assert SourceProfileService(tmp_db).get(source["id"])["failure"]["count"] == 1


def test_oversized_response_is_blocked_without_partial_document(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "Large Web", "slug": "large-web"})
    service = AcquisitionService(
        tmp_db,
        policy=AcquisitionPolicy(max_response_bytes=10),
        transport=SequencedTransport(
            [HttpResponse(200, "https://example.test/large", {"content-type": "text/html"}, b"01234567890")]
        ),
    )

    with pytest.raises(AcquisitionTooLarge):
        service.acquire_document(source["id"], "https://example.test/large")

    conn = storage.connect(tmp_db)
    try:
        event = conn.execute("SELECT outcome, error_code FROM acquisition_events").fetchone()
        assert tuple(event) == ("blocked", "AcquisitionTooLarge")
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 0
    finally:
        conn.close()


def test_acquisition_events_are_append_only(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "Immutable Web", "slug": "immutable-web"})
    service = AcquisitionService(
        tmp_db,
        transport=SequencedTransport(
            [HttpResponse(200, "https://example.test/item", {"content-type": "text/plain"}, b"item")]
        ),
    )
    service.acquire_document(source["id"], "https://example.test/item")

    conn = storage.connect(tmp_db)
    try:
        event_id = conn.execute("SELECT id FROM acquisition_events").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="acquisition events are immutable"):
            conn.execute("UPDATE acquisition_events SET outcome = 'failed' WHERE id = ?", (event_id,))
        with pytest.raises(sqlite3.IntegrityError, match="acquisition events are immutable"):
            conn.execute("DELETE FROM acquisition_events WHERE id = ?", (event_id,))
    finally:
        conn.close()


def test_feed_polling_creates_metadata_versions_then_uses_conditional_304(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source(
        {"name": "Fixture Feed", "slug": "fixture-feed", "feed_url": "https://example.test/feed.xml", "source_kind": "feed"}
    )
    transport = SequencedTransport(
        [
            HttpResponse(200, "https://example.test/feed.xml", {"content-type": "application/rss+xml", "etag": '"feed-1"'}, RSS_FIXTURE),
            HttpResponse(304, "https://example.test/feed.xml", {"etag": '"feed-1"'}, b""),
        ]
    )
    service = AcquisitionService(tmp_db, transport=transport)

    first = service.poll_feed(source["id"])
    second = service.poll_feed(source["id"])

    assert first.new_count == 1
    assert first.unchanged_count == 0
    assert second.outcome == "not_modified"
    assert transport.requests[1]["headers"]["If-None-Match"] == '"feed-1"'
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0] == 1
    finally:
        conn.close()
    assert SourceProfileService(tmp_db).get(source["id"])["activity"]["success_count"] == 2


def test_source_suggestions_require_explicit_review_and_do_not_create_sources(tmp_db):
    apply_migrations(tmp_db)
    suggestions = SourceSuggestionService(tmp_db)
    suggestion = suggestions.create(
        {
            "name": "Official Fixture",
            "homepage_url": "https://official.example.test",
            "feed_url": "https://official.example.test/feed.xml",
            "rationale": "Matches the monitored subject.",
            "likely_contribution": "Primary announcements.",
            "limitations": "Only covers official releases.",
            "supported_methods": ["rss", "direct_http"],
        }
    )
    assert suggestion["status"] == "pending"
    assert suggestions.review(suggestion["id"], "approved", "user_1")["status"] == "approved"
    assert len(suggestions.list()) == 1
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0
    finally:
        conn.close()


def test_authenticated_profile_and_source_suggestion_api_requires_review(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.post("/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}).status_code == 201
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}
    source = client.post(
        "/api/v1/sources",
        headers=headers,
        json={"name": "API Source", "slug": "api-source", "homepage_url": "https://api.example.test"},
    ).json()

    profile = client.get(f"/api/v1/sources/{source['id']}/profile")
    assert profile.status_code == 200
    assert profile.json()["source_id"] == source["id"]
    suggestion = client.post(
        "/api/v1/source-suggestions",
        headers=headers,
        json={
            "name": "Suggested Source",
            "homepage_url": "https://suggested.example.test",
            "rationale": "Official release feed.",
            "likely_contribution": "Primary announcements.",
            "limitations": "Narrow scope.",
            "supported_methods": ["rss"],
        },
    )
    assert suggestion.status_code == 201
    assert suggestion.json()["status"] == "pending"
    review = client.post(
        f"/api/v1/source-suggestions/{suggestion.json()['id']}/review",
        headers=headers,
        json={"status": "approved"},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "approved"
