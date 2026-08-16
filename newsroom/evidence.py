"""Evidence-ledger services for the Phase 04 manual vertical slice."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .domain import (
    CoreService,
    DomainConflict,
    DomainNotFound,
    DomainValidation,
    new_id,
    normalized_slug,
    normalized_text,
    utc_now,
)
from .repository import evidence_span_hash
from .url_norm import normalize_url, parse_url, url_fingerprint


CLAIM_STATES = (
    "pending",
    "supported",
    "partially_supported",
    "disputed",
    "unsubstantiated",
    "superseded",
)
ACCEPTED_STATES = frozenset({"supported", "partially_supported"})
RELATIONSHIPS = ("supports", "contradicts", "contextualizes")


def claim_proposition_hash(proposition: str) -> str:
    return hashlib.sha256(normalized_text(proposition).encode("utf-8")).hexdigest()


def claim_set_hash(claim_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(claim_ids)).encode("utf-8")).hexdigest()


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _decode_json(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _require(conn, table: str, identifier: str, label: str, *, live: bool = False):
    predicate = "id = ?"
    params: list[object] = [identifier]
    if live:
        predicate += " AND deleted_at IS NULL"
    row = conn.execute(f"SELECT * FROM {table} WHERE {predicate}", params).fetchone()
    if row is None:
        raise DomainNotFound(f"{label} not found")
    return row


def _insert(conn, table: str, values: Mapping[str, object]) -> None:
    columns = tuple(values)
    try:
        conn.execute(
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
            tuple(values[column] for column in columns),
        )
    except sqlite3.IntegrityError as exc:
        raise DomainConflict("resource already exists or violates a relationship") from exc


class EvidenceService:
    """Short-lived transactional service for immutable evidence records."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.core = CoreService(db_path)

    def create_document_version(self, document_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("dv")
        content_hash = str(data["content_hash"]).strip()
        if not content_hash:
            raise DomainValidation("content_hash must not be empty")
        normalized_json = data.get("normalized_json")
        encoded_json = (
            json.dumps(normalized_json, sort_keys=True, separators=(",", ":"))
            if normalized_json is not None and not isinstance(normalized_json, str)
            else normalized_json
        )
        if encoded_json is not None and len(encoded_json) > 20000:
            raise DomainValidation("normalized_json exceeds max length 20000")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                _require(conn, "documents", document_id, "document")
                _insert(
                    conn,
                    "document_versions",
                    {
                        "id": identifier,
                        "document_id": document_id,
                        "retrieved_at": data.get("retrieved_at") or now,
                        "content_hash": content_hash,
                        "content_kind": data.get("content_kind", "metadata"),
                        "locator_type": data.get("locator_type"),
                        "locator_value": data.get("locator_value"),
                        "normalized_json": encoded_json,
                        "etag": data.get("etag"),
                        "last_modified": data.get("last_modified"),
                        "created_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_document_version(identifier)

    def list_document_versions(self, document_id: str, *, page=1, page_size=25) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("page must be >= 1 and page_size must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            _require(conn, "documents", document_id, "document")
            total = conn.execute(
                "SELECT COUNT(*) FROM document_versions WHERE document_id = ?", (document_id,)
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM document_versions WHERE document_id = "
                "? ORDER BY retrieved_at DESC, id DESC LIMIT ? OFFSET ?",
                (document_id, page_size, (page - 1) * page_size),
            ).fetchall()
            items = [_as_dict(row) for row in rows]
            for item in items:
                item["normalized_json"] = _decode_json(item["normalized_json"])
            return {"items": items, "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def get_document_version(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT dv.*, d.source_id, d.canonical_url, d.title AS document_title,
                       s.id AS source_record_id, s.name AS source_name, s.slug AS source_slug
                FROM document_versions dv
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE dv.id = ?
                """,
                (identifier,),
            ).fetchone()
            if row is None:
                raise DomainNotFound("document version not found")
            result = _as_dict(row)
            result["normalized_json"] = _decode_json(result["normalized_json"])
            result["document"] = {
                "id": result["document_id"],
                "source_id": result["source_id"],
                "canonical_url": result.pop("canonical_url"),
                "title": result.pop("document_title"),
            }
            result["source"] = {
                "id": result.pop("source_record_id"),
                "name": result.pop("source_name"),
                "slug": result.pop("source_slug"),
            }
            return result
        finally:
            conn.close()

    def create_evidence_span(self, document_version_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("span")
        excerpt = str(data["excerpt"]).strip()
        if not excerpt:
            raise DomainValidation("excerpt must not be empty")
        locator_type = data.get("locator_type")
        locator_value = data.get("locator_value")
        span_hash = evidence_span_hash(excerpt, locator_type, locator_value)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                _require(conn, "document_versions", document_version_id, "document version")
                try:
                    _insert(
                        conn,
                        "evidence_spans",
                        {
                            "id": identifier,
                            "document_version_id": document_version_id,
                            "excerpt": excerpt,
                            "locator_type": locator_type,
                            "locator_value": locator_value,
                            "span_hash": span_hash,
                            "created_at": utc_now(),
                        },
                    )
                except DomainConflict:
                    existing = conn.execute(
                        "SELECT id FROM evidence_spans WHERE document_version_id = ? AND span_hash = ?",
                        (document_version_id, span_hash),
                    ).fetchone()
                    if existing is None:
                        raise
                    identifier = existing[0]
        finally:
            conn.close()
        return self.get_evidence_span(identifier)

    def get_evidence_span(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT es.*, dv.document_id, dv.retrieved_at, dv.content_hash,
                       d.canonical_url, d.title AS document_title, d.source_id,
                       s.name AS source_name, s.slug AS source_slug
                FROM evidence_spans es
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE es.id = ?
                """,
                (identifier,),
            ).fetchone()
            if row is None:
                raise DomainNotFound("evidence span not found")
            result = _as_dict(row)
            result["document_version"] = {
                "id": result.pop("document_version_id"),
                "document_id": result.pop("document_id"),
                "retrieved_at": result.pop("retrieved_at"),
                "content_hash": result.pop("content_hash"),
            }
            result["document"] = {
                "canonical_url": result.pop("canonical_url"),
                "title": result.pop("document_title"),
                "source_id": result.pop("source_id"),
            }
            result["source"] = {
                "name": result.pop("source_name"),
                "slug": result.pop("source_slug"),
            }
            return result
        finally:
            conn.close()

    def list_evidence_spans(self, document_version_id: str, *, page=1, page_size=100) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("page must be >= 1 and page_size must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            _require(conn, "document_versions", document_version_id, "document version")
            total = conn.execute(
                "SELECT COUNT(*) FROM evidence_spans WHERE document_version_id = ?",
                (document_version_id,),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM evidence_spans WHERE document_version_id = ? "
                "ORDER BY created_at, id LIMIT ? OFFSET ?",
                (document_version_id, page_size, (page - 1) * page_size),
            ).fetchall()
            return {"items": [_as_dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def _claim_evidence(self, conn, claim_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT ce.id, ce.claim_id, ce.evidence_span_id, ce.relationship, ce.created_at,
                   es.excerpt, es.locator_type, es.locator_value, es.span_hash,
                   es.document_version_id, dv.document_id, dv.retrieved_at, dv.content_hash,
                   d.canonical_url, d.title AS document_title, d.source_id,
                   s.name AS source_name, s.slug AS source_slug
            FROM claim_evidence ce
            JOIN evidence_spans es ON es.id = ce.evidence_span_id
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE ce.claim_id = ?
            ORDER BY ce.created_at, ce.id
            """,
            (claim_id,),
        ).fetchall()
        evidence: list[dict[str, Any]] = []
        for row in rows:
            item = _as_dict(row)
            item["document_version"] = {
                "id": item.pop("document_version_id"),
                "document_id": item.pop("document_id"),
                "retrieved_at": item.pop("retrieved_at"),
                "content_hash": item.pop("content_hash"),
            }
            item["document"] = {
                "canonical_url": item.pop("canonical_url"),
                "title": item.pop("document_title"),
                "source_id": item.pop("source_id"),
            }
            item["source"] = {
                "name": item.pop("source_name"),
                "slug": item.pop("source_slug"),
            }
            evidence.append(item)
        return evidence

    def _claim_result(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        result = _as_dict(row)
        result["accepted"] = result["accepted_at"] is not None and result["state"] in ACCEPTED_STATES
        result["state_history"] = [
            _as_dict(item)
            for item in conn.execute(
                "SELECT * FROM claim_state_history WHERE claim_id = ? ORDER BY rowid",
                (result["id"],),
            ).fetchall()
        ]
        result["evidence"] = self._claim_evidence(conn, result["id"])
        return result

    def get_claim(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = _require(conn, "claims", identifier, "claim")
            return self._claim_result(conn, row)
        finally:
            conn.close()

    def list_claims(self, story_id: str, *, page=1, page_size=100) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("page must be >= 1 and page_size must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            _require(conn, "stories", story_id, "story")
            total = conn.execute("SELECT COUNT(*) FROM claims WHERE story_id = ?", (story_id,)).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM claims WHERE story_id = ? ORDER BY created_at, id LIMIT ? OFFSET ?",
                (story_id, page_size, (page - 1) * page_size),
            ).fetchall()
            return {
                "items": [self._claim_result(conn, row) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    def _create_claim_tx(self, conn, story_id: str, data: Mapping[str, Any]) -> str:
        _require(conn, "stories", story_id, "story", live=True)
        proposition = str(data["proposition"]).strip()
        if not proposition:
            raise DomainValidation("proposition must not be empty")
        supersedes = data.get("supersedes_claim_id")
        if supersedes:
            parent = _require(conn, "claims", supersedes, "claim")
            if parent["story_id"] != story_id:
                raise DomainValidation("superseded claim must belong to the same story")
        identifier = new_id("claim")
        now = utc_now()
        _insert(
            conn,
            "claims",
            {
                "id": identifier,
                "story_id": story_id,
                "proposition": proposition,
                "proposition_hash": claim_proposition_hash(proposition),
                "importance": data.get("importance", "relevant"),
                "state": "pending",
                "supersedes_claim_id": supersedes,
                "created_at": now,
                "accepted_at": None,
            },
        )
        _insert(
            conn,
            "claim_state_history",
            {
                "id": new_id("csh"),
                "claim_id": identifier,
                "from_state": None,
                "to_state": "pending",
                "reason": "claim created",
                "created_at": now,
            },
        )
        if supersedes:
            self._set_claim_state_tx(conn, supersedes, "superseded", "superseded by corrected claim")
        return identifier

    def create_claim(self, story_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                identifier = self._create_claim_tx(conn, story_id, data)
        finally:
            conn.close()
        return self.get_claim(identifier)

    def _set_claim_state_tx(self, conn, claim_id: str, state: str, reason: str) -> None:
        if state not in CLAIM_STATES:
            raise DomainValidation("invalid claim state")
        row = _require(conn, "claims", claim_id, "claim")
        if row["state"] == state:
            return
        now = utc_now()
        conn.execute("UPDATE claims SET state = ? WHERE id = ?", (state, claim_id))
        _insert(
            conn,
            "claim_state_history",
            {
                "id": new_id("csh"),
                "claim_id": claim_id,
                "from_state": row["state"],
                "to_state": state,
                "reason": reason,
                "created_at": now,
            },
        )

    def set_claim_state(self, claim_id: str, state: str, reason: str = "") -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._set_claim_state_tx(conn, claim_id, state, reason.strip())
        finally:
            conn.close()
        return self.get_claim(claim_id)

    def _accept_claim_tx(self, conn, claim_id: str) -> None:
        row = _require(conn, "claims", claim_id, "claim")
        if row["state"] not in ACCEPTED_STATES:
            raise DomainConflict("claim must be supported or partially_supported before acceptance")
        supported = conn.execute(
            "SELECT 1 FROM claim_evidence WHERE claim_id = ? AND relationship = 'supports' LIMIT 1",
            (claim_id,),
        ).fetchone()
        if supported is None:
            raise DomainConflict("claim requires supporting evidence before acceptance")
        if row["accepted_at"] is None:
            conn.execute("UPDATE claims SET accepted_at = ? WHERE id = ?", (utc_now(), claim_id))

    def accept_claim(self, claim_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._accept_claim_tx(conn, claim_id)
        finally:
            conn.close()
        return self.get_claim(claim_id)

    def link_claim_evidence(self, claim_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        relationship = data["relationship"]
        if relationship not in RELATIONSHIPS:
            raise DomainValidation("invalid evidence relationship")
        span_id = data["evidence_span_id"]
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                _require(conn, "claims", claim_id, "claim")
                _require(conn, "evidence_spans", span_id, "evidence span")
                _insert(
                    conn,
                    "claim_evidence",
                    {
                        "id": new_id("ce"),
                        "claim_id": claim_id,
                        "evidence_span_id": span_id,
                        "relationship": relationship,
                        "created_at": utc_now(),
                    },
                )
        finally:
            conn.close()
        return self.get_claim(claim_id)

    def _audit_revision_tx(
        self,
        conn,
        story_id: str,
        claim_ids: list[str],
        propositions: list[Mapping[str, Any]],
    ) -> str:
        if not claim_ids or len(set(claim_ids)) != len(claim_ids):
            raise DomainValidation("synthesis audit failed: revision requires a unique Claim set")
        rows = conn.execute(
            f"SELECT * FROM claims WHERE story_id = ? AND id IN ({', '.join('?' for _ in claim_ids)})",
            [story_id, *claim_ids],
        ).fetchall()
        found = {row["id"]: row for row in rows}
        missing = [identifier for identifier in claim_ids if identifier not in found]
        if missing:
            raise DomainValidation("synthesis audit failed: unknown Claim citation")
        ineligible = [
            identifier
            for identifier in claim_ids
            if found[identifier]["accepted_at"] is None
            or found[identifier]["state"] not in ACCEPTED_STATES
        ]
        if ineligible:
            raise DomainValidation("synthesis audit failed: revision requires accepted Claims")
        if not propositions:
            raise DomainValidation("synthesis audit failed: every proposition needs citations")
        selected = set(claim_ids)
        for proposition in propositions:
            cited = proposition.get("claim_ids") or []
            if not cited or any(identifier not in selected for identifier in cited):
                raise DomainValidation("synthesis audit failed: unsupported proposition citation")
        return claim_set_hash(claim_ids)

    def _create_revision_tx(self, conn, story_id: str, data: Mapping[str, Any]) -> tuple[str, str]:
        _require(conn, "stories", story_id, "story", live=True)
        claim_ids = list(data.get("claim_ids") or [])
        propositions = list(data.get("propositions") or [])
        computed_hash = self._audit_revision_tx(conn, story_id, claim_ids, propositions)
        next_number = conn.execute(
            "SELECT COALESCE(MAX(revision_number), 0) + 1 FROM story_revisions WHERE story_id = ?",
            (story_id,),
        ).fetchone()[0]
        revision_id = new_id("rev")
        now = utc_now()
        _insert(
            conn,
            "story_revisions",
            {
                "id": revision_id,
                "story_id": story_id,
                "revision_number": next_number,
                "headline": str(data["headline"]).strip(),
                "headline_normalized": normalized_text(str(data["headline"])),
                "summary": data.get("summary", ""),
                "why_it_matters": data.get("why_it_matters", ""),
                "material_change": int(data.get("material_change", False)),
                "claim_set_hash": computed_hash,
                "created_at": now,
            },
        )
        for position, claim_id in enumerate(claim_ids):
            _insert(
                conn,
                "story_revision_claims",
                {"revision_id": revision_id, "claim_id": claim_id, "position": position},
            )
        conn.execute("UPDATE stories SET updated_at = ? WHERE id = ?", (now, story_id))
        return revision_id, computed_hash

    def _revision_result(self, conn, row: sqlite3.Row) -> dict[str, Any]:
        result = _as_dict(row)
        result["claim_ids"] = [
            item[0]
            for item in conn.execute(
                "SELECT claim_id FROM story_revision_claims WHERE revision_id = ? ORDER BY position",
                (result["id"],),
            ).fetchall()
        ]
        result["audit"] = {
            "passed": True,
            "unsupported_propositions": 0,
            "claim_set_hash": result["claim_set_hash"],
        }
        return result

    def get_story_revisions(self, story_id: str) -> list[dict[str, Any]]:
        conn = storage.connect(self.db_path)
        try:
            _require(conn, "stories", story_id, "story")
            return [
                self._revision_result(conn, row)
                for row in conn.execute(
                    "SELECT * FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC, id DESC",
                    (story_id,),
                ).fetchall()
            ]
        finally:
            conn.close()

    def create_story_revision(self, story_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                revision_id, _ = self._create_revision_tx(conn, story_id, data)
        finally:
            conn.close()
        revision = next(item for item in self.get_story_revisions(story_id) if item["id"] == revision_id)
        story = self.core.get_story(story_id, include_deleted=True)
        story["current_revision"] = revision
        story["revision"] = revision
        story["audit"] = revision["audit"]
        return story

    def get_story_evidence(self, story_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            story = _require(conn, "stories", story_id, "story")
            claims = [
                self._claim_result(conn, row)
                for row in conn.execute(
                    "SELECT * FROM claims WHERE story_id = ? ORDER BY created_at, id", (story_id,)
                ).fetchall()
            ]
            revisions = [
                self._revision_result(conn, row)
                for row in conn.execute(
                    "SELECT * FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC, id DESC",
                    (story_id,),
                ).fetchall()
            ]
            return {"story": _as_dict(story), "claims": claims, "revisions": revisions}
        finally:
            conn.close()

    def _create_source_tx(self, conn, data: Mapping[str, Any]) -> str:
        identifier = new_id("src")
        try:
            homepage_url = normalize_url(data["homepage_url"]) if data.get("homepage_url") else None
            feed_url = normalize_url(data["feed_url"]) if data.get("feed_url") else None
            slug = normalized_slug(str(data["slug"]))
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        domain = data.get("domain") or (parse_url(homepage_url)["domain"] if homepage_url else None)
        now = utc_now()
        _insert(
            conn,
            "sources",
            {
                "id": identifier,
                "name": str(data["name"]).strip(),
                "slug": slug,
                "domain": domain,
                "homepage_url": homepage_url,
                "feed_url": feed_url,
                "source_kind": data.get("source_kind", "web"),
                "default_quality": data.get("default_quality", "unknown"),
                "created_at": now,
                "updated_at": now,
            },
        )
        return identifier

    def _create_document_tx(self, conn, source_id: str, data: Mapping[str, Any]) -> str:
        identifier = new_id("doc")
        try:
            canonical_url = normalize_url(str(data["canonical_url"]))
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        now = utc_now()
        _require(conn, "sources", source_id, "source", live=True)
        _insert(
            conn,
            "documents",
            {
                "id": identifier,
                "source_id": source_id,
                "canonical_url": canonical_url,
                "canonical_url_hash": url_fingerprint(canonical_url),
                "title": str(data["title"]).strip(),
                "title_normalized": normalized_text(str(data["title"])),
                "published_at": data.get("published_at"),
                "first_seen_at": now,
                "created_at": now,
            },
        )
        return identifier

    def _create_story_tx(self, conn, data: Mapping[str, Any]) -> str:
        identifier = new_id("st")
        revision_id = new_id("rev")
        now = utc_now()
        headline = str(data["headline"]).strip()
        _insert(
            conn,
            "stories",
            {
                "id": identifier,
                "lifecycle": data.get("lifecycle", "developing"),
                "created_at": now,
                "updated_at": now,
            },
        )
        _insert(
            conn,
            "story_revisions",
            {
                "id": revision_id,
                "story_id": identifier,
                "revision_number": 1,
                "headline": headline,
                "headline_normalized": normalized_text(headline),
                "summary": data.get("summary", ""),
                "why_it_matters": data.get("why_it_matters", ""),
                "material_change": int(data.get("material_change", False)),
                "claim_set_hash": None,
                "created_at": now,
            },
        )
        _insert(conn, "story_review", {"story_id": identifier, "updated_at": now})
        return identifier

    def _create_span_tx(self, conn, document_version_id: str, data: Mapping[str, Any]) -> str:
        excerpt = str(data["excerpt"]).strip()
        if not excerpt:
            raise DomainValidation("excerpt must not be empty")
        locator_type = data.get("locator_type")
        locator_value = data.get("locator_value")
        span_hash = evidence_span_hash(excerpt, locator_type, locator_value)
        existing = conn.execute(
            "SELECT id FROM evidence_spans WHERE document_version_id = ? AND span_hash = ?",
            (document_version_id, span_hash),
        ).fetchone()
        if existing is not None:
            return existing[0]
        identifier = new_id("span")
        _insert(
            conn,
            "evidence_spans",
            {
                "id": identifier,
                "document_version_id": document_version_id,
                "excerpt": excerpt,
                "locator_type": locator_type,
                "locator_value": locator_value,
                "span_hash": span_hash,
                "created_at": utc_now(),
            },
        )
        return identifier

    def _link_evidence_tx(self, conn, claim_id: str, span_id: str, relationship: str) -> None:
        _insert(
            conn,
            "claim_evidence",
            {
                "id": new_id("ce"),
                "claim_id": claim_id,
                "evidence_span_id": span_id,
                "relationship": relationship,
                "created_at": utc_now(),
            },
        )

    def run_manual(self, data: Mapping[str, Any]) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        source_id: str
        document_id: str
        version_id: str
        story_id: str
        claim_ids: list[str] = []
        revision_id: str | None = None
        try:
            with storage.write_tx(conn):
                source_id = data.get("source_id") or self._create_source_tx(conn, data["source"])
                _require(conn, "sources", source_id, "source", live=True)
                document_id = data.get("document_id") or self._create_document_tx(
                    conn, source_id, data["document"]
                )
                document = _require(conn, "documents", document_id, "document")
                if document["source_id"] != source_id:
                    raise DomainValidation("document does not belong to the selected source")
                version_data = data["document_version"]
                version_id = new_id("dv")
                normalized_json = version_data.get("normalized_json")
                if normalized_json is not None and not isinstance(normalized_json, str):
                    normalized_json = json.dumps(normalized_json, sort_keys=True, separators=(",", ":"))
                content_hash = str(version_data["content_hash"]).strip()
                if not content_hash:
                    raise DomainValidation("content_hash must not be empty")
                if normalized_json is not None and len(normalized_json) > 20000:
                    raise DomainValidation("normalized_json exceeds max length 20000")
                _insert(
                    conn,
                    "document_versions",
                    {
                        "id": version_id,
                        "document_id": document_id,
                        "retrieved_at": version_data.get("retrieved_at") or utc_now(),
                        "content_hash": content_hash,
                        "content_kind": version_data.get("content_kind", "metadata"),
                        "locator_type": version_data.get("locator_type"),
                        "locator_value": version_data.get("locator_value"),
                        "normalized_json": normalized_json,
                        "etag": version_data.get("etag"),
                        "last_modified": version_data.get("last_modified"),
                        "created_at": utc_now(),
                    },
                )
                if data.get("story_id"):
                    story_id = data["story_id"]
                    _require(conn, "stories", story_id, "story", live=True)
                    resolution = "existing"
                else:
                    story_data = dict(data.get("story") or {})
                    story_data.setdefault("headline", data["document"]["title"])
                    story_id = self._create_story_tx(conn, story_data)
                    resolution = "new"
                for claim_data in data["claims"]:
                    claim_id = self._create_claim_tx(conn, story_id, claim_data)
                    for evidence_data in claim_data.get("evidence", []):
                        span_id = self._create_span_tx(conn, version_id, evidence_data)
                        self._link_evidence_tx(conn, claim_id, span_id, evidence_data["relationship"])
                    state = claim_data.get("state", "pending")
                    if state != "pending":
                        self._set_claim_state_tx(conn, claim_id, state, "manual fixture assessment")
                    if claim_data.get("accept"):
                        self._accept_claim_tx(conn, claim_id)
                    claim_ids.append(claim_id)
                revision_data = data.get("revision")
                if revision_data is not None:
                    revision_claim_indexes = revision_data.get("claim_indexes") or []
                    if any(index < 0 or index >= len(claim_ids) for index in revision_claim_indexes):
                        raise DomainValidation("revision claim index is out of range")
                    revision = dict(revision_data)
                    revision["claim_ids"] = [claim_ids[index] for index in revision_claim_indexes]
                    revision["propositions"] = [
                        {
                            "text": proposition["text"],
                            "claim_ids": [claim_ids[index] for index in proposition.get("claim_indexes", [])],
                        }
                        for proposition in revision_data.get("propositions", [])
                    ]
                    revision_id, _ = self._create_revision_tx(conn, story_id, revision)
        finally:
            conn.close()
        result = {
            "resolution": resolution,
            "source": self.core.get_source(source_id),
            "document": self.core.get_document(document_id),
            "document_version": self.get_document_version(version_id),
            "story": self.core.get_story(story_id, include_deleted=True),
            "claims": [self.get_claim(identifier) for identifier in claim_ids],
            "revision": None,
        }
        if revision_id is not None:
            revision = next(item for item in self.get_story_revisions(story_id) if item["id"] == revision_id)
            result["revision"] = revision
        return result
