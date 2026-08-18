"""Bounded source discovery and document acquisition primitives.

Network access is isolated behind ``HttpTransport``. Parsing produces metadata
and in-memory text only; callers decide which exact excerpts are permitted to
enter the evidence ledger.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urljoin, urlparse

from . import storage
from .content_artifacts import ContentArtifactService, normalized_text_hash
from .document_processing import enqueue_document_version_processing_tx
from .domain import DomainNotFound, DomainValidation, new_id, normalized_text, utc_now
from .url_norm import normalize_url, url_fingerprint


class AcquisitionError(RuntimeError):
    """Base class for bounded, attributable acquisition failures."""


class AcquisitionBlocked(AcquisitionError):
    """A URL or response was rejected by the acquisition policy."""


class AcquisitionTooLarge(AcquisitionError):
    """A response or parsed text exceeded its configured limit."""


class AcquisitionTimeout(AcquisitionError):
    """The transport exceeded its configured timeout."""


class FeedParseError(AcquisitionError):
    """A feed was malformed, unsafe, or did not contain usable entries."""


@dataclass(frozen=True)
class AcquisitionPolicy:
    allowed_domains: frozenset[str] = frozenset()
    denied_domains: frozenset[str] = frozenset()
    max_response_bytes: int = 2_000_000
    timeout_seconds: float = 10.0
    max_redirects: int = 3
    max_feed_entries: int = 100
    max_html_text_chars: int = 200_000

    def __post_init__(self) -> None:
        if self.max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.max_redirects < 0:
            raise ValueError("max_redirects must be nonnegative")
        if self.max_feed_entries < 1 or self.max_html_text_chars < 1:
            raise ValueError("feed and HTML limits must be positive")
        object.__setattr__(self, "allowed_domains", frozenset(_clean_domain(item) for item in self.allowed_domains))
        object.__setattr__(self, "denied_domains", frozenset(_clean_domain(item) for item in self.denied_domains))

    def check_url(self, url: str) -> str:
        try:
            canonical = normalize_url(url)
        except ValueError as exc:
            raise AcquisitionBlocked("URL is invalid") from exc
        parsed = urlparse(canonical)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AcquisitionBlocked("only HTTP(S) URLs are permitted")
        host = parsed.hostname.casefold().rstrip(".")
        if _is_private_host(host):
            raise AcquisitionBlocked("private, loopback, and local hosts are not permitted")
        if any(_domain_matches(host, domain) for domain in self.denied_domains):
            raise AcquisitionBlocked("URL host is denied")
        if self.allowed_domains and not any(_domain_matches(host, domain) for domain in self.allowed_domains):
            raise AcquisitionBlocked("URL host is not allow-listed")
        return canonical

    def check_content_length(self, content_length: int | None) -> None:
        if content_length is not None and content_length > self.max_response_bytes:
            raise AcquisitionTooLarge("response exceeds configured byte limit")

    def check_resolved_url(self, url: str) -> str:
        """Validate the URL and reject any non-public resolved address."""
        canonical = self.check_url(url)
        parsed = urlparse(canonical)
        try:
            addresses = socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise AcquisitionError("URL host could not be resolved") from exc
        if not addresses:
            raise AcquisitionError("URL host could not be resolved")
        if any(_is_private_host(item[4][0]) for item in addresses):
            raise AcquisitionBlocked("URL host resolves to a non-public address")
        return canonical


def _clean_domain(value: str) -> str:
    domain = str(value).strip().casefold().rstrip(".")
    if not domain or "/" in domain or ":" in domain:
        raise ValueError("domain controls must contain host names only")
    return domain


def _domain_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _is_private_host(host: str) -> bool:
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_unspecified,
            address.is_reserved,
        )
    )


def _normalized_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", value)


@dataclass(frozen=True)
class HTMLDocument:
    title: str
    text: str


class SafeHTMLExtractor(HTMLParser):
    """Extract bounded visible text while ignoring active/embedded content."""

    _blocked_tags = frozenset({"script", "style", "noscript", "template", "svg", "math", "iframe", "object", "embed"})
    _title_tags = frozenset({"title"})

    def __init__(self, *, max_text_chars: int = 200_000, max_nodes: int = 20_000):
        super().__init__(convert_charrefs=True)
        if max_text_chars < 1 or max_nodes < 1:
            raise ValueError("HTML limits must be positive")
        self.max_text_chars = max_text_chars
        self.max_nodes = max_nodes
        self._text_parts: list[str] = []
        self._title_parts: list[str] = []
        self._blocked_depth = 0
        self._in_title = False
        self._nodes = 0
        self._raw_chars = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._nodes += 1
        if self._nodes > self.max_nodes:
            raise AcquisitionTooLarge("HTML node limit exceeded")
        tag = tag.casefold()
        if tag in self._blocked_tags:
            self._blocked_depth += 1
        elif tag in self._title_tags and self._blocked_depth == 0:
            self._in_title = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self._blocked_tags and self._blocked_depth:
            self._blocked_depth -= 1
        elif tag in self._title_tags:
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._blocked_depth:
            return
        self._raw_chars += len(data)
        if self._raw_chars > self.max_text_chars:
            raise AcquisitionTooLarge("HTML text limit exceeded")
        if self._in_title:
            self._title_parts.append(data)
        else:
            self._text_parts.append(data)

    def extract(self, html: str) -> HTMLDocument:
        self.feed(html)
        self.close()
        return HTMLDocument(
            title=_normalized_text(" ".join(self._title_parts))[:500],
            text=_normalized_text(" ".join(self._text_parts)),
        )


def raw_content_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def normalized_content_hash(body: bytes, content_type: str) -> str:
    if "html" in content_type.casefold():
        normalized = SafeHTMLExtractor(max_text_chars=max(len(body), 1)).extract(
            body.decode("utf-8", errors="replace")
        ).text.encode("utf-8")
    else:
        normalized = _normalized_text(body.decode("utf-8", errors="replace")).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


@dataclass(frozen=True)
class FeedEntry:
    title: str
    url: str
    published_at: str | None
    summary: str
    entry_id: str | None = None


@dataclass(frozen=True)
class FeedResult:
    title: str
    entries: tuple[FeedEntry, ...]
    format: str = "rss"


class FeedParser:
    def __init__(self, *, max_bytes: int = 2_000_000, max_entries: int = 100):
        self.max_bytes = max_bytes
        self.max_entries = max_entries

    def parse(self, body: bytes, feed_url: str) -> FeedResult:
        if len(body) > self.max_bytes:
            raise AcquisitionTooLarge("feed exceeds configured byte limit")
        lowered = body.lower()
        if b"<!doctype" in lowered or b"<!entity" in lowered:
            raise FeedParseError("DOCTYPE and ENTITY declarations are not permitted")
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise FeedParseError("feed XML is malformed") from exc
        root_name = _local_name(root.tag)
        if root_name == "rss":
            container = next((item for item in root if _local_name(item.tag) == "channel"), root)
            entry_nodes = [item for item in container if _local_name(item.tag) == "item"]
        elif root_name == "feed":
            container = root
            entry_nodes = [item for item in root if _local_name(item.tag) == "entry"]
        else:
            raise FeedParseError("root element is not RSS or Atom")
        feed_title = _child_text(container, "title") or normalize_url(feed_url)
        entries: list[FeedEntry] = []
        for node in entry_nodes[: self.max_entries]:
            url = _feed_link(node)
            if not url:
                continue
            try:
                canonical = normalize_url(urljoin(feed_url, url))
            except ValueError:
                continue
            title = _child_text(node, "title") or canonical
            published = _child_text(node, "pubDate", "published", "updated")
            published = _normalize_date(published)
            summary = _child_text(node, "description", "summary", "content") or ""
            if "<" in summary and ">" in summary:
                summary = SafeHTMLExtractor(max_text_chars=20_000).extract(summary).text
            entries.append(
                FeedEntry(
                    title=_normalized_text(title)[:500],
                    url=canonical,
                    published_at=published,
                    summary=_normalized_text(summary)[:20_000],
                    entry_id=_child_text(node, "id"),
                )
            )
        return FeedResult(title=_normalized_text(feed_title)[:500], entries=tuple(entries), format="atom" if root_name == "feed" else "rss")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _child_text(node: ET.Element, *names: str) -> str | None:
    wanted = {name.casefold() for name in names}
    for child in node:
        if _local_name(child.tag) in wanted:
            value = _normalized_text(" ".join(child.itertext()))
            if value:
                return value
    return None


def _feed_link(node: ET.Element) -> str | None:
    for child in node:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        rel = child.attrib.get("rel", "alternate")
        if href and rel in {"alternate", ""}:
            return href
        text = _normalized_text(" ".join(child.itertext()))
        if text:
            return text
    return _child_text(node, "id")


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError):
        return value


@dataclass(frozen=True)
class HttpResponse:
    status_code: int
    url: str
    headers: Mapping[str, str]
    body: bytes


class HttpTransport(Protocol):
    def get(self, url: str, *, headers: Mapping[str, str], policy: AcquisitionPolicy) -> HttpResponse: ...


class _BoundedRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, max_redirects: int, policy: AcquisitionPolicy):
        super().__init__()
        self.max_redirects = max_redirects
        self.policy = policy
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if self.count >= self.max_redirects:
            raise AcquisitionBlocked("redirect limit exceeded")
        # Validate the redirect target's DNS/public-address policy, but follow
        # the server-provided URL rather than its normalized form. Normalizing
        # drops `www.` and other details that servers legitimately redirect to,
        # which would bounce every such hop back to the same host forever.
        self.policy.check_resolved_url(newurl)
        self.count += 1
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibHttpTransport:
    """Bounded HTTP GET transport; never executes browser JavaScript."""

    user_agent = "Newsroom/0.1 (+local source acquisition)"

    def get(self, url: str, *, headers: Mapping[str, str], policy: AcquisitionPolicy) -> HttpResponse:
        canonical = policy.check_resolved_url(url)
        request = urllib.request.Request(canonical, headers={"User-Agent": self.user_agent, **dict(headers)}, method="GET")
        opener = urllib.request.build_opener(_BoundedRedirectHandler(policy.max_redirects, policy))
        try:
            with opener.open(request, timeout=policy.timeout_seconds) as response:
                content_length = _header_int(response.headers.get("Content-Length"))
                policy.check_content_length(content_length)
                body = response.read(policy.max_response_bytes + 1)
                policy.check_content_length(len(body))
                final_url = policy.check_url(response.geturl())
                return HttpResponse(response.status, final_url, _headers(response.headers), body)
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return HttpResponse(304, canonical, _headers(exc.headers), b"")
            raise AcquisitionError(f"HTTP status {exc.code}") from exc
        except TimeoutError as exc:
            raise AcquisitionTimeout("HTTP request timed out") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise AcquisitionTimeout("HTTP request timed out") from exc
            raise AcquisitionError("HTTP request failed") from exc


def _header_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        raise AcquisitionError("invalid response Content-Length")


def _headers(headers: Any) -> dict[str, str]:
    return {str(key).casefold(): str(value).strip() for key, value in headers.items()}


@dataclass(frozen=True)
class DocumentAcquisitionResult:
    outcome: str
    source_id: str
    request_url: str
    final_url: str | None
    document_id: str | None
    document_version_id: str | None
    event_id: str
    raw_content_hash: str | None = None
    normalized_content_hash: str | None = None
    status_code: int | None = None
    extracted: HTMLDocument | None = None
    artifact_id: str | None = None


@dataclass(frozen=True)
class FeedPollResult:
    outcome: str
    source_id: str
    feed_url: str
    event_id: str
    entries: tuple[FeedEntry, ...] = ()
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    artifact_ids: tuple[str | None, ...] = ()


class AcquisitionService:
    """Persist bounded acquisition observations without storing article bodies."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        transport: HttpTransport | None = None,
        policy: AcquisitionPolicy | None = None,
        parser: FeedParser | None = None,
    ):
        self.db_path = Path(db_path)
        self.policy = policy or AcquisitionPolicy()
        self.transport = transport or UrllibHttpTransport()
        self.parser = parser or FeedParser(
            max_bytes=self.policy.max_response_bytes,
            max_entries=self.policy.max_feed_entries,
        )
        self.profiles = SourceProfileService(db_path)
        self.artifacts = ContentArtifactService(
            db_path,
            max_text_chars=self.policy.max_html_text_chars,
        )

    def acquire_document(
        self,
        source_id: str,
        url: str,
        *,
        channel: str = "direct_http",
        monitor_id: str | None = None,
    ) -> DocumentAcquisitionResult:
        if channel not in {"direct_http", "page"}:
            raise DomainValidation("document acquisition channel must be direct_http or page")
        self._require_source(source_id)
        canonical = url
        try:
            canonical = self.policy.check_url(url)
            previous = self._latest_event(source_id, canonical, channel=channel)
            response = self.transport.get(
                canonical,
                headers=self._conditional_headers(previous),
                policy=self.policy,
            )
            if response.status_code == 304:
                previous_version_id = previous["document_version_id"] if previous else None
                previous_artifact_id = None
                if previous_version_id is not None:
                    conn = storage.connect(self.db_path)
                    try:
                        row = conn.execute(
                            "SELECT artifact_id FROM document_versions WHERE id = ?",
                            (previous_version_id,),
                        ).fetchone()
                        previous_artifact_id = row[0] if row is not None else None
                    finally:
                        conn.close()
                event_id = self._record_event(
                    source_id=source_id,
                    channel=channel,
                    request_url=canonical,
                    final_url=response.url,
                    outcome="not_modified",
                    status_code=304,
                    headers=response.headers,
                    response_bytes=0,
                    document_id=previous["document_id"] if previous else None,
                    document_version_id=previous_version_id,
                    raw_hash=previous["raw_content_hash"] if previous else None,
                    normalized_hash=previous["normalized_content_hash"] if previous else None,
                )
                self.profiles.record_success(source_id, channel, document_count=0, unchanged_count=0)
                return DocumentAcquisitionResult(
                    outcome="not_modified",
                    source_id=source_id,
                    request_url=canonical,
                    final_url=response.url,
                    document_id=previous["document_id"] if previous else None,
                    document_version_id=previous_version_id,
                    event_id=event_id,
                    raw_content_hash=previous["raw_content_hash"] if previous else None,
                    normalized_content_hash=previous["normalized_content_hash"] if previous else None,
                    status_code=304,
                    artifact_id=previous_artifact_id,
                )
            if response.status_code < 200 or response.status_code >= 300:
                raise AcquisitionError(f"unexpected HTTP status {response.status_code}")
            self.policy.check_content_length(len(response.body))
            final_url = self.policy.check_url(response.url)
            content_type = _header(response.headers, "content-type") or "application/octet-stream"
            raw_hash = raw_content_hash(response.body)
            extracted = self._extract_response(response.body, content_type)
            if extracted is not None:
                normalized_text = extracted.text
                content_kind = "visible_text"
            else:
                normalized_text = _normalized_text(response.body.decode("utf-8", errors="replace"))
                content_kind = "fallback_text"
                if len(normalized_text) > self.policy.max_html_text_chars:
                    raise AcquisitionTooLarge("normalized text exceeds configured character limit")
            # The normalized content hash is computed over the exact canonical
            # text that is persisted as the durable content artifact, never
            # over a different normalization of the same body.
            normalized_hash = normalized_text_hash(normalized_text)
            title = (extracted.title if extracted else "") or _title_from_url(final_url)
            result = self._persist_document(
                source_id=source_id,
                request_url=canonical,
                final_url=final_url,
                channel=channel,
                response=response,
                title=title,
                content_type=content_type,
                raw_hash=raw_hash,
                normalized_hash=normalized_hash,
                text_length=len(normalized_text),
                artifact_text=normalized_text,
                content_kind=content_kind,
                monitor_id=monitor_id,
            )
            if result.outcome == "retrieved":
                self.profiles.record_success(source_id, channel, document_count=1, changed_count=1)
            else:
                self.profiles.record_success(source_id, channel, document_count=0, unchanged_count=1)
            return DocumentAcquisitionResult(**{**result.__dict__, "extracted": extracted})
        except AcquisitionError as exc:
            self._record_failure(source_id, canonical, channel, exc)
            raise

    def poll_feed(self, source_id: str, feed_url: str | None = None, *, monitor_id: str | None = None) -> FeedPollResult:
        self._require_source(source_id)
        if feed_url is None:
            conn = storage.connect(self.db_path)
            try:
                row = conn.execute("SELECT feed_url FROM sources WHERE id = ?", (source_id,)).fetchone()
            finally:
                conn.close()
            feed_url = row[0] if row else None
        if not feed_url:
            raise DomainValidation("source has no feed URL")
        canonical = feed_url
        try:
            canonical = self.policy.check_url(feed_url)
            previous = self._latest_event(source_id, canonical)
            response = self.transport.get(
                canonical,
                headers=self._conditional_headers(previous),
                policy=self.policy,
            )
            event_channel = previous["channel"] if previous and previous["channel"] in {"rss", "atom"} else "rss"
            if response.status_code == 304:
                event_id = self._record_event(
                    source_id=source_id,
                    channel=event_channel,
                    request_url=canonical,
                    final_url=response.url,
                    outcome="not_modified",
                    status_code=304,
                    headers=response.headers,
                    response_bytes=0,
                    document_id=None,
                    document_version_id=None,
                    raw_hash=previous["raw_content_hash"] if previous else None,
                    normalized_hash=previous["normalized_content_hash"] if previous else None,
                )
                self.profiles.record_success(source_id, event_channel, document_count=0, unchanged_count=1)
                return FeedPollResult("not_modified", source_id, canonical, event_id)
            if response.status_code < 200 or response.status_code >= 300:
                raise AcquisitionError(f"unexpected HTTP status {response.status_code}")
            self.policy.check_content_length(len(response.body))
            final_url = self.policy.check_url(response.url)
            parsed = self.parser.parse(response.body, final_url)
            content_type = _header(response.headers, "content-type") or "application/xml"
            raw_hash = raw_content_hash(response.body)
            normalized_hash = normalized_content_hash(response.body, content_type)
            new_count, changed_count, unchanged_count, artifact_ids = self._persist_feed_entries(
                source_id, parsed.entries, monitor_id=monitor_id
            )
            outcome = "retrieved" if new_count or changed_count else "unchanged"
            event_id = self._record_event(
                source_id=source_id,
                channel=parsed.format,
                request_url=canonical,
                final_url=final_url,
                outcome=outcome,
                status_code=response.status_code,
                headers=response.headers,
                response_bytes=len(response.body),
                document_id=None,
                document_version_id=None,
                raw_hash=raw_hash,
                normalized_hash=normalized_hash,
            )
            self.profiles.record_success(
                source_id,
                parsed.format,
                document_count=new_count,
                changed_count=changed_count,
                unchanged_count=unchanged_count,
            )
            return FeedPollResult(outcome, source_id, canonical, event_id, parsed.entries, new_count, changed_count, unchanged_count, artifact_ids)
        except AcquisitionError as exc:
            self._record_failure(source_id, canonical, "rss", exc)
            raise

    def _extract_response(self, body: bytes, content_type: str) -> HTMLDocument | None:
        if "html" in content_type.casefold():
            return SafeHTMLExtractor(max_text_chars=self.policy.max_html_text_chars).extract(
                body.decode("utf-8", errors="replace")
            )
        if "text/plain" in content_type.casefold():
            text = body.decode("utf-8", errors="replace")
            if len(text) > self.policy.max_html_text_chars:
                raise AcquisitionTooLarge("text response exceeds configured character limit")
            return HTMLDocument("", _normalized_text(text))
        return None

    def _persist_document(
        self,
        *,
        source_id: str,
        request_url: str,
        final_url: str,
        channel: str,
        response: HttpResponse,
        title: str,
        content_type: str,
        raw_hash: str,
        normalized_hash: str,
        text_length: int,
        artifact_text: str,
        content_kind: str,
        monitor_id: str | None = None,
    ) -> DocumentAcquisitionResult:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_source_tx(conn, source_id)
                document = conn.execute(
                    "SELECT * FROM documents WHERE canonical_url_hash = ?", (url_fingerprint(final_url),)
                ).fetchone()
                now = utc_now()
                if document is None:
                    document_id = new_id("doc")
                    conn.execute(
                        """
                        INSERT INTO documents
                            (id, source_id, canonical_url, canonical_url_hash, title,
                             title_normalized, published_at, first_seen_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (document_id, source_id, final_url, url_fingerprint(final_url), title, normalized_text(title), None, now, now),
                    )
                else:
                    if document["source_id"] != source_id:
                        raise AcquisitionError("canonical document belongs to another source")
                    document_id = document["id"]
                latest = conn.execute(
                    "SELECT * FROM document_versions WHERE document_id = ? ORDER BY retrieved_at DESC, id DESC LIMIT 1",
                    (document_id,),
                ).fetchone()
                if latest is not None and latest["content_hash"] == raw_hash:
                    event_id = self._insert_event_tx(
                        conn, source_id, channel, request_url, final_url, "unchanged", response.status_code,
                        response.headers, len(response.body), document_id, latest["id"], raw_hash, normalized_hash,
                    )
                    return DocumentAcquisitionResult("unchanged", source_id, request_url, final_url, document_id, latest["id"], event_id, raw_hash, normalized_hash, response.status_code, artifact_id=latest["artifact_id"] if "artifact_id" in latest.keys() else None)
                version_id = new_id("dv")
                artifact = self.artifacts.create_tx(
                    conn,
                    normalized_text=artifact_text,
                    content_kind=content_kind,
                    max_text_chars=self.policy.max_html_text_chars,
                )
                metadata = json.dumps(
                    {"normalized_content_hash": normalized_hash, "text_length": text_length, "title": title},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                conn.execute(
                    """
                    INSERT INTO document_versions
                        (id, document_id, retrieved_at, content_hash, content_kind,
                         artifact_id, normalized_json, etag, last_modified, created_at)
                    VALUES (?, ?, ?, ?, 'excerpt', ?, ?, ?, ?, ?)
                    """,
                    (version_id, document_id, now, raw_hash, artifact["id"], metadata, _header(response.headers, "etag"), _header(response.headers, "last-modified"), now),
                )
                event_id = self._insert_event_tx(
                    conn, source_id, channel, request_url, final_url, "retrieved", response.status_code,
                    response.headers, len(response.body), document_id, version_id, raw_hash, normalized_hash,
                )
                enqueue_document_version_processing_tx(
                    conn,
                    version_id=version_id,
                    monitor_id=monitor_id,
                )
                return DocumentAcquisitionResult("retrieved", source_id, request_url, final_url, document_id, version_id, event_id, raw_hash, normalized_hash, response.status_code, artifact_id=artifact["id"])
        finally:
            conn.close()

    def _persist_feed_entries(
        self,
        source_id: str,
        entries: tuple[FeedEntry, ...],
        *,
        monitor_id: str | None = None,
    ) -> tuple[int, int, int, tuple[str | None, ...]]:
        new_count = changed_count = unchanged_count = 0
        artifact_ids: list[str | None] = []
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_source_tx(conn, source_id)
                for entry in entries:
                    metadata = json.dumps(
                        {"published_at": entry.published_at, "summary": entry.summary, "title": entry.title, "url": entry.url},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    entry_hash = raw_content_hash(metadata.encode("utf-8"))
                    document = conn.execute(
                        "SELECT * FROM documents WHERE canonical_url_hash = ?", (url_fingerprint(entry.url),)
                    ).fetchone()
                    now = utc_now()
                    if document is None:
                        document_id = new_id("doc")
                        conn.execute(
                            """
                            INSERT INTO documents
                                (id, source_id, canonical_url, canonical_url_hash, title,
                                 title_normalized, published_at, first_seen_at, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (document_id, source_id, entry.url, url_fingerprint(entry.url), entry.title, normalized_text(entry.title), entry.published_at, now, now),
                        )
                        new_count += 1
                    else:
                        if document["source_id"] != source_id:
                            continue
                        document_id = document["id"]
                    latest = conn.execute(
                        "SELECT content_hash FROM document_versions WHERE document_id = ? ORDER BY retrieved_at DESC, id DESC LIMIT 1",
                        (document_id,),
                    ).fetchone()
                    if latest is not None and latest[0] == entry_hash:
                        unchanged_count += 1
                        artifact_ids.append(None)
                        continue
                    version_id = new_id("dv")
                    # The exact metadata string that defines this feed entry is
                    # the durable normalized content artifact; the artifact hash
                    # equals entry_hash (sha256 of the exact persisted metadata).
                    artifact = self.artifacts.create_tx(
                        conn,
                        normalized_text=metadata,
                        content_kind="feed_metadata",
                        max_text_chars=self.policy.max_html_text_chars,
                    )
                    conn.execute(
                        """
                        INSERT INTO document_versions
                            (id, document_id, retrieved_at, content_hash, content_kind,
                             artifact_id, normalized_json, created_at)
                        VALUES (?, ?, ?, ?, 'metadata', ?, ?, ?)
                        """,
                        (version_id, document_id, now, entry_hash, artifact["id"], metadata, now),
                    )
                    enqueue_document_version_processing_tx(
                        conn,
                        version_id=version_id,
                        monitor_id=monitor_id,
                    )
                    artifact_ids.append(artifact["id"])
                    if latest is not None:
                        changed_count += 1
            return new_count, changed_count, unchanged_count, tuple(artifact_ids)
        finally:
            conn.close()

    def _record_failure(self, source_id: str, request_url: str, channel: str, exc: AcquisitionError) -> None:
        try:
            safe_url = self.policy.check_url(request_url)
        except AcquisitionError:
            safe_url = request_url[:2048]
        event_id = self._record_event(
            source_id=source_id,
            channel=channel if channel in {"rss", "atom", "direct_http", "page"} else "direct_http",
            request_url=safe_url,
            final_url=None,
            outcome="blocked" if isinstance(exc, (AcquisitionBlocked, AcquisitionTooLarge)) else "failed",
            status_code=None,
            headers={},
            response_bytes=0,
            document_id=None,
            document_version_id=None,
            raw_hash=None,
            normalized_hash=None,
            error_code=type(exc).__name__,
            error_message=str(exc)[:500],
        )
        self.profiles.record_failure(source_id, type(exc).__name__)

    def _record_event(self, **values: Any) -> str:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                return self._insert_event_tx(conn, **values)
        finally:
            conn.close()

    def _insert_event_tx(self, conn, source_id, channel, request_url, final_url, outcome, status_code, headers, response_bytes, document_id, document_version_id, raw_hash, normalized_hash, error_code=None, error_message=None):
        identifier = new_id("acq")
        now = utc_now()
        conn.execute(
            """
            INSERT INTO acquisition_events
                (id, source_id, document_id, document_version_id, channel,
                 request_url, final_url, outcome, status_code, content_type,
                 etag, last_modified, raw_content_hash, normalized_content_hash,
                 response_bytes, error_code, error_message, observed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (identifier, source_id, document_id, document_version_id, channel, request_url, final_url, outcome, status_code,
             _header(headers, "content-type"), _header(headers, "etag"), _header(headers, "last-modified"), raw_hash,
             normalized_hash, response_bytes, error_code, error_message, now, now),
        )
        return identifier

    def _latest_event(self, source_id: str, request_url: str, *, channel: str | None = None):
        conn = storage.connect(self.db_path)
        try:
            if channel is None:
                return conn.execute(
                    "SELECT * FROM acquisition_events WHERE source_id = ? AND request_url = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                    (source_id, request_url),
                ).fetchone()
            return conn.execute(
                "SELECT * FROM acquisition_events WHERE source_id = ? AND request_url = ? AND channel = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (source_id, request_url, channel),
            ).fetchone()
        finally:
            conn.close()

    @staticmethod
    def _conditional_headers(previous) -> dict[str, str]:
        if previous is None:
            return {}
        headers: dict[str, str] = {}
        if previous["etag"]:
            headers["If-None-Match"] = previous["etag"]
        if previous["last_modified"]:
            headers["If-Modified-Since"] = previous["last_modified"]
        return headers

    def _require_source(self, source_id: str) -> None:
        conn = storage.connect(self.db_path)
        try:
            self._require_source_tx(conn, source_id)
        finally:
            conn.close()

    @staticmethod
    def _require_source_tx(conn, source_id: str):
        row = conn.execute("SELECT * FROM sources WHERE id = ? AND deleted_at IS NULL", (source_id,)).fetchone()
        if row is None:
            raise DomainNotFound("source not found")
        return row


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.casefold()
    for key, value in headers.items():
        if str(key).casefold() == target:
            return str(value).strip()
    return None


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return _normalized_text(path.rsplit("/", 1)[-1].replace("-", " ").replace("_", " "))[:500] or urlparse(url).hostname or "Untitled document"


def _json_value(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


class SourceProfileService:
    """Maintain multidimensional source observations without a trust score."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def get(self, source_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            source = conn.execute("SELECT source_kind FROM sources WHERE id = ? AND deleted_at IS NULL", (source_id,)).fetchone()
            if source is None:
                raise DomainNotFound("source not found")
            self._ensure_tx(conn, source_id, source[0])
            row = conn.execute("SELECT * FROM source_profiles WHERE source_id = ?", (source_id,)).fetchone()
            return self._result(row)
        finally:
            conn.close()

    def record_success(
        self,
        source_id: str,
        method: str,
        *,
        document_count: int = 0,
        changed_count: int = 0,
        unchanged_count: int = 0,
        useful_count: int = 0,
    ) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                source = AcquisitionService._require_source_tx(conn, source_id)
                self._ensure_tx(conn, source_id, source["source_kind"])
                row = conn.execute("SELECT * FROM source_profiles WHERE source_id = ?", (source_id,)).fetchone()
                activity = _json_value(row["activity_json"], {})
                coverage = _json_value(row["coverage_json"], {})
                duplication = _json_value(row["duplication_json"], {})
                usefulness = _json_value(row["usefulness_json"], {})
                methods = _json_value(row["acquisition_methods_json"], [])
                if method not in methods:
                    methods.append(method)
                activity["success_count"] = int(activity.get("success_count", 0)) + 1
                activity["last_success_at"] = utc_now()
                coverage["documents_seen"] = int(coverage.get("documents_seen", 0)) + document_count
                duplication["changed_count"] = int(duplication.get("changed_count", 0)) + changed_count
                duplication["unchanged_count"] = int(duplication.get("unchanged_count", 0)) + unchanged_count
                usefulness["useful_count"] = int(usefulness.get("useful_count", 0)) + useful_count
                conn.execute(
                    """
                    UPDATE source_profiles
                    SET acquisition_methods_json = ?, activity_json = ?, coverage_json = ?,
                        duplication_json = ?, usefulness_json = ?, updated_at = ?
                    WHERE source_id = ?
                    """,
                    (json.dumps(methods, sort_keys=True), json.dumps(activity, sort_keys=True), json.dumps(coverage, sort_keys=True),
                     json.dumps(duplication, sort_keys=True), json.dumps(usefulness, sort_keys=True), utc_now(), source_id),
                )
            return self.get(source_id)
        finally:
            conn.close()

    def record_failure(self, source_id: str, error_code: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                source = AcquisitionService._require_source_tx(conn, source_id)
                self._ensure_tx(conn, source_id, source["source_kind"])
                row = conn.execute("SELECT * FROM source_profiles WHERE source_id = ?", (source_id,)).fetchone()
                failures = _json_value(row["failure_json"], {})
                by_code = failures.get("by_code", {})
                by_code[error_code] = int(by_code.get(error_code, 0)) + 1
                failures["count"] = int(failures.get("count", 0)) + 1
                failures["by_code"] = by_code
                failures["last_error_code"] = error_code
                failures["last_failure_at"] = utc_now()
                conn.execute(
                    "UPDATE source_profiles SET failure_json = ?, updated_at = ? WHERE source_id = ?",
                    (json.dumps(failures, sort_keys=True), utc_now(), source_id),
                )
            return self.get(source_id)
        finally:
            conn.close()

    @staticmethod
    def _ensure_tx(conn, source_id: str, source_type: str) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO source_profiles
                (source_id, source_type, coverage_json, acquisition_methods_json,
                 activity_json, failure_json, duplication_json, usefulness_json, updated_at)
            VALUES (?, ?, '{}', '[]', '{"success_count": 0}', '{"count": 0, "by_code": {}}',
                    '{"changed_count": 0, "unchanged_count": 0}', '{"useful_count": 0}', ?)
            """,
            (source_id, source_type or "unknown", utc_now()),
        )

    @staticmethod
    def _result(row) -> dict[str, Any]:
        return {
            "source_id": row["source_id"],
            "source_type": row["source_type"],
            "coverage": _json_value(row["coverage_json"], {}),
            "acquisition_methods": _json_value(row["acquisition_methods_json"], []),
            "activity": _json_value(row["activity_json"], {}),
            "failure": _json_value(row["failure_json"], {}),
            "duplication": _json_value(row["duplication_json"], {}),
            "usefulness": _json_value(row["usefulness_json"], {}),
            "updated_at": row["updated_at"],
        }


class SourceSuggestionService:
    """Persist suggestions until a user explicitly approves or rejects them."""

    _methods = frozenset({"rss", "atom", "direct_http", "page"})

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def create(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        rationale = str(data.get("rationale", "")).strip()
        contribution = str(data.get("likely_contribution", "")).strip()
        if not name or not rationale or not contribution:
            raise DomainValidation("source suggestion requires name, rationale, and likely_contribution")
        methods = list(dict.fromkeys(str(item).strip() for item in data.get("supported_methods", [])))
        if not methods or any(item not in self._methods for item in methods):
            raise DomainValidation("source suggestion has unsupported monitoring method")
        try:
            homepage = normalize_url(data["homepage_url"]) if data.get("homepage_url") else None
            feed = normalize_url(data["feed_url"]) if data.get("feed_url") else None
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        identifier = new_id("suggest")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                source_id = data.get("source_id")
                if source_id is not None:
                    AcquisitionService._require_source_tx(conn, source_id)
                conn.execute(
                    """
                    INSERT INTO source_suggestions
                        (id, source_id, name, domain, homepage_url, feed_url,
                         rationale, likely_contribution, limitations,
                         supported_methods_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (identifier, source_id, name, urlparse(homepage).hostname if homepage else None, homepage, feed,
                     rationale[:4000], contribution[:4000], str(data.get("limitations", ""))[:4000], json.dumps(methods), utc_now()),
                )
        finally:
            conn.close()
        return self.get(identifier)

    def get(self, suggestion_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM source_suggestions WHERE id = ?", (suggestion_id,)).fetchone()
            if row is None:
                raise DomainNotFound("source suggestion not found")
            return self._result(row)
        finally:
            conn.close()

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status is not None and status not in {"pending", "approved", "rejected"}:
            raise DomainValidation("invalid source suggestion status")
        conn = storage.connect(self.db_path)
        try:
            if status:
                rows = conn.execute("SELECT * FROM source_suggestions WHERE status = ? ORDER BY created_at, id", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM source_suggestions ORDER BY created_at, id").fetchall()
            return [self._result(row) for row in rows]
        finally:
            conn.close()

    def review(self, suggestion_id: str, status: str, reviewed_by: str) -> dict[str, Any]:
        if status not in {"approved", "rejected"}:
            raise DomainValidation("source suggestions may only be approved or rejected")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                result = conn.execute(
                    "UPDATE source_suggestions SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                    (status, utc_now(), reviewed_by[:200], suggestion_id),
                )
                if result.rowcount != 1:
                    raise DomainNotFound("source suggestion not found")
        finally:
            conn.close()
        return self.get(suggestion_id)

    @staticmethod
    def _result(row) -> dict[str, Any]:
        result = dict(row)
        result["supported_methods"] = _json_value(result.pop("supported_methods_json"), [])
        return result


__all__ = [
    "AcquisitionError",
    "AcquisitionBlocked",
    "AcquisitionTooLarge",
    "AcquisitionTimeout",
    "FeedParseError",
    "AcquisitionPolicy",
    "HTMLDocument",
    "SafeHTMLExtractor",
    "raw_content_hash",
    "normalized_content_hash",
    "FeedEntry",
    "FeedResult",
    "FeedParser",
    "HttpResponse",
    "HttpTransport",
    "UrllibHttpTransport",
    "DocumentAcquisitionResult",
    "FeedPollResult",
    "AcquisitionService",
    "SourceProfileService",
    "SourceSuggestionService",
]
