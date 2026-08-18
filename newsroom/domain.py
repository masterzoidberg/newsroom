"""Transactional services for the user-managed Phase 03 domain."""
from __future__ import annotations

import re
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from . import storage
from .url_norm import normalize_url, parse_url, url_fingerprint


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class DomainNotFound(DomainError):
    status_code = 404
    code = "not_found"


class DomainConflict(DomainError):
    status_code = 409
    code = "conflict"


class DomainValidation(DomainError):
    status_code = 422
    code = "validation_error"


SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SENSITIVE_SETTING_RE = re.compile(
    r"(?:password|secret|token|api[_-]?key|private|credential)", re.IGNORECASE
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(16)}"


def normalized_text(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def normalized_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug or len(slug) > 120 or not SLUG_RE.fullmatch(slug):
        raise DomainValidation("slug must contain lowercase letters, numbers, and hyphens")
    return slug


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class CoreService:
    """One-service boundary for short-lived SQLite transactions."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _require(self, conn, table: str, identifier: str, label: str, *, live: bool = False):
        condition = "id = ?"
        params: list[object] = [identifier]
        if live:
            condition += " AND deleted_at IS NULL"
        row = conn.execute(
            f"SELECT * FROM {table} WHERE {condition}", params
        ).fetchone()
        if row is None:
            raise DomainNotFound(f"{label} not found")
        return row

    def _list(
        self,
        table: str,
        columns: str,
        *,
        where: Iterable[str] = (),
        params: Iterable[object] = (),
        order_by: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("page must be >= 1 and page_size must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            clauses = list(where)
            query_params = list(params)
            predicate = " AND ".join(clauses) if clauses else "1 = 1"
            total = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {predicate}", query_params
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT {columns} FROM {table} WHERE {predicate} "
                f"ORDER BY {order_by} LIMIT ? OFFSET ?",
                [*query_params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [_as_dict(row) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    @staticmethod
    def _q_filter(q: Optional[str], fields: tuple[str, ...]) -> tuple[str, list[str]]:
        if not q:
            return "", []
        value = f"%{normalized_text(q)}%"
        return "(" + " OR ".join(f"LOWER({field}) LIKE ?" for field in fields) + ")", [value] * len(fields)

    def _insert(self, conn, table: str, values: Mapping[str, object]) -> None:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        try:
            conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("resource already exists or violates a relationship") from exc

    def _update(self, conn, table: str, identifier: str, values: Mapping[str, object]) -> None:
        if not values:
            raise DomainValidation("at least one field must be supplied")
        assignments = ", ".join(f"{column} = ?" for column in values)
        try:
            result = conn.execute(
                f"UPDATE {table} SET {assignments} WHERE id = ?",
                [*values.values(), identifier],
            )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("resource already exists or violates a relationship") from exc
        if result.rowcount != 1:
            raise DomainNotFound("resource not found")

    def _soft_delete(self, table: str, identifier: str) -> None:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute(
                    f"SELECT 1 FROM {table} WHERE id = ? AND deleted_at IS NULL", (identifier,)
                ).fetchone() is None:
                    raise DomainNotFound("resource not found")
                conn.execute(
                    f"UPDATE {table} SET deleted_at = ?, updated_at = ? WHERE id = ?",
                    (utc_now(), utc_now(), identifier),
                )
        finally:
            conn.close()

    def create_category(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("cat")
        now = utc_now()
        values = {
            "id": identifier,
            "slug": normalized_slug(data["slug"]),
            "name": data["name"].strip(),
            "description": data.get("description", ""),
            "display_order": data.get("display_order", 0),
            "enabled": int(data.get("enabled", True)),
            "priority": data.get("priority", "normal"),
            "max_stories_per_run": data.get("max_stories_per_run"),
            "created_at": now,
            "updated_at": now,
        }
        if not values["name"]:
            raise DomainValidation("name must not be empty")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._insert(conn, "categories", values)
        finally:
            conn.close()
        return self.get_category(identifier, include_deleted=True)

    def list_categories(self, *, q=None, slug=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if slug:
            clauses.append("slug = ?")
            params.append(normalized_slug(slug))
        query, query_params = self._q_filter(q, ("name", "slug"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "categories",
            "id, slug, name, description, display_order, enabled, priority, max_stories_per_run, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="display_order ASC, slug ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_category(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "categories", identifier, "category", live=not include_deleted))
        finally:
            conn.close()

    def update_category(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "display_order", "enabled", "priority", "max_stories_per_run"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "name" in values:
            values["name"] = values["name"].strip()
            if not values["name"]:
                raise DomainValidation("name must not be empty")
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "categories", identifier, "category", live=True)
                self._update(conn, "categories", identifier, values)
        finally:
            conn.close()
        return self.get_category(identifier, include_deleted=True)

    def delete_category(self, identifier: str) -> None:
        self._soft_delete("categories", identifier)

    def create_topic(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("top")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                category = self._require(conn, "categories", data["category_id"], "category")
                if category["deleted_at"] is not None:
                    raise DomainConflict("category is deleted")
                self._insert(
                    conn,
                    "topics",
                    {
                        "id": identifier,
                        "category_id": data["category_id"],
                        "slug": normalized_slug(data["slug"]),
                        "name": data["name"].strip(),
                        "description": data.get("description", ""),
                        "enabled": int(data.get("enabled", True)),
                        "priority": data.get("priority", "normal"),
                        "max_queries_per_run": data.get("max_queries_per_run"),
                        "max_stories_per_run": data.get("max_stories_per_run"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_topic(identifier, include_deleted=True)

    def list_topics(self, *, category_id=None, q=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if category_id:
            clauses.append("category_id = ?")
            params.append(category_id)
        query, query_params = self._q_filter(q, ("name", "slug"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "topics",
            "id, category_id, slug, name, description, enabled, priority, max_queries_per_run, max_stories_per_run, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="name COLLATE NOCASE ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_topic(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "topics", identifier, "topic", live=not include_deleted))
        finally:
            conn.close()

    def update_topic(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"name", "description", "enabled", "priority", "max_queries_per_run", "max_stories_per_run"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "name" in values:
            values["name"] = values["name"].strip()
            if not values["name"]:
                raise DomainValidation("name must not be empty")
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "topics", identifier, "topic", live=True)
                self._update(conn, "topics", identifier, values)
        finally:
            conn.close()
        return self.get_topic(identifier, include_deleted=True)

    def delete_topic(self, identifier: str) -> None:
        self._soft_delete("topics", identifier)

    def create_vocabulary(self, topic_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("term")
        term = data["term"].strip()
        if not term:
            raise DomainValidation("term must not be empty")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "topics", topic_id, "topic", live=True)
                self._insert(
                    conn,
                    "topic_terms",
                    {
                        "id": identifier,
                        "topic_id": topic_id,
                        "term": term,
                        "term_normalized": normalized_text(term),
                        "term_type": data.get("term_type", "include"),
                        "weight": data.get("weight", 1.0),
                        "created_at": now,
                        "concept_kind": data.get("concept_kind", "term"),
                    },
                )
        finally:
            conn.close()
        # A direct user vocabulary edit is an explicit scope change. Persist it
        # for existing topic monitors without making pending AI suggestions active.
        from .monitoring import MonitorService
        MonitorService(self.db_path).refresh_topic_scopes(topic_id, change_type="manual")
        return self.get_vocabulary_item(identifier)

    def get_vocabulary_item(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM topic_terms WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("vocabulary term not found")
            return _as_dict(row)
        finally:
            conn.close()

    def list_vocabulary(self, topic_id: str, *, page=1, page_size=100):
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "topics", topic_id, "topic", live=True)
        finally:
            conn.close()
        return self._list(
            "topic_terms",
            "id, topic_id, term, term_normalized, term_type, weight, concept_kind, created_at",
            where=["topic_id = ?"],
            params=[topic_id],
            order_by="term_type ASC, concept_kind ASC, term_normalized ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def list_scope_suggestions(self, topic_id: str, *, page=1, page_size=25):
        conn = storage.connect(self.db_path)
        try:
            self._require(conn, "topics", topic_id, "topic", live=True)
        finally:
            conn.close()
        return self._list(
            "topic_scope_suggestions",
            "id, topic_id, suggestion_type, value, value_normalized, rationale, source, status, created_at, reviewed_at, reviewed_by",
            where=["topic_id = ?"],
            params=[topic_id],
            order_by="created_at DESC, id DESC",
            page=page,
            page_size=page_size,
        )

    def create_scope_suggestion(self, topic_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        suggestion_type = data["suggestion_type"]
        value = data["value"].strip()
        if not value:
            raise DomainValidation("suggestion value must not be empty")
        identifier = new_id("scope")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "topics", topic_id, "topic", live=True)
                self._insert(
                    conn,
                    "topic_scope_suggestions",
                    {
                        "id": identifier,
                        "topic_id": topic_id,
                        "suggestion_type": suggestion_type,
                        "value": value,
                        "value_normalized": normalized_text(value),
                        "rationale": data.get("rationale", ""),
                        "source": data.get("source", "ai"),
                        "status": "pending",
                        "created_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_scope_suggestion(identifier)

    def get_scope_suggestion(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM topic_scope_suggestions WHERE id = ?", (identifier,)
            ).fetchone()
            if row is None:
                raise DomainNotFound("scope suggestion not found")
            return _as_dict(row)
        finally:
            conn.close()

    def review_scope_suggestion(self, identifier: str, *, approved: bool, reviewed_by: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute(
                    "SELECT * FROM topic_scope_suggestions WHERE id = ?", (identifier,)
                ).fetchone()
                if row is None:
                    raise DomainNotFound("scope suggestion not found")
                if row[7] != "pending":
                    raise DomainConflict("scope suggestion has already been reviewed")
                now = utc_now()
                if approved:
                    mapping = {
                        "term": ("include", "term"),
                        "alias": ("alias", "term"),
                        "acronym": ("alias", "acronym"),
                        "related_concept": ("include", "related_concept"),
                        "exclude": ("exclude", "term"),
                    }
                    term_type, concept_kind = mapping[row[2]]
                    self._insert(
                        conn,
                        "topic_terms",
                        {
                            "id": new_id("term"),
                            "topic_id": row[1],
                            "term": row[3],
                            "term_normalized": row[4],
                            "term_type": term_type,
                            "weight": 1.0,
                            "created_at": now,
                            "concept_kind": concept_kind,
                        },
                    )
                conn.execute(
                    "UPDATE topic_scope_suggestions SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                    ("approved" if approved else "rejected", now, reviewed_by, identifier),
                )
        finally:
            conn.close()
        if approved:
            from .monitoring import MonitorService
            MonitorService(self.db_path).refresh_topic_scopes(row[1], changed_by=reviewed_by, change_type="approved")
        return self.get_scope_suggestion(identifier)

    def create_subject(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("sub")
        now = utc_now()
        try:
            canonical_url = normalize_url(data["canonical_url"]) if data.get("canonical_url") else None
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._insert(
                    conn,
                    "subjects",
                    {
                        "id": identifier,
                        "canonical_name": data["canonical_name"].strip(),
                        "subject_type": data["subject_type"],
                        "description": data.get("description", ""),
                        "canonical_url": canonical_url,
                        "canonical_id": data.get("canonical_id"),
                        "enabled": int(data.get("enabled", True)),
                        "priority": data.get("priority", "normal"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                for alias in data.get("aliases", []):
                    alias = alias.strip()
                    if not alias:
                        raise DomainValidation("alias must not be empty")
                    self._insert(
                        conn,
                        "subject_aliases",
                        {
                            "id": new_id("alias"),
                            "subject_id": identifier,
                            "alias": alias,
                            "alias_normalized": normalized_text(alias),
                            "created_at": now,
                        },
                    )
                for topic_id in data.get("topic_ids", []):
                    self._require(conn, "topics", topic_id, "topic", live=True)
                    self._insert(
                        conn,
                        "topic_subjects",
                        {"topic_id": topic_id, "subject_id": identifier},
                    )
        finally:
            conn.close()
        return self.get_subject(identifier, include_deleted=True)

    def list_subjects(self, *, q=None, subject_type=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if subject_type:
            clauses.append("subject_type = ?")
            params.append(subject_type)
        query, query_params = self._q_filter(q, ("canonical_name", "canonical_id"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "subjects",
            "id, canonical_name, subject_type, description, canonical_url, canonical_id, enabled, priority, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="canonical_name COLLATE NOCASE ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_subject(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = self._require(conn, "subjects", identifier, "subject", live=not include_deleted)
            result = _as_dict(row)
            result["aliases"] = [
                item[0]
                for item in conn.execute(
                    "SELECT alias FROM subject_aliases WHERE subject_id = ? ORDER BY alias_normalized, id",
                    (identifier,),
                )
            ]
            return result
        finally:
            conn.close()

    def update_subject(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"canonical_name", "description", "canonical_url", "canonical_id", "enabled", "priority"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "canonical_name" in values:
            values["canonical_name"] = values["canonical_name"].strip()
        if "canonical_url" in values and values["canonical_url"]:
            try:
                values["canonical_url"] = normalize_url(values["canonical_url"])
            except ValueError as exc:
                raise DomainValidation(str(exc)) from exc
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "subjects", identifier, "subject", live=True)
                self._update(conn, "subjects", identifier, values)
        finally:
            conn.close()
        return self.get_subject(identifier, include_deleted=True)

    def add_subject_alias(self, identifier: str, alias: str) -> dict[str, Any]:
        alias = alias.strip()
        if not alias:
            raise DomainValidation("alias must not be empty")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "subjects", identifier, "subject", live=True)
                self._insert(
                    conn,
                    "subject_aliases",
                    {
                        "id": new_id("alias"),
                        "subject_id": identifier,
                        "alias": alias,
                        "alias_normalized": normalized_text(alias),
                        "created_at": utc_now(),
                    },
                )
        finally:
            conn.close()
        return self.get_subject(identifier, include_deleted=True)

    def delete_subject(self, identifier: str) -> None:
        self._soft_delete("subjects", identifier)

    def create_source(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("src")
        now = utc_now()
        try:
            homepage_url = normalize_url(data["homepage_url"]) if data.get("homepage_url") else None
            feed_url = normalize_url(data["feed_url"]) if data.get("feed_url") else None
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        domain = data.get("domain")
        if not domain and homepage_url:
            domain = parse_url(homepage_url)["domain"]
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._insert(
                    conn,
                    "sources",
                    {
                        "id": identifier,
                        "name": data["name"].strip(),
                        "slug": normalized_slug(data["slug"]),
                        "domain": domain,
                        "homepage_url": homepage_url,
                        "feed_url": feed_url,
                        "source_kind": data.get("source_kind", "web"),
                        "default_quality": data.get("default_quality", "unknown"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_source(identifier, include_deleted=True)

    def list_sources(self, *, q=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        query, query_params = self._q_filter(q, ("name", "slug", "domain"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "sources",
            "id, name, slug, domain, homepage_url, feed_url, source_kind, default_quality, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="name COLLATE NOCASE ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_source(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "sources", identifier, "source", live=not include_deleted))
        finally:
            conn.close()

    def update_source(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        allowed = {"name", "domain", "homepage_url", "feed_url", "source_kind", "default_quality"}
        values = {key: value for key, value in data.items() if key in allowed}
        if "homepage_url" in values and values["homepage_url"]:
            try:
                values["homepage_url"] = normalize_url(values["homepage_url"])
            except ValueError as exc:
                raise DomainValidation(str(exc)) from exc
        if "feed_url" in values and values["feed_url"]:
            try:
                values["feed_url"] = normalize_url(values["feed_url"])
            except ValueError as exc:
                raise DomainValidation(str(exc)) from exc
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "sources", identifier, "source", live=True)
                self._update(conn, "sources", identifier, values)
        finally:
            conn.close()
        return self.get_source(identifier, include_deleted=True)

    def delete_source(self, identifier: str) -> None:
        self._soft_delete("sources", identifier)

    def create_document(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("doc")
        now = utc_now()
        try:
            canonical_url = normalize_url(data["canonical_url"])
        except ValueError as exc:
            raise DomainValidation(str(exc)) from exc
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "sources", data["source_id"], "source", live=True)
                self._insert(
                    conn,
                    "documents",
                    {
                        "id": identifier,
                        "source_id": data["source_id"],
                        "canonical_url": canonical_url,
                        "canonical_url_hash": url_fingerprint(canonical_url),
                        "title": data["title"].strip(),
                        "title_normalized": normalized_text(data["title"]),
                        "published_at": data.get("published_at"),
                        "first_seen_at": now,
                        "created_at": now,
                    },
                )
        finally:
            conn.close()
        return self.get_document(identifier)

    def list_documents(self, *, source_id=None, q=None, page=1, page_size=25):
        clauses: list[str] = []
        params: list[object] = []
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        query, query_params = self._q_filter(q, ("title", "canonical_url"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "documents",
            "id, source_id, canonical_url, canonical_url_hash, title, title_normalized, published_at, first_seen_at, created_at",
            where=clauses,
            params=params,
            order_by="created_at DESC, id DESC",
            page=page,
            page_size=page_size,
        )

    def get_document(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "documents", identifier, "document"))
        finally:
            conn.close()

    def update_document(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in {"title", "published_at"}}
        if "title" in values:
            values["title"] = values["title"].strip()
            values["title_normalized"] = normalized_text(values["title"])
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "documents", identifier, "document")
                self._update(conn, "documents", identifier, values)
        finally:
            conn.close()
        return self.get_document(identifier)

    def update_vocabulary(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in {"term", "term_type", "concept_kind", "weight"}}
        if "term" in values:
            values["term"] = values["term"].strip()
            if not values["term"]:
                raise DomainValidation("term must not be empty")
            values["term_normalized"] = normalized_text(values["term"])
        conn = storage.connect(self.db_path)
        topic_id = None
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT topic_id FROM topic_terms WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("vocabulary term not found")
                topic_id = row[0]
                self._update(conn, "topic_terms", identifier, values)
        finally:
            conn.close()
        from .monitoring import MonitorService
        MonitorService(self.db_path).refresh_topic_scopes(topic_id, change_type="manual")
        return self.get_vocabulary_item(identifier)

    def delete_vocabulary(self, identifier: str) -> None:
        conn = storage.connect(self.db_path)
        topic_id = None
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT topic_id FROM topic_terms WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("vocabulary term not found")
                topic_id = row[0]
                result = conn.execute("DELETE FROM topic_terms WHERE id = ?", (identifier,))
                if result.rowcount != 1:
                    raise DomainNotFound("vocabulary term not found")
        finally:
            conn.close()
        from .monitoring import MonitorService
        MonitorService(self.db_path).refresh_topic_scopes(topic_id, change_type="manual")

    def create_story(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = new_id("st")
        revision_id = new_id("rev")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                for topic_id in data.get("topic_ids", []):
                    self._require(conn, "topics", topic_id, "topic", live=True)
                for subject_id in data.get("subject_ids", []):
                    self._require(conn, "subjects", subject_id, "subject", live=True)
                self._insert(
                    conn,
                    "stories",
                    {
                        "id": identifier,
                        "lifecycle": data.get("lifecycle", "developing"),
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                self._insert(
                    conn,
                    "story_revisions",
                    {
                        "id": revision_id,
                        "story_id": identifier,
                        "revision_number": 1,
                        "headline": data["headline"].strip(),
                        "headline_normalized": normalized_text(data["headline"]),
                        "summary": data.get("summary", ""),
                        "why_it_matters": data.get("why_it_matters", ""),
                        "material_change": int(data.get("material_change", False)),
                        "claim_set_hash": data.get("claim_set_hash"),
                        "created_at": now,
                    },
                )
                self._insert(
                    conn,
                    "story_review",
                    {"story_id": identifier, "updated_at": now},
                )
                for topic_id in data.get("topic_ids", []):
                    self._insert(conn, "story_topics", {"story_id": identifier, "topic_id": topic_id})
                for subject_id in data.get("subject_ids", []):
                    self._insert(conn, "story_subjects", {"story_id": identifier, "subject_id": subject_id})
        finally:
            conn.close()
        return self.get_story(identifier, include_deleted=True)

    def list_stories(self, *, q=None, lifecycle=None, include_deleted=False, page=1, page_size=25):
        clauses: list[str] = [] if include_deleted else ["deleted_at IS NULL"]
        params: list[object] = []
        if lifecycle:
            clauses.append("lifecycle = ?")
            params.append(lifecycle)
        if q:
            clauses.append(
                "(LOWER(stories.id) LIKE ? OR EXISTS (SELECT 1 FROM story_revisions WHERE story_revisions.story_id = stories.id AND LOWER(story_revisions.headline) LIKE ?))"
            )
            value = f"%{normalized_text(q)}%"
            params.extend([value, value])
        return self._list(
            "stories",
            "id, lifecycle, created_at, updated_at, deleted_at",
            where=clauses,
            params=params,
            order_by="updated_at DESC, id DESC",
            page=page,
            page_size=page_size,
        )

    def get_story(self, identifier: str, *, include_deleted=False) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = self._require(conn, "stories", identifier, "story", live=not include_deleted)
            result = _as_dict(row)
            revision = conn.execute(
                "SELECT * FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC, id DESC LIMIT 1",
                (identifier,),
            ).fetchone()
            result["current_revision"] = _as_dict(revision)
            review = conn.execute(
                "SELECT * FROM story_review WHERE story_id = ?", (identifier,)
            ).fetchone()
            if review is not None:
                review_result = _as_dict(review)
                reviewed_number = 0
                if review_result["last_reviewed_revision_id"]:
                    reviewed = conn.execute(
                        "SELECT revision_number FROM story_revisions WHERE id = ? AND story_id = ?",
                        (review_result["last_reviewed_revision_id"], identifier),
                    ).fetchone()
                    reviewed_number = reviewed["revision_number"] if reviewed else 0
                review_result["new_update"] = conn.execute(
                    """
                    SELECT 1 FROM story_revisions
                    WHERE story_id = ? AND material_change = 1 AND revision_number > ?
                    LIMIT 1
                    """,
                    (identifier, reviewed_number),
                ).fetchone() is not None
                result["review"] = review_result
            result["subject_ids"] = [
                item[0] for item in conn.execute(
                    "SELECT subject_id FROM story_subjects WHERE story_id = ? ORDER BY subject_id", (identifier,)
                )
            ]
            result["topic_ids"] = [
                item[0] for item in conn.execute(
                    "SELECT topic_id FROM story_topics WHERE story_id = ? ORDER BY topic_id", (identifier,)
                )
            ]
            result["tag_ids"] = [
                item[0] for item in conn.execute(
                    "SELECT tag_id FROM story_tags WHERE story_id = ? ORDER BY tag_id", (identifier,)
                )
            ]
            return result
        finally:
            conn.close()

    def update_story(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in data.items() if key in {"lifecycle"}}
        values["updated_at"] = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "stories", identifier, "story", live=True)
                self._update(conn, "stories", identifier, values)
        finally:
            conn.close()
        return self.get_story(identifier, include_deleted=True)

    def create_story_revision(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        # Keep the legacy service entry point evidence-bound as well as the
        # HTTP route. This prevents callers that still hold CoreService from
        # bypassing the Phase 04 closed-world audit.
        from .evidence import EvidenceService

        return EvidenceService(self.db_path).create_story_revision(identifier, data)

    def delete_story(self, identifier: str) -> None:
        self._soft_delete("stories", identifier)

    def create_tag(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name = data["name"].strip()
        if not name:
            raise DomainValidation("tag name must not be empty")
        namespace = str(data.get("namespace", "user")).strip()
        tag_type = str(data.get("tag_type", "user"))
        if not namespace or len(namespace) > 64 or not re.fullmatch(r"[A-Za-z0-9._:-]+", namespace):
            raise DomainValidation("tag namespace is invalid")
        if tag_type not in {"user", "smart"}:
            raise DomainValidation("tag type must be user or smart")
        identifier = new_id("tag")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._insert(
                    conn,
                    "tags",
                    {
                        "id": identifier,
                        "name": name,
                        "normalized_name": normalized_text(name),
                        "namespace": namespace,
                        "tag_type": tag_type,
                        "created_at": utc_now(),
                    },
                )
        finally:
            conn.close()
        return self.get_tag(identifier)

    def list_tags(self, *, q=None, namespace=None, tag_type=None, page=1, page_size=25):
        clauses: list[str] = []
        params: list[object] = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if tag_type:
            clauses.append("tag_type = ?")
            params.append(tag_type)
        query, query_params = self._q_filter(q, ("name", "normalized_name"))
        if query:
            clauses.append(query)
            params.extend(query_params)
        return self._list(
            "tags",
            "id, name, normalized_name, namespace, tag_type, created_at",
            where=clauses,
            params=params,
            order_by="normalized_name ASC, id ASC",
            page=page,
            page_size=page_size,
        )

    def get_tag(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _as_dict(self._require(conn, "tags", identifier, "tag"))
        finally:
            conn.close()

    def update_tag(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        name = data.get("name", "").strip()
        if not name:
            raise DomainValidation("tag name must not be empty")
        namespace = data.get("namespace")
        tag_type = data.get("tag_type")
        if namespace is not None and (not str(namespace).strip() or not re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", str(namespace).strip())):
            raise DomainValidation("tag namespace is invalid")
        if tag_type is not None and tag_type not in {"user", "smart"}:
            raise DomainValidation("tag type must be user or smart")
        values = {"name": name, "normalized_name": normalized_text(name)}
        if namespace is not None:
            values["namespace"] = str(namespace).strip()
        if tag_type is not None:
            values["tag_type"] = tag_type
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._update(
                    conn,
                    "tags",
                    identifier,
                    values,
                )
        finally:
            conn.close()
        return self.get_tag(identifier)

    def delete_tag(self, identifier: str) -> None:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute("SELECT 1 FROM tags WHERE id = ?", (identifier,)).fetchone() is None:
                    raise DomainNotFound("tag not found")
                if conn.execute("SELECT 1 FROM story_tags WHERE tag_id = ?", (identifier,)).fetchone() is not None:
                    raise DomainConflict("tag is still attached to a story")
                conn.execute("DELETE FROM tags WHERE id = ?", (identifier,))
        finally:
            conn.close()

    def tag_story(self, story_id: str, tag_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require(conn, "stories", story_id, "story", live=True)
                self._require(conn, "tags", tag_id, "tag")
                self._insert(
                    conn,
                    "story_tags",
                    {"story_id": story_id, "tag_id": tag_id, "created_at": utc_now()},
                )
        finally:
            conn.close()
        return self.get_story(story_id, include_deleted=True)

    def set_setting(self, key: str, value: str) -> dict[str, Any]:
        key = key.strip()
        if not key or len(key) > 120 or SENSITIVE_SETTING_RE.search(key):
            raise DomainValidation("setting key is invalid or sensitive")
        if len(value) > 4000:
            raise DomainValidation("setting value is too long")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO settings(key, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )
        finally:
            conn.close()
        return {"key": key, "value": value, "updated_at": now}

    def list_settings(self, *, page=1, page_size=100):
        result = self._list(
            "settings",
            "key, value, updated_at",
            where=[
                "LOWER(key) NOT LIKE '%password%'",
                "LOWER(key) NOT LIKE '%secret%'",
                "LOWER(key) NOT LIKE '%token%'",
                "LOWER(key) NOT LIKE '%api_key%'",
                "LOWER(key) NOT LIKE '%credential%'",
                "LOWER(key) NOT LIKE '%private%'",
            ],
            order_by="key ASC",
            page=page,
            page_size=page_size,
        )
        return result


__all__ = [
    "CoreService",
    "DomainConflict",
    "DomainError",
    "DomainNotFound",
    "DomainValidation",
]
