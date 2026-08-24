"""Canonical Entity and cross-object knowledge services for Phase 26.

Entity metadata is organizational state.  It can improve retrieval and
navigation, but it is never treated as Evidence and never rewrites the
immutable Phase 25 assessment history.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, normalized_text, utc_now


ENTITY_TYPES = frozenset(
    {
        "person", "organization", "agency", "company", "program", "location",
        "event", "legislation", "technology", "publication", "other", "unknown",
    }
)
ALIAS_TYPES = frozenset(
    {"alternate_name", "acronym", "expanded_name", "abbreviation", "former_name", "deterministic"}
)
RELATION_ROLES = frozenset({"subject", "object", "mentioned", "context"})
RELATION_ORIGINS = frozenset({"user", "deterministic", "provider", "import", "backfill"})
TAG_ORIGINS = frozenset({"user", "deterministic", "provider", "import", "backfill"})
TAG_OBJECT_TABLES = {
    "entity": "entities",
    "claim": "claims",
    "evidence": "evidence_spans",
    "document": "documents",
    "story": "stories",
    "research_question": "research_questions",
    "research_gap": "research_question_gaps",
    "research_task": "research_tasks",
    "source": "sources",
    "watch": "watches",
    "article_analysis": "article_analyses",
}


def _page(page: int, page_size: int, maximum: int = 100) -> tuple[int, int, int]:
    if page < 1 or page_size < 1 or page_size > maximum:
        raise DomainValidation(f"page must be >= 1 and page_size must be between 1 and {maximum}")
    return page, page_size, (page - 1) * page_size


def _json(value: Any) -> str:
    try:
        return json.dumps(value if value is not None else {}, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise DomainValidation("mention context must be JSON serializable") from exc


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class KnowledgeService:
    """Own canonical Entity identity, aliases, mentions, and relationships."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _require_entity(self, conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM entities WHERE id = ?", (identifier,)).fetchone()
        if row is None:
            raise DomainNotFound("entity not found")
        return row

    @staticmethod
    def _entity_type(value: Any) -> str:
        result = str(value or "unknown").strip().casefold()
        if result not in ENTITY_TYPES:
            result = "other"
        return result

    @staticmethod
    def _name(value: Any, label: str = "entity name") -> tuple[str, str]:
        name = str(value or "").strip()
        if not name or len(name) > 500:
            raise DomainValidation(f"{label} must be between 1 and 500 characters")
        normalized = normalized_text(name)
        if not normalized:
            raise DomainValidation(f"{label} must contain searchable text")
        return name, normalized

    def create_entity(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name, normalized = self._name(data.get("canonical_name"))
        entity_type = self._entity_type(data.get("entity_type"))
        description = str(data.get("description", "")).strip()
        if len(description) > 5_000:
            raise DomainValidation("entity description is too long")
        now = utc_now()
        aliases = data.get("aliases", ())
        if not isinstance(aliases, (list, tuple)):
            raise DomainValidation("entity aliases must be a list")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = conn.execute("SELECT id FROM entities WHERE normalized_name = ?", (normalized,)).fetchone()
                if existing is not None:
                    identifier = existing[0]
                    for alias in aliases:
                        self._add_alias_tx(conn, identifier, alias, origin=str(data.get("origin", "user")))
                else:
                    identifier = new_id("ent")
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO entities
                            (id, canonical_name, normalized_name, entity_type, description,
                             status, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                        """,
                        (identifier, name, normalized, entity_type, description, now, now),
                    )
                    identifier = conn.execute("SELECT id FROM entities WHERE normalized_name = ?", (normalized,)).fetchone()[0]
                    for alias in aliases:
                        self._add_alias_tx(conn, identifier, alias, origin=str(data.get("origin", "user")))
        finally:
            conn.close()
        return self.get_entity(identifier)

    def create_candidate(self, name: str, *, entity_type: str = "unknown", origin: str = "deterministic") -> dict[str, Any]:
        canonical, normalized = self._name(name)
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                identifier = self._create_candidate_tx(conn, canonical, normalized, entity_type, now)
        finally:
            conn.close()
        return self.get_entity(identifier)

    def _create_candidate_tx(self, conn: sqlite3.Connection, canonical: str, normalized: str, entity_type: str, now: str | None = None) -> str:
        row = conn.execute("SELECT id FROM entities WHERE normalized_name = ?", (normalized,)).fetchone()
        if row is not None:
            return row[0]
        identifier = new_id("ent")
        created_at = now or utc_now()
        conn.execute(
            "INSERT OR IGNORE INTO entities(id, canonical_name, normalized_name, entity_type, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'candidate', ?, ?)",
            (identifier, canonical, normalized, self._entity_type(entity_type), created_at, created_at),
        )
        return conn.execute("SELECT id FROM entities WHERE normalized_name = ?", (normalized,)).fetchone()[0]

    def _add_alias_tx(self, conn: sqlite3.Connection, entity_id: str, data: Any, *, origin: str) -> str:
        if isinstance(data, str):
            alias_value, alias_type = data, "alternate_name"
        elif isinstance(data, Mapping):
            alias_value, alias_type = data.get("alias"), data.get("alias_type", "alternate_name")
            origin = str(data.get("origin", origin))
        else:
            raise DomainValidation("entity alias must be a string or object")
        alias, normalized = self._name(alias_value, "entity alias")
        alias_type = str(alias_type).strip().casefold()
        if alias_type not in ALIAS_TYPES:
            raise DomainValidation("unsupported entity alias type")
        if origin not in {"user", "subject", "watch", "article_analysis", "deterministic", "provider", "import"}:
            raise DomainValidation("unsupported entity alias origin")
        existing = conn.execute(
            "SELECT id FROM entity_aliases WHERE entity_id = ? AND normalized_alias = ?",
            (entity_id, normalized),
        ).fetchone()
        if existing is not None:
            return existing[0]
        identifier = new_id("ealias")
        conn.execute(
            """
            INSERT OR IGNORE INTO entity_aliases
                (id, entity_id, alias, normalized_alias, alias_type, origin, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (identifier, entity_id, alias, normalized, alias_type, origin, utc_now()),
        )
        return conn.execute("SELECT id FROM entity_aliases WHERE entity_id = ? AND normalized_alias = ?", (entity_id, normalized)).fetchone()[0]

    def add_alias(self, entity_id: str, data: Mapping[str, Any] | str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_entity(conn, entity_id)
                identifier = self._add_alias_tx(conn, entity_id, data, origin="user")
        finally:
            conn.close()
        return self.get_alias(identifier)

    def get_alias(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM entity_aliases WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("entity alias not found")
            return dict(row)
        finally:
            conn.close()

    def _resolve_entity_tx(self, conn: sqlite3.Connection, value: str) -> dict[str, Any]:
        _, normalized = self._name(value, "entity lookup")
        canonical = conn.execute(
            "SELECT * FROM entities WHERE normalized_name = ? AND status <> 'merged'",
            (normalized,),
        ).fetchall()
        if canonical:
            return {"status": "resolved", "entity": dict(canonical[0]), "candidates": [dict(canonical[0])], "match_reason": "exact_canonical_name"}
        rows = conn.execute(
            """
            SELECT DISTINCT e.*
            FROM entity_aliases a JOIN entities e ON e.id = a.entity_id
            WHERE a.normalized_alias = ? AND a.status = 'active' AND e.status <> 'merged'
            ORDER BY e.id
            """,
            (normalized,),
        ).fetchall()
        candidates = [dict(row) for row in rows]
        if len(candidates) == 1:
            return {"status": "resolved", "entity": candidates[0], "candidates": candidates, "match_reason": "exact_alias"}
        if candidates:
            return {"status": "ambiguous", "entity": None, "candidates": candidates, "match_reason": "ambiguous_alias"}
        return {"status": "unresolved", "entity": None, "candidates": [], "match_reason": "no_exact_identity"}

    def resolve_entity(self, value: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return self._resolve_entity_tx(conn, value)
        finally:
            conn.close()

    def list_entities(self, *, q: str | None = None, entity_type: str | None = None, status: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        page, page_size, offset = _page(page, page_size)
        clauses = ["1 = 1"]
        params: list[Any] = []
        if q:
            _, normalized = self._name(q, "entity query")
            clauses.append("(e.normalized_name LIKE ? OR EXISTS (SELECT 1 FROM entity_aliases a WHERE a.entity_id = e.id AND a.normalized_alias LIKE ?))")
            params.extend([f"%{normalized}%", f"%{normalized}%"])
        if entity_type:
            if entity_type not in ENTITY_TYPES:
                raise DomainValidation("unsupported entity type")
            clauses.append("e.entity_type = ?")
            params.append(entity_type)
        if status:
            if status not in {"active", "candidate", "merged"}:
                raise DomainValidation("unsupported entity status")
            clauses.append("e.status = ?")
            params.append(status)
        where = " AND ".join(clauses)
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM entities e WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT e.* FROM entities e WHERE {where} ORDER BY e.normalized_name, e.id LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            ).fetchall()
            return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total, "has_more": offset + len(rows) < total}
        finally:
            conn.close()

    def record_mention(self, data: Mapping[str, Any]) -> dict[str, Any]:
        mention, normalized = self._name(data.get("mention_text"), "mention text")
        source_type = str(data.get("source_type", "unknown")).strip()
        if source_type not in {"article_analysis", "document_version", "claim", "manual", "unknown"}:
            raise DomainValidation("unsupported entity mention source type")
        source_id = data.get("source_id")
        entity_id = data.get("entity_id")
        resolution_status = str(data.get("resolution_status", "resolved" if entity_id else "unresolved"))
        resolution_method = str(data.get("resolution_method", "deterministic" if entity_id else "unresolved"))
        if resolution_status not in {"resolved", "unresolved", "ambiguous"}:
            raise DomainValidation("unsupported entity mention resolution status")
        if resolution_method not in {"user", "deterministic", "provider", "unresolved"}:
            raise DomainValidation("unsupported entity mention resolution method")
        if entity_id is None and resolution_status == "resolved":
            raise DomainValidation("resolved entity mention requires an entity")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if entity_id is not None:
                    self._require_entity(conn, str(entity_id))
                existing = conn.execute(
                    "SELECT id FROM entity_mentions WHERE source_type = ? AND source_id IS ? AND normalized_mention = ?",
                    (source_type, source_id, normalized),
                ).fetchone()
                if existing is not None:
                    identifier = existing[0]
                else:
                    identifier = new_id("mention")
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO entity_mentions
                            (id, entity_id, mention_text, normalized_mention, source_type,
                             source_id, article_analysis_id, document_version_id,
                             resolution_status, resolution_method, confidence,
                             context_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            identifier, entity_id, mention, normalized, source_type, source_id,
                            data.get("article_analysis_id") or (source_id if source_type == "article_analysis" else None),
                            data.get("document_version_id") or (source_id if source_type == "document_version" else None),
                            resolution_status, resolution_method, data.get("confidence"),
                            _json(data.get("context")), utc_now(),
                        ),
                    )
                    identifier = conn.execute(
                        "SELECT id FROM entity_mentions WHERE source_type = ? AND source_id IS ? AND normalized_mention = ?",
                        (source_type, source_id, normalized),
                    ).fetchone()[0]
        finally:
            conn.close()
        return self.get_mention(identifier)

    def get_mention(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM entity_mentions WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("entity mention not found")
            result = dict(row)
            result["context"] = json.loads(result.pop("context_json") or "{}")
            return result
        finally:
            conn.close()

    def link_claim_entity(self, claim_id: str, entity_id: str, *, role: str = "mentioned", origin: str = "deterministic", mention_id: str | None = None) -> dict[str, Any]:
        if role not in RELATION_ROLES or origin not in RELATION_ORIGINS:
            raise DomainValidation("unsupported Claim-Entity relationship")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute("SELECT 1 FROM claims WHERE id = ?", (claim_id,)).fetchone() is None:
                    raise DomainNotFound("claim not found")
                self._require_entity(conn, entity_id)
                if mention_id is not None and conn.execute("SELECT 1 FROM entity_mentions WHERE id = ?", (mention_id,)).fetchone() is None:
                    raise DomainNotFound("entity mention not found")
                conn.execute(
                    "INSERT OR IGNORE INTO claim_entities(claim_id, entity_id, role, origin, mention_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (claim_id, entity_id, role, origin, mention_id, utc_now()),
                )
                story = conn.execute("SELECT story_id FROM claims WHERE id = ?", (claim_id,)).fetchone()
                if story and story[0]:
                    conn.execute(
                        "INSERT OR IGNORE INTO story_entities(story_id, entity_id, origin, authority, created_at) VALUES (?, ?, ?, 'derived', ?)",
                        (story[0], entity_id, origin, utc_now()),
                    )
        finally:
            conn.close()
        return {"claim_id": claim_id, "entity_id": entity_id, "role": role, "origin": origin, "mention_id": mention_id}

    def link_research_question_entity(self, question_id: str, entity_id: str, *, origin: str = "deterministic") -> dict[str, Any]:
        return self._link_pair("research_question_entities", "question_id", question_id, "research_questions", entity_id, origin)

    def link_gap_entity(self, gap_id: str, entity_id: str, *, origin: str = "deterministic") -> dict[str, Any]:
        return self._link_pair("research_gap_entities", "gap_id", gap_id, "research_question_gaps", entity_id, origin)

    def link_task_entity(self, task_id: str, entity_id: str, *, origin: str = "deterministic") -> dict[str, Any]:
        return self._link_pair("research_task_entities", "task_id", task_id, "research_tasks", entity_id, origin)

    def link_watch_entity(self, watch_id: str, entity_id: str, *, origin: str = "deterministic") -> dict[str, Any]:
        return self._link_pair("watch_entities", "watch_id", watch_id, "watches", entity_id, origin)

    def create_tag(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name, normalized = self._name(data.get("name"), "tag name")
        if len(name) > 100:
            raise DomainValidation("tag name must be at most 100 characters")
        namespace = str(data.get("namespace", "user")).strip()
        tag_type = str(data.get("tag_type", "user")).strip()
        if not namespace or len(namespace) > 64:
            raise DomainValidation("tag namespace is invalid")
        if tag_type not in {"user", "smart"}:
            raise DomainValidation("tag type must be user or smart")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = conn.execute("SELECT id FROM tags WHERE namespace = ? AND normalized_name = ?", (namespace, normalized)).fetchone()
                if existing is not None:
                    identifier = existing[0]
                else:
                    identifier = new_id("tag")
                    conn.execute(
                        "INSERT OR IGNORE INTO tags(id, name, normalized_name, namespace, tag_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (identifier, name, normalized, namespace, tag_type, utc_now()),
                    )
                    identifier = conn.execute("SELECT id FROM tags WHERE namespace = ? AND normalized_name = ?", (namespace, normalized)).fetchone()[0]
        finally:
            conn.close()
        return self.get_tag(identifier)

    def _require_object(self, conn: sqlite3.Connection, object_type: str, object_id: str) -> None:
        table = TAG_OBJECT_TABLES.get(object_type)
        if table is None:
            raise DomainValidation("unsupported tag object type")
        condition = " AND deleted_at IS NULL" if table in {"stories", "subjects", "research_questions", "topics", "sources"} else ""
        if conn.execute(f"SELECT 1 FROM {table} WHERE id = ?{condition}", (object_id,)).fetchone() is None:
            raise DomainNotFound(f"{object_type} not found")

    def assign_tag(self, tag_id: str, object_type: str, object_id: str, *, origin: str = "user", confidence: float | None = None, reason: str = "") -> dict[str, Any]:
        if origin not in TAG_ORIGINS:
            raise DomainValidation("unsupported tag assignment origin")
        if confidence is not None and not 0 <= float(confidence) <= 1:
            raise DomainValidation("tag assignment confidence must be between 0 and 1")
        if len(reason) > 2_000:
            raise DomainValidation("tag assignment reason is too long")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute("SELECT 1 FROM tags WHERE id = ?", (tag_id,)).fetchone() is None:
                    raise DomainNotFound("tag not found")
                self._require_object(conn, object_type, object_id)
                identifier = new_id("tagassign")
                conn.execute(
                    "INSERT OR IGNORE INTO tag_assignments(id, tag_id, object_type, object_id, origin, confidence, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (identifier, tag_id, object_type, object_id, origin, confidence, reason, utc_now()),
                )
                identifier = conn.execute("SELECT id FROM tag_assignments WHERE tag_id = ? AND object_type = ? AND object_id = ?", (tag_id, object_type, object_id)).fetchone()[0]
                if object_type == "story":
                    conn.execute("INSERT OR IGNORE INTO story_tags(story_id, tag_id, created_at) VALUES (?, ?, ?)", (object_id, tag_id, utc_now()))
        finally:
            conn.close()
        return self.get_assignment(identifier)

    def get_assignment(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT ta.*, t.name, t.namespace, t.tag_type FROM tag_assignments ta JOIN tags t ON t.id = ta.tag_id WHERE ta.id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("tag assignment not found")
            return dict(row)
        finally:
            conn.close()

    def get_tag(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM tags WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("tag not found")
            result = dict(row)
            result["assignments"] = [dict(item) for item in conn.execute("SELECT * FROM tag_assignments WHERE tag_id = ? ORDER BY created_at DESC, id DESC LIMIT 100", (identifier,))]
            return result
        finally:
            conn.close()

    def list_tags(self, *, q: str | None = None, namespace: str | None = None, tag_type: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        page, page_size, offset = _page(page, page_size)
        clauses = ["1 = 1"]
        params: list[Any] = []
        if q:
            clauses.append("(name LIKE ? OR normalized_name LIKE ?)")
            params.extend([f"%{q.strip()}%", f"%{normalized_text(q)}%"])
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if tag_type:
            clauses.append("tag_type = ?")
            params.append(tag_type)
        where = " AND ".join(clauses)
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM tags WHERE {where}", params).fetchone()[0]
            rows = conn.execute(f"SELECT * FROM tags WHERE {where} ORDER BY normalized_name, id LIMIT ? OFFSET ?", [*params, page_size, offset]).fetchall()
            return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total, "has_more": offset + len(rows) < total}
        finally:
            conn.close()

    def deterministic_tags(self, object_type: str, object_id: str) -> list[dict[str, Any]]:
        conn = storage.connect(self.db_path)
        try:
            self._require_object(conn, object_type, object_id)
            suggestions: list[tuple[str, str]] = []
            if object_type == "entity":
                row = conn.execute("SELECT entity_type FROM entities WHERE id = ?", (object_id,)).fetchone()
                if row:
                    suggestions.append((f"entity:{row[0]}", "canonical entity type"))
            elif object_type == "source":
                row = conn.execute("SELECT source_kind FROM sources WHERE id = ?", (object_id,)).fetchone()
                if row:
                    suggestions.append((f"source:{row[0]}", "persisted Source class"))
            elif object_type == "claim":
                row = conn.execute("SELECT state, importance FROM claims WHERE id = ?", (object_id,)).fetchone()
                if row and row[0] == "disputed":
                    suggestions.append(("evidence:contradictory", "Claim state is disputed"))
                if row and row[1] == "major":
                    suggestions.append(("priority:major", "Claim importance is major"))
            elif object_type == "research_question":
                row = conn.execute("SELECT assessment_state FROM research_questions WHERE id = ?", (object_id,)).fetchone()
                if row:
                    suggestions.append((f"assessment:{row[0]}", "Phase 25 evidence assessment"))
                if conn.execute("SELECT 1 FROM research_question_gaps WHERE question_id = ? AND status IN ('open','pursuing') LIMIT 1", (object_id,)).fetchone():
                    suggestions.append(("research:open-gap", "durable Evidence Gap remains open"))
            suggestions = suggestions[:5]
        finally:
            conn.close()
        output = []
        for name, reason in suggestions:
            tag = self.create_tag({"name": name, "namespace": "smart", "tag_type": "smart"})
            output.append(self.assign_tag(tag["id"], object_type, object_id, origin="deterministic", reason=reason))
        return output

    def start_backfill(self, kind: str, *, row_limit: int = 500, batch_size: int = 25) -> dict[str, Any]:
        if kind not in {"article_analysis_entities", "smart_tags"}:
            raise DomainValidation("unsupported knowledge backfill kind")
        if not 1 <= row_limit <= 10_000 or not 1 <= batch_size <= 100:
            raise DomainValidation("knowledge backfill bounds are invalid")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = conn.execute(
                    "SELECT * FROM knowledge_backfills WHERE kind = ? AND status IN ('queued','running') ORDER BY id LIMIT 1",
                    (kind,),
                ).fetchone()
                if existing is not None:
                    return dict(existing)
                identifier = new_id("backfill")
                now = utc_now()
                conn.execute(
                    "INSERT INTO knowledge_backfills(id, kind, status, row_limit, batch_size, created_at, updated_at) VALUES (?, ?, 'queued', ?, ?, ?, ?)",
                    (identifier, kind, row_limit, batch_size, now, now),
                )
        finally:
            conn.close()
        return self.get_backfill(identifier)

    def get_backfill(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM knowledge_backfills WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("knowledge backfill not found")
            return dict(row)
        finally:
            conn.close()

    def run_backfill(self, identifier: str) -> dict[str, Any]:
        run = self.get_backfill(identifier)
        if run["status"] in {"completed", "failed", "cancelled"}:
            return run
        self._update_backfill(identifier, status="running")
        processed = int(run["processed"])
        cursor = run["cursor"]
        try:
            while processed < int(run["row_limit"]):
                conn = storage.connect(self.db_path)
                try:
                    if run["kind"] == "article_analysis_entities":
                        rows = conn.execute(
                            "SELECT id FROM article_analyses WHERE (? IS NULL OR id > ?) ORDER BY id LIMIT ?",
                            (cursor, cursor, min(int(run["batch_size"]), int(run["row_limit"]) - processed)),
                        ).fetchall()
                    else:
                        rows = conn.execute(
                            "SELECT id FROM entities WHERE status = 'active' AND (? IS NULL OR id > ?) ORDER BY id LIMIT ?",
                            (cursor, cursor, min(int(run["batch_size"]), int(run["row_limit"]) - processed)),
                        ).fetchall()
                finally:
                    conn.close()
                if not rows:
                    return self._update_backfill(identifier, status="completed", cursor=cursor, processed=processed, completed_at=utc_now())
                for row in rows:
                    if run["kind"] == "article_analysis_entities":
                        self.index_article_analysis(row[0])
                    else:
                        self.deterministic_tags("entity", row[0])
                    cursor = row[0]
                    processed += 1
                    self._update_backfill(identifier, cursor=cursor, processed=processed)
            return self._update_backfill(identifier, status="completed", cursor=cursor, processed=processed, completed_at=utc_now())
        except Exception as exc:
            return self._update_backfill(identifier, status="failed", cursor=cursor, processed=processed, error_code=type(exc).__name__, error_detail=str(exc)[:500], completed_at=utc_now())

    def _update_backfill(self, identifier: str, **values: Any) -> dict[str, Any]:
        values["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(f"UPDATE knowledge_backfills SET {assignments} WHERE id = ?", [*values.values(), identifier])
        finally:
            conn.close()
        return self.get_backfill(identifier)

    def _subject_resolution(self, conn: sqlite3.Connection, value: str) -> list[sqlite3.Row]:
        normalized = normalized_text(value)
        return conn.execute(
            """
            SELECT DISTINCT s.*
            FROM subjects s
            LEFT JOIN subject_aliases sa ON sa.subject_id = s.id
            WHERE s.deleted_at IS NULL
              AND (LOWER(s.canonical_name) = LOWER(?) OR LOWER(COALESCE(s.canonical_id, '')) = LOWER(?) OR LOWER(COALESCE(sa.alias, '')) = LOWER(?))
            """,
            (normalized, normalized, normalized),
        ).fetchall()

    def _resolve_or_import_subject(self, conn: sqlite3.Connection, value: str) -> tuple[dict[str, Any] | None, str]:
        candidates = self._subject_resolution(conn, value)
        if len(candidates) != 1:
            return None, "ambiguous_subject" if candidates else "no_subject_identity"
        subject = candidates[0]
        entity_row = conn.execute(
            "SELECT * FROM entities WHERE normalized_name = ?",
            (normalized_text(subject["canonical_name"]),),
        ).fetchone()
        if entity_row is None:
            now = utc_now()
            entity_id = new_id("ent")
            conn.execute(
                "INSERT OR IGNORE INTO entities(id, canonical_name, normalized_name, entity_type, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
                (entity_id, subject["canonical_name"], normalized_text(subject["canonical_name"]), self._entity_type(subject["subject_type"]), subject["description"] or "", now, now),
            )
            entity_id = conn.execute("SELECT id FROM entities WHERE normalized_name = ?", (normalized_text(subject["canonical_name"]),)).fetchone()[0]
        else:
            entity_id = entity_row["id"]
        self._add_alias_tx(conn, entity_id, {"alias": subject["canonical_name"], "alias_type": "alternate_name", "origin": "subject"}, origin="subject")
        if subject["canonical_id"]:
            self._add_alias_tx(conn, entity_id, {"alias": subject["canonical_id"], "alias_type": "abbreviation", "origin": "subject"}, origin="subject")
        for alias in conn.execute("SELECT alias FROM subject_aliases WHERE subject_id = ? ORDER BY id", (subject["id"],)):
            self._add_alias_tx(conn, entity_id, {"alias": alias[0], "alias_type": "alternate_name", "origin": "subject"}, origin="subject")
        return dict(conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()), "subject_identity"

    def index_article_analysis(self, analysis_id: str) -> dict[str, Any]:
        """Resolve ArticleAnalysis entity proposals without touching Evidence/Claims."""
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                analysis = conn.execute("SELECT * FROM article_analyses WHERE id = ?", (analysis_id,)).fetchone()
                if analysis is None:
                    raise DomainNotFound("article analysis not found")
                try:
                    payload = json.loads(analysis["result_json"] or "{}")
                except json.JSONDecodeError as exc:
                    raise DomainValidation("article analysis result is not valid JSON") from exc
                raw_entities = payload.get("entities", []) if isinstance(payload, Mapping) else []
                if not isinstance(raw_entities, list) or len(raw_entities) > 100:
                    raise DomainValidation("article analysis entity output is invalid")
                resolved: list[dict[str, Any]] = []
                for index, raw in enumerate(raw_entities):
                    if not isinstance(raw, Mapping):
                        continue
                    name = str(raw.get("name", "")).strip()
                    if not name:
                        continue
                    entity_type = self._entity_type(raw.get("category"))
                    identity = self._resolve_entity_tx(conn, name)
                    entity = identity.get("entity")
                    resolution_status = identity["status"]
                    resolution_method = "deterministic"
                    reason = identity.get("match_reason", "")
                    if entity is None and resolution_status == "unresolved":
                        entity, reason = self._resolve_or_import_subject(conn, name)
                        if entity is not None:
                            resolution_status = "resolved"
                        else:
                            canonical, normalized = self._name(name)
                            candidate_id = self._create_candidate_tx(conn, canonical, normalized, entity_type)
                            entity = dict(conn.execute("SELECT * FROM entities WHERE id = ?", (candidate_id,)).fetchone())
                            resolution_status = "unresolved"
                            resolution_method = "unresolved"
                    mention = self._record_mention_tx(
                        conn,
                        mention_text=name,
                        entity_id=entity["id"] if entity is not None and resolution_status != "ambiguous" else None,
                        source_type="article_analysis",
                        source_id=analysis_id,
                        article_analysis_id=analysis_id,
                        document_version_id=analysis["document_version_id"],
                        resolution_status=resolution_status,
                        resolution_method=resolution_method,
                        confidence=raw.get("confidence"),
                        context={"entity_index": index, "match_reason": reason},
                    )
                    resolved.append({"name": name, "entity_id": entity["id"] if entity is not None and resolution_status != "ambiguous" else None, "mention_id": mention["id"], "status": resolution_status, "match_reason": reason})
                claim_links = 0
                claims = conn.execute("SELECT id, proposition, story_id FROM claims WHERE article_analysis_id = ? ORDER BY id", (analysis_id,)).fetchall()
                for claim in claims:
                    proposition = normalized_text(claim["proposition"]).casefold()
                    for item in resolved:
                        entity_id = item.get("entity_id")
                        if entity_id and normalized_text(item["name"]).casefold() in proposition:
                            self._link_claim_entity_tx(conn, claim["id"], entity_id, role="mentioned", origin="deterministic", mention_id=item["mention_id"])
                            claim_links += 1
                question_links = 0
                for claim in claims:
                    for question in conn.execute("SELECT question_id FROM research_question_claims WHERE claim_id = ?", (claim["id"],)):
                        for item in resolved:
                            if item.get("entity_id") and normalized_text(item["name"]).casefold() in normalized_text(claim["proposition"]).casefold():
                                self._link_pair_tx(conn, "research_question_entities", "question_id", question[0], "research_questions", item["entity_id"], "deterministic")
                                question_links += 1
                return {"analysis_id": analysis_id, "entities": resolved, "claim_links": claim_links, "question_links": question_links}
        finally:
            conn.close()

    def _record_mention_tx(self, conn: sqlite3.Connection, *, mention_text: str, entity_id: str | None, source_type: str, source_id: str | None, article_analysis_id: str | None, document_version_id: str | None, resolution_status: str, resolution_method: str, confidence: Any, context: Mapping[str, Any]) -> dict[str, Any]:
        _, normalized = self._name(mention_text, "mention text")
        existing = conn.execute("SELECT * FROM entity_mentions WHERE source_type = ? AND source_id IS ? AND normalized_mention = ?", (source_type, source_id, normalized)).fetchone()
        if existing is not None:
            return self._mention_row(existing)
        identifier = new_id("mention")
        conn.execute(
            "INSERT OR IGNORE INTO entity_mentions(id, entity_id, mention_text, normalized_mention, source_type, source_id, article_analysis_id, document_version_id, resolution_status, resolution_method, confidence, context_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (identifier, entity_id, mention_text, normalized, source_type, source_id, article_analysis_id, document_version_id, resolution_status, resolution_method, confidence, _json(context), utc_now()),
        )
        return self._mention_row(conn.execute("SELECT * FROM entity_mentions WHERE source_type = ? AND source_id IS ? AND normalized_mention = ?", (source_type, source_id, normalized)).fetchone())

    def _link_claim_entity_tx(self, conn: sqlite3.Connection, claim_id: str, entity_id: str, *, role: str, origin: str, mention_id: str | None) -> None:
        conn.execute("INSERT OR IGNORE INTO claim_entities(claim_id, entity_id, role, origin, mention_id, created_at) VALUES (?, ?, ?, ?, ?, ?)", (claim_id, entity_id, role, origin, mention_id, utc_now()))
        story = conn.execute("SELECT story_id FROM claims WHERE id = ?", (claim_id,)).fetchone()
        if story and story[0]:
            conn.execute("INSERT OR IGNORE INTO story_entities(story_id, entity_id, origin, authority, created_at) VALUES (?, ?, ?, 'derived', ?)", (story[0], entity_id, origin, utc_now()))

    def _link_pair_tx(self, conn: sqlite3.Connection, relation_table: str, left_column: str, left_id: str, left_table: str, entity_id: str, origin: str) -> None:
        conn.execute(
            f"INSERT OR IGNORE INTO {relation_table}({left_column}, entity_id, origin, created_at) VALUES (?, ?, ?, ?)",
            (left_id, entity_id, origin, utc_now()),
        )

    def _link_pair(self, relation_table: str, left_column: str, left_id: str, left_table: str, entity_id: str, origin: str) -> dict[str, Any]:
        if origin not in RELATION_ORIGINS:
            raise DomainValidation("unsupported Entity relationship origin")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute(f"SELECT 1 FROM {left_table} WHERE id = ?", (left_id,)).fetchone() is None:
                    raise DomainNotFound("related object not found")
                self._require_entity(conn, entity_id)
                conn.execute(
                    f"INSERT OR IGNORE INTO {relation_table}({left_column}, entity_id, origin, created_at) VALUES (?, ?, ?, ?)",
                    (left_id, entity_id, origin, utc_now()),
                )
        finally:
            conn.close()
        return {left_column: left_id, "entity_id": entity_id, "origin": origin}

    def get_entity(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            entity = self._require_entity(conn, identifier)
            result = dict(entity)
            result["aliases"] = [dict(row) for row in conn.execute("SELECT * FROM entity_aliases WHERE entity_id = ? AND status = 'active' ORDER BY normalized_alias, id LIMIT 100", (identifier,))]
            result["mentions"] = [self._mention_row(row) for row in conn.execute("SELECT * FROM entity_mentions WHERE entity_id = ? ORDER BY created_at DESC, id DESC LIMIT 100", (identifier,))]
            result["claims"] = self._claim_rows(conn, identifier)
            result["stories"] = [dict(row) for row in conn.execute(
                """
                SELECT s.* FROM stories s
                WHERE s.deleted_at IS NULL AND s.id IN (
                    SELECT story_id FROM story_entities WHERE entity_id = ? AND authority = 'manual'
                    UNION
                    SELECT c.story_id FROM claims c JOIN claim_entities ce ON ce.claim_id = c.id
                    WHERE ce.entity_id = ? AND c.story_id IS NOT NULL
                )
                ORDER BY s.updated_at DESC, s.id DESC LIMIT 100
                """,
                (identifier, identifier),
            )]
            result["research_questions"] = [dict(row) for row in conn.execute("SELECT q.id, q.question, q.status, q.assessment_state, q.assessment_explanation FROM research_question_entities qe JOIN research_questions q ON q.id = qe.question_id WHERE qe.entity_id = ? AND q.deleted_at IS NULL ORDER BY q.updated_at DESC, q.id DESC LIMIT 100", (identifier,))]
            result["gaps"] = [dict(row) for row in conn.execute("SELECT g.* FROM research_gap_entities ge JOIN research_question_gaps g ON g.id = ge.gap_id WHERE ge.entity_id = ? ORDER BY g.updated_at DESC, g.id DESC LIMIT 100", (identifier,))]
            result["tasks"] = [dict(row) for row in conn.execute("SELECT t.id, t.question_id, t.gap_id, t.status, t.mode, t.created_at, t.updated_at FROM research_task_entities te JOIN research_tasks t ON t.id = te.task_id WHERE te.entity_id = ? ORDER BY t.updated_at DESC, t.id DESC LIMIT 100", (identifier,))]
            result["watches"] = [dict(row) for row in conn.execute("SELECT w.* FROM watch_entities we JOIN watches w ON w.id = we.watch_id WHERE we.entity_id = ? ORDER BY w.updated_at DESC, w.id DESC LIMIT 100", (identifier,))]
            result["tags"] = [dict(row) for row in conn.execute("SELECT t.*, ta.object_type, ta.object_id, ta.origin AS assignment_origin, ta.reason FROM tag_assignments ta JOIN tags t ON t.id = ta.tag_id WHERE ta.object_type = 'entity' AND ta.object_id = ? ORDER BY t.normalized_name, t.id LIMIT 100", (identifier,))] if self._table_exists(conn, "tag_assignments") else []
            result["sources"] = self._sources_for_entity(conn, identifier)
            result["evidence"] = [item for claim in result["claims"] for item in claim.get("evidence", [])][:100]
            return result
        finally:
            conn.close()

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None

    @staticmethod
    def _mention_row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["context"] = json.loads(result.pop("context_json") or "{}")
        return result

    @staticmethod
    def _claim_rows(conn: sqlite3.Connection, entity_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT c.id, c.proposition, c.importance, c.state, c.story_id,
                   ce.role, ce.origin, ce.mention_id
            FROM claim_entities ce JOIN claims c ON c.id = ce.claim_id
            WHERE ce.entity_id = ? ORDER BY c.created_at DESC, c.id DESC LIMIT 100
            """,
            (entity_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["evidence"] = [dict(evidence) for evidence in conn.execute(
                """
                SELECT es.id, es.excerpt, es.locator_type, es.locator_value,
                       dv.id AS document_version_id, d.id AS document_id,
                       d.title AS document_title, d.source_id, s.name AS source_name
                FROM claims c JOIN claim_evidence ce ON ce.claim_id = c.id
                JOIN evidence_spans es ON es.id = ce.evidence_span_id
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE c.id = ? ORDER BY es.id LIMIT 100
                """,
                (row["id"],),
            )]
            result.append(item)
        return result

    @staticmethod
    def _sources_for_entity(conn: sqlite3.Connection, entity_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in conn.execute(
            """
            SELECT DISTINCT s.id, s.name, s.slug, s.domain
            FROM claim_entities ce JOIN claims c ON c.id = ce.claim_id
            JOIN claim_evidence cl ON cl.claim_id = c.id
            JOIN evidence_spans es ON es.id = cl.evidence_span_id
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id
            JOIN sources s ON s.id = d.source_id
            WHERE ce.entity_id = ? ORDER BY s.name, s.id LIMIT 100
            """,
            (entity_id,),
        )]


__all__ = ["ALIAS_TYPES", "ENTITY_TYPES", "KnowledgeService", "RELATION_ORIGINS", "RELATION_ROLES"]
