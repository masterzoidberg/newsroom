"""Bounded search, comparison, context, and operational diagnostics."""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import storage
from .domain import (
    DomainConflict,
    DomainNotFound,
    DomainValidation,
    CoreService,
    new_id,
    normalized_text,
    utc_now,
)
from .integrity import check_database


ENTITY_TYPES = (
    "monitor",
    "source",
    "document",
    "story",
    "subject",
    "claim",
    "evidence",
    "tag",
    "question",
    "note",
)
OBJECT_TABLES = {
    "story": ("stories", "id", "deleted_at"),
    "subject": ("subjects", "id", "deleted_at"),
    "document": ("documents", "id", None),
    "claim": ("claims", "id", None),
    "monitor": ("monitors", "id", None),
    "research_question": ("research_questions", "id", "deleted_at"),
}
_TOKEN_RE = re.compile(r"[\w]+(?:[-'][\w]+)*", re.UNICODE)
_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?)\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"(?<![\w])(?:[$€£]\s*)?\d[\d,]*(?:\.\d+)?\s*%?(?![\w])")


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _page(page: int, page_size: int, *, maximum: int = 100) -> tuple[int, int, int]:
    if page < 1 or page_size < 1 or page_size > maximum:
        raise DomainValidation(f"page must be >= 1 and page_size must be between 1 and {maximum}")
    return page, page_size, (page - 1) * page_size


def _safe_fts_query(value: str) -> str:
    if not isinstance(value, str) or len(value) > 500:
        raise DomainValidation("search query must be a string of at most 500 characters")
    tokens = _TOKEN_RE.findall(value)
    if not tokens:
        raise DomainValidation("search query must contain at least one searchable term")
    # Quote every token. This deliberately treats MATCH operators, wildcards,
    # and punctuation as literal user input instead of executable FTS syntax.
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens[:50])


def _append_record(records: list[dict[str, Any]], *, entity_type: str, entity_id: str, title: str, body: str = "", created_at: str | None = None, **filters: Any) -> None:
    records.append(
        {
            "id": f"{entity_type}:{entity_id}",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "title": str(title or "").strip() or entity_id,
            "body": str(body or "").strip(),
            "created_at": created_at or "1970-01-01T00:00:00Z",
            **filters,
        }
    )


class SearchService:
    """Rebuild a small FTS5 projection from authoritative SQLite state per query."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _records(self, conn: sqlite3.Connection) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        titles: dict[tuple[str, str], str] = {}

        for row in conn.execute("SELECT * FROM sources WHERE deleted_at IS NULL ORDER BY id"):
            title = row["name"]
            titles[("source", row["id"])] = title
            _append_record(
                records,
                entity_type="source",
                entity_id=row["id"],
                title=title,
                body=" ".join(filter(None, (row["slug"], row["domain"], row["source_kind"], row["default_quality"]))),
                created_at=row["created_at"],
                source_id=row["id"],
            )

        for row in conn.execute("SELECT * FROM subjects WHERE deleted_at IS NULL ORDER BY id"):
            aliases = " ".join(item[0] for item in conn.execute("SELECT alias FROM subject_aliases WHERE subject_id = ? ORDER BY id", (row["id"],)))
            title = row["canonical_name"]
            titles[("subject", row["id"])] = title
            _append_record(
                records,
                entity_type="subject",
                entity_id=row["id"],
                title=title,
                body=" ".join(filter(None, (row["description"], row["canonical_id"], aliases))),
                created_at=row["created_at"],
                subject_id=row["id"],
            )

        for row in conn.execute(
            """
            SELECT d.*, s.name AS source_name
            FROM documents d JOIN sources s ON s.id = d.source_id
            WHERE s.deleted_at IS NULL ORDER BY d.id
            """
        ):
            title = row["title"]
            titles[("document", row["id"])] = title
            _append_record(
                records,
                entity_type="document",
                entity_id=row["id"],
                title=title,
                body=" ".join(filter(None, (row["canonical_url"], row["source_name"], row["published_at"]))),
                created_at=row["created_at"],
                source_id=row["source_id"],
            )

        story_subjects: dict[str, list[str]] = defaultdict(list)
        for row in conn.execute(
            "SELECT ss.story_id, s.canonical_name FROM story_subjects ss JOIN subjects s ON s.id = ss.subject_id WHERE s.deleted_at IS NULL ORDER BY ss.story_id, s.id"
        ):
            story_subjects[row["story_id"]].append(row["canonical_name"])
        story_tags: dict[str, list[str]] = defaultdict(list)
        for row in conn.execute(
            "SELECT st.story_id, t.name FROM story_tags st JOIN tags t ON t.id = st.tag_id ORDER BY st.story_id, t.id"
        ):
            story_tags[row["story_id"]].append(row["name"])
        for row in conn.execute(
            """
            SELECT s.*, r.headline, r.summary, r.why_it_matters
            FROM stories s
            LEFT JOIN story_revisions r ON r.id = (
                SELECT r2.id FROM story_revisions r2
                WHERE r2.story_id = s.id ORDER BY r2.revision_number DESC, r2.id DESC LIMIT 1
            )
            WHERE s.deleted_at IS NULL ORDER BY s.id
            """
        ):
            title = row["headline"] or row["id"]
            titles[("story", row["id"])] = title
            body = " ".join(filter(None, (row["summary"], row["why_it_matters"], row["lifecycle"], *story_subjects[row["id"]], *story_tags[row["id"]])))
            _append_record(records, entity_type="story", entity_id=row["id"], title=title, body=body, created_at=row["created_at"], story_id=row["id"], lifecycle=row["lifecycle"])

        for row in conn.execute("SELECT * FROM tags ORDER BY id"):
            title = row["name"]
            titles[("tag", row["id"])] = title
            _append_record(
                records,
                entity_type="tag",
                entity_id=row["id"],
                title=title,
                body=" ".join(filter(None, (row["namespace"], row["tag_type"], row["normalized_name"]))),
                created_at=row["created_at"],
                tag_id=row["id"],
            )

        for row in conn.execute("SELECT * FROM research_questions WHERE deleted_at IS NULL ORDER BY id"):
            title = row["question"]
            titles[("question", row["id"])] = title
            _append_record(records, entity_type="question", entity_id=row["id"], title=title, body=" ".join(filter(None, (row["status"], row["priority"], row["resolution_note"]))), created_at=row["created_at"], question_id=row["id"], state=row["status"])

        for row in conn.execute(
            """
            SELECT m.*, p.name AS policy_name
            FROM monitors m JOIN monitoring_policies p ON p.id = m.policy_id
            ORDER BY m.id
            """
        ):
            target_title = titles.get((row["target_type"], row["target_id"]), row["target_id"])
            _append_record(records, entity_type="monitor", entity_id=row["id"], title=f"{row['target_type']}: {target_title}", body=" ".join(filter(None, (row["policy_name"], row["last_result"], row["target_type"], row["target_id"]))), created_at=row["created_at"], monitor_id=row["id"], state=row["last_result"])

        indexed_claims: set[str] = set()
        for row in conn.execute(
            """
            SELECT c.*, s.headline, d.id AS document_id, d.title AS document_title
            FROM claims c
            LEFT JOIN stories st ON st.id = c.story_id AND st.deleted_at IS NULL
            LEFT JOIN story_revisions s ON s.id = (
                SELECT s2.id FROM story_revisions s2 WHERE s2.story_id = st.id ORDER BY s2.revision_number DESC, s2.id DESC LIMIT 1
            )
            LEFT JOIN claim_evidence ce ON ce.claim_id = c.id
            LEFT JOIN evidence_spans es ON es.id = ce.evidence_span_id
            LEFT JOIN document_versions dv ON dv.id = es.document_version_id
            LEFT JOIN documents d ON d.id = dv.document_id
            ORDER BY c.id, d.id
            """
        ):
            if row["id"] in indexed_claims:
                continue
            indexed_claims.add(row["id"])
            _append_record(records, entity_type="claim", entity_id=row["id"], title=row["proposition"], body=" ".join(filter(None, (row["state"], row["importance"], row["headline"], row["document_title"]))), created_at=row["created_at"], story_id=row["story_id"], state=row["state"])

        for row in conn.execute(
            """
            SELECT es.*, dv.document_id, d.title AS document_title, d.source_id, s.name AS source_name
            FROM evidence_spans es
            JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id
            JOIN sources s ON s.id = d.source_id AND s.deleted_at IS NULL
            ORDER BY es.id
            """
        ):
            _append_record(records, entity_type="evidence", entity_id=row["id"], title=row["document_title"], body=" ".join(filter(None, (row["excerpt"], row["source_name"], row["locator_type"], row["locator_value"]))), created_at=row["created_at"], source_id=row["source_id"], document_id=row["document_id"])

        for row in conn.execute(
            """
            SELECT n.*, q.question
            FROM notes n LEFT JOIN research_questions q ON q.id = n.object_id AND n.object_type = 'research_question'
            ORDER BY n.id
            """
        ):
            object_title = titles.get(("question", row["object_id"]), row["object_id"])
            _append_record(records, entity_type="note", entity_id=row["id"], title=f"{row['note_type']}: {object_title}", body=row["body"], created_at=row["created_at"], story_id=row["object_id"] if row["object_type"] == "story" else None, subject_id=row["object_id"] if row["object_type"] == "subject" else None, question_id=row["object_id"] if row["object_type"] == "research_question" else None, state=row["note_type"])

        for row in conn.execute("SELECT * FROM research_question_notes ORDER BY id"):
            object_title = titles.get(("question", row["question_id"]), row["question_id"])
            _append_record(records, entity_type="note", entity_id=f"research-question:{row['id']}", title=f"{row['note_type']}: {object_title}", body=row["body"], created_at=row["created_at"], question_id=row["question_id"], state=row["note_type"])
        return records

    def _rebuild(self, conn: sqlite3.Connection) -> None:
        records = self._records(conn)
        conn.execute("DELETE FROM search_fts")
        conn.execute("DELETE FROM search_records")
        for record in records:
            columns = ("id", "entity_type", "entity_id", "title", "body", "source_id", "story_id", "subject_id", "monitor_id", "question_id", "tag_id", "document_id", "state", "lifecycle", "created_at")
            conn.execute(f"INSERT INTO search_records ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", tuple(record.get(column) for column in columns))
        conn.execute(
            """
            INSERT INTO search_fts(rowid, entity_type, entity_id, title, body)
            SELECT rowid, entity_type, entity_id, title, body FROM search_records
            """
        )
        conn.execute("UPDATE search_index_meta SET dirty = 0, updated_at = ? WHERE id = 1", (utc_now(),))

    def _ensure_index(self, conn: sqlite3.Connection) -> None:
        dirty = conn.execute("SELECT dirty FROM search_index_meta WHERE id = 1").fetchone()
        if dirty is not None and dirty[0] == 0:
            return
        with storage.write_tx(conn):
            self._rebuild(conn)

    def search(
        self,
        query: str,
        *,
        entity_types: Sequence[str] | None = None,
        source_id: str | None = None,
        story_id: str | None = None,
        subject_id: str | None = None,
        monitor_id: str | None = None,
        question_id: str | None = None,
        tag_id: str | None = None,
        document_id: str | None = None,
        state: str | None = None,
        lifecycle: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        page, page_size, offset = _page(page, page_size)
        match = _safe_fts_query(query)
        types = list(entity_types or [])
        invalid = sorted(set(types) - set(ENTITY_TYPES))
        if invalid:
            raise DomainValidation(f"unsupported search entity type: {', '.join(invalid)}")
        conn = storage.connect(self.db_path)
        try:
            self._ensure_index(conn)
            clauses = ["search_fts MATCH ?"]
            params: list[Any] = [match]
            if types:
                clauses.append(f"r.entity_type IN ({', '.join('?' for _ in types)})")
                params.extend(types)
            for column, value in (("source_id", source_id), ("story_id", story_id), ("subject_id", subject_id), ("monitor_id", monitor_id), ("question_id", question_id), ("tag_id", tag_id), ("document_id", document_id), ("state", state), ("lifecycle", lifecycle)):
                if value is not None:
                    clauses.append(f"r.{column} = ?")
                    params.append(value)
            if date_from is not None:
                clauses.append("r.created_at >= ?")
                params.append(date_from)
            if date_to is not None:
                clauses.append("r.created_at <= ?")
                params.append(date_to)
            where = " AND ".join(clauses)
            total = conn.execute(f"SELECT COUNT(*) FROM search_fts JOIN search_records r ON r.rowid = search_fts.rowid WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT r.*, bm25(search_fts, 1.0, 0.6) AS score
                FROM search_fts JOIN search_records r ON r.rowid = search_fts.rowid
                WHERE {where}
                ORDER BY score ASC, r.entity_type ASC, r.entity_id ASC
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, offset],
            ).fetchall()
            items: list[dict[str, Any]] = []
            for row in rows:
                item = _as_dict(row) or {}
                item["snippet"] = (f"{item['title']} {item['body']}".strip())[:280]
                item.pop("id", None)
                items.append(item)
            return {"items": items, "page": page, "page_size": page_size, "total": total, "has_more": offset + len(items) < total, "ranking": "bm25_then_entity_type_then_entity_id"}
        except sqlite3.OperationalError as exc:
            raise DomainValidation("search query could not be evaluated") from exc
        finally:
            conn.close()


def _placeholders(values: Sequence[str]) -> str:
    return ", ".join("?" for _ in values)


def _extract_values(text: str) -> tuple[list[str], list[str]]:
    dates = sorted(set(match.group(0) for match in _DATE_RE.finditer(text)), key=str.casefold)
    without_dates = _DATE_RE.sub(" ", text)
    numbers = sorted(set(match.group(0).strip() for match in _NUMBER_RE.finditer(without_dates)), key=str.casefold)
    return dates, numbers


def _value_key(text: str) -> str:
    value = _DATE_RE.sub(" ", text)
    value = _NUMBER_RE.sub(" ", value)
    return normalized_text(value).casefold()


class ComparisonService:
    """Compare a bounded set of Documents using only stored Claims and Evidence."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def compare(self, document_ids: Sequence[str], *, story_id: str | None = None) -> dict[str, Any]:
        ids = list(dict.fromkeys(document_ids))
        if len(ids) < 2 or len(ids) > 20:
            raise DomainValidation("comparison requires between 2 and 20 distinct documents")
        conn = storage.connect(self.db_path)
        try:
            rows = conn.execute(
                f"""
                SELECT d.*, s.name AS source_name, s.source_kind, s.default_quality
                FROM documents d JOIN sources s ON s.id = d.source_id
                WHERE d.id IN ({_placeholders(ids)})
                """,
                ids,
            ).fetchall()
            by_id = {row["id"]: row for row in rows}
            missing = [identifier for identifier in ids if identifier not in by_id]
            if missing:
                raise DomainNotFound(f"document not found: {missing[0]}")
            evidence_rows = conn.execute(
                f"""
                SELECT c.id AS claim_id, c.story_id, c.proposition, c.importance, c.state,
                       ce.relationship, es.id AS evidence_span_id, es.excerpt,
                       es.locator_type, es.locator_value, d.id AS document_id,
                       d.title AS document_title, d.published_at, s.name AS source_name
                FROM claims c
                JOIN claim_evidence ce ON ce.claim_id = c.id
                JOIN evidence_spans es ON es.id = ce.evidence_span_id
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE d.id IN ({_placeholders(ids)})
                  AND (? IS NULL OR c.story_id = ?)
                ORDER BY c.id, d.id, es.id
                """,
                [*ids, story_id, story_id],
            ).fetchall()
            claim_docs: dict[str, set[str]] = defaultdict(set)
            claim_rows: dict[str, list[sqlite3.Row]] = defaultdict(list)
            for row in evidence_rows:
                claim_docs[row["claim_id"]].add(row["document_id"])
                claim_rows[row["claim_id"]].append(row)

            def claim_item(claim_id: str, rows_for_claim: list[sqlite3.Row]) -> dict[str, Any]:
                first = rows_for_claim[0]
                return {
                    "claim_id": claim_id,
                    "claim_ids": [claim_id],
                    "story_id": first["story_id"],
                    "proposition": first["proposition"],
                    "importance": first["importance"],
                    "state": first["state"],
                    "document_ids": sorted({row["document_id"] for row in rows_for_claim}),
                    "evidence_span_ids": sorted({row["evidence_span_id"] for row in rows_for_claim}),
                    "evidence": [
                        {
                            "id": row["evidence_span_id"],
                            "document_id": row["document_id"],
                            "excerpt": row["excerpt"],
                            "locator_type": row["locator_type"],
                            "locator_value": row["locator_value"],
                            "relationship": row["relationship"],
                        }
                        for row in rows_for_claim
                    ],
                }

            shared_claims = [claim_item(identifier, claim_rows[identifier]) for identifier in sorted(claim_rows) if len(claim_docs[identifier]) > 1]
            unique_claims = [claim_item(identifier, claim_rows[identifier]) for identifier in sorted(claim_rows) if len(claim_docs[identifier]) == 1]

            claims_by_story: dict[str | None, list[str]] = defaultdict(list)
            for identifier, rows_for_claim in claim_rows.items():
                claims_by_story[rows_for_claim[0]["story_id"]].append(identifier)
            contradictions: list[dict[str, Any]] = []
            for group_story_id, claim_ids in sorted(
                claims_by_story.items(), key=lambda item: (item[0] is not None, item[0] or "")
            ):
                group_rows = [row for identifier in claim_ids for row in claim_rows[identifier]]
                explicit = any(row["relationship"] == "contradicts" for row in group_rows)
                signatures = {_value_key(row["proposition"]) for row in group_rows}
                different_values = len(signatures) > 1 and any(_extract_values(row["proposition"])[0] or _extract_values(row["proposition"])[1] for row in group_rows)
                if explicit or different_values:
                    contradictions.append(
                        {
                            "story_id": group_story_id,
                            "claim_ids": sorted(set(claim_ids)),
                            "propositions": sorted({row["proposition"] for row in group_rows}),
                            "evidence_span_ids": sorted({row["evidence_span_id"] for row in group_rows}),
                            "document_ids": sorted({row["document_id"] for row in group_rows}),
                            "reason": "explicit contradictory evidence" if explicit else "different date or number assertions",
                        }
                    )

            per_document: list[dict[str, Any]] = []
            date_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            number_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for identifier in ids:
                document_claims = [row for row in evidence_rows if row["document_id"] == identifier]
                dates: set[str] = set()
                numbers: set[str] = set()
                for row in document_claims:
                    row_dates, row_numbers = _extract_values(row["proposition"])
                    row_dates += _DATE_RE.findall(row["excerpt"])
                    row_numbers += [match.group(0).strip() for match in _NUMBER_RE.finditer(_DATE_RE.sub(" ", row["excerpt"]))]
                    dates.update(row_dates)
                    numbers.update(row_numbers)
                    base = _value_key(row["proposition"])
                    if row_dates:
                        date_groups[base].append({"document_id": identifier, "values": sorted(set(row_dates)), "claim_id": row["claim_id"], "evidence_span_ids": [row["evidence_span_id"]]})
                    if row_numbers:
                        number_groups[base].append({"document_id": identifier, "values": sorted(set(row_numbers)), "claim_id": row["claim_id"], "evidence_span_ids": [row["evidence_span_id"]]})
                per_document.append({"document_id": identifier, "dates": sorted(dates), "numbers": sorted(numbers)})

            def differences(groups: Mapping[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
                result = []
                for base, items in sorted(groups.items()):
                    values = sorted({value for item in items for value in item["values"]})
                    documents = sorted({item["document_id"] for item in items})
                    if len(values) > 1 and len(documents) > 1:
                        result.append({"assertion": base, "values": values, "observations": items})
                return result

            lineage_rows = conn.execute(
                f"""
                SELECT dl.* FROM document_lineage dl
                WHERE dl.document_id IN ({_placeholders(ids)}) OR dl.parent_document_id IN ({_placeholders(ids)})
                ORDER BY dl.document_id, dl.parent_document_id, dl.relationship, dl.id
                """,
                [*ids, *ids],
            ).fetchall()
            lineage = [_as_dict(row) for row in lineage_rows]
            primary_source_use = [
                {
                    "document_id": identifier,
                    "source_id": by_id[identifier]["source_id"],
                    "source_name": by_id[identifier]["source_name"],
                    "source_kind": by_id[identifier]["source_kind"],
                    "default_quality": by_id[identifier]["default_quality"],
                    "is_primary": by_id[identifier]["default_quality"] == "primary" or by_id[identifier]["source_kind"] == "official",
                    "supporting_evidence_ids": sorted({row["evidence_span_id"] for row in evidence_rows if row["document_id"] == identifier and row["relationship"] == "supports"}),
                }
                for identifier in ids
            ]
            interpretations = [
                {
                    "claim_id": identifier,
                    "proposition": claim_rows[identifier][0]["proposition"],
                    "document_ids": sorted(claim_docs[identifier]),
                    "evidence_span_ids": sorted({row["evidence_span_id"] for row in claim_rows[identifier] if row["relationship"] in {"contextualizes", "supports"}}),
                    "kind": "contextualized_claim" if any(row["relationship"] == "contextualizes" for row in claim_rows[identifier]) else "reported_claim",
                }
                for identifier in sorted(claim_rows)
            ]
            return {
                "document_ids": ids,
                "documents": [
                    {
                        "id": identifier,
                        "title": by_id[identifier]["title"],
                        "canonical_url": by_id[identifier]["canonical_url"],
                        "published_at": by_id[identifier]["published_at"],
                        "source": {"id": by_id[identifier]["source_id"], "name": by_id[identifier]["source_name"]},
                    }
                    for identifier in ids
                ],
                "shared_claims": shared_claims,
                "unique_claims": unique_claims,
                "contradictions": contradictions,
                "dates_and_numbers": {"per_document": per_document, "differences": [{"kind": "date", **item} for item in differences(date_groups)] + [{"kind": "number", **item} for item in differences(number_groups)]},
                "interpretations": interpretations,
                "primary_source_use": primary_source_use,
                "lineage": lineage,
                "evidence_authority": "All conclusions resolve to stored Claims, Evidence Spans, Sources, and Document lineage.",
            }
        finally:
            conn.close()

    def compare_documents(self, document_ids: Sequence[str], *, story_id: str | None = None) -> dict[str, Any]:
        return self.compare(document_ids, story_id=story_id)


class WorkbenchService:
    """Small application service for notes, tags, subject context, and lineage."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.core = CoreService(db_path)

    def create_tag(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        namespace = str(data.get("namespace", "user")).strip()
        tag_type = str(data.get("tag_type", "user"))
        if not name or len(name) > 100:
            raise DomainValidation("tag name must be between 1 and 100 characters")
        if not namespace or len(namespace) > 64 or not re.fullmatch(r"[A-Za-z0-9._:-]+", namespace):
            raise DomainValidation("tag namespace is invalid")
        if tag_type not in {"user", "smart"}:
            raise DomainValidation("tag type must be user or smart")
        identifier = new_id("tag")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "INSERT INTO tags(id, name, normalized_name, namespace, tag_type, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (identifier, name, normalized_text(name), namespace, tag_type, now),
                )
        finally:
            conn.close()
        return self.core.get_tag(identifier)

    def add_note(self, object_type: str, object_id: str, body: str, *, note_type: str = "note") -> dict[str, Any]:
        if object_type not in OBJECT_TABLES:
            raise DomainValidation("unsupported note object type")
        body = str(body).strip()
        if not body or len(body) > 10_000:
            raise DomainValidation("note body must be between 1 and 10000 characters")
        if note_type not in {"note", "hypothesis", "context"}:
            raise DomainValidation("unsupported note type")
        table, key_column, deleted_column = OBJECT_TABLES[object_type]
        conn = storage.connect(self.db_path)
        try:
            condition = f" AND {deleted_column} IS NULL" if deleted_column else ""
            if conn.execute(f"SELECT 1 FROM {table} WHERE {key_column} = ?{condition}", (object_id,)).fetchone() is None:
                raise DomainNotFound(f"{object_type} not found")
            identifier = new_id("note")
            now = utc_now()
            with storage.write_tx(conn):
                conn.execute(
                    "INSERT INTO notes(id, object_type, object_id, note_type, body, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (identifier, object_type, object_id, note_type, body, now, now),
                )
            return {"id": identifier, "object_type": object_type, "object_id": object_id, "note_type": note_type, "body": body, "created_at": now, "updated_at": now}
        finally:
            conn.close()

    def link_lineage(self, document_id: str, parent_document_id: str, relationship: str, *, confidence: float = 1.0, rationale: str = "") -> dict[str, Any]:
        from .story_evolution import StoryEvolutionService

        return StoryEvolutionService(self.db_path).link_lineage(document_id, parent_document_id, relationship, confidence=confidence, rationale=rationale)

    def historical_context(self, subject_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            subject = conn.execute("SELECT * FROM subjects WHERE id = ? AND deleted_at IS NULL", (subject_id,)).fetchone()
            if subject is None:
                raise DomainNotFound("subject not found")
            evidence = conn.execute(
                """
                SELECT DISTINCT es.id, es.excerpt, es.locator_type, es.locator_value,
                       c.id AS claim_id, c.proposition, c.state,
                       d.id AS document_id, d.title AS document_title, d.canonical_url,
                       s.id AS source_id, s.name AS source_name, dv.retrieved_at
                FROM story_subjects ss
                JOIN stories st ON st.id = ss.story_id AND st.deleted_at IS NULL
                JOIN claims c ON c.story_id = st.id
                JOIN claim_evidence ce ON ce.claim_id = c.id
                JOIN evidence_spans es ON es.id = ce.evidence_span_id
                JOIN document_versions dv ON dv.id = es.document_version_id
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE ss.subject_id = ?
                ORDER BY COALESCE(d.published_at, dv.retrieved_at) DESC, es.id DESC
                LIMIT 200
                """,
                (subject_id,),
            ).fetchall()
            claims = conn.execute(
                """
                SELECT DISTINCT c.id, c.proposition, c.state, c.importance, c.story_id
                FROM story_subjects ss JOIN claims c ON c.story_id = ss.story_id
                JOIN stories st ON st.id = c.story_id AND st.deleted_at IS NULL
                WHERE ss.subject_id = ? ORDER BY c.created_at DESC, c.id DESC LIMIT 200
                """,
                (subject_id,),
            ).fetchall()
            notes = conn.execute("SELECT * FROM notes WHERE object_type = 'subject' AND object_id = ? ORDER BY created_at DESC, id DESC LIMIT 100", (subject_id,)).fetchall()
            return {
                "subject_id": subject_id,
                "claims": [_as_dict(row) for row in claims],
                "evidence": [_as_dict(row) for row in evidence],
                "notes": [_as_dict(row) for row in notes],
                "basis": "Derived from linked Stories, Claims, and exact Evidence Spans; no model memory is used.",
            }
        finally:
            conn.close()

    def timeline(self, object_type: str, object_id: str) -> list[dict[str, Any]]:
        conn = storage.connect(self.db_path)
        try:
            if object_type == "subject":
                if conn.execute("SELECT 1 FROM subjects WHERE id = ? AND deleted_at IS NULL", (object_id,)).fetchone() is None:
                    raise DomainNotFound("subject not found")
                rows = conn.execute(
                    """
                    SELECT 'story_revision' AS event_type, r.id, r.created_at AS at,
                           r.headline AS label, r.story_id, r.material_change
                    FROM story_subjects ss JOIN story_revisions r ON r.story_id = ss.story_id
                    JOIN stories st ON st.id = r.story_id AND st.deleted_at IS NULL
                    WHERE ss.subject_id = ?
                    UNION ALL
                    SELECT 'evolution' AS event_type, e.id, e.created_at AS at,
                           e.update_class AS label, e.story_id, e.material_change
                    FROM story_subjects ss JOIN story_evolution_events e ON e.story_id = ss.story_id
                    JOIN stories st ON st.id = e.story_id AND st.deleted_at IS NULL
                    WHERE ss.subject_id = ?
                    ORDER BY 3 DESC, 2 DESC LIMIT 200
                    """,
                    (object_id, object_id),
                ).fetchall()
                return [_as_dict(row) for row in rows]
            if object_type not in OBJECT_TABLES:
                raise DomainValidation("unsupported timeline object type")
            table, key_column, deleted_column = OBJECT_TABLES[object_type]
            condition = f" AND {deleted_column} IS NULL" if deleted_column else ""
            if conn.execute(f"SELECT 1 FROM {table} WHERE {key_column} = ?{condition}", (object_id,)).fetchone() is None:
                raise DomainNotFound(f"{object_type} not found")
            rows = conn.execute("SELECT id, created_at AS at, note_type AS event_type, body AS label FROM notes WHERE object_type = ? AND object_id = ? ORDER BY created_at DESC, id DESC LIMIT 200", (object_type, object_id)).fetchall()
            return [_as_dict(row) for row in rows]
        finally:
            conn.close()

    def subject_page(self, subject_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            subject = conn.execute("SELECT * FROM subjects WHERE id = ? AND deleted_at IS NULL", (subject_id,)).fetchone()
            if subject is None:
                raise DomainNotFound("subject not found")
            aliases = [row[0] for row in conn.execute("SELECT alias FROM subject_aliases WHERE subject_id = ? ORDER BY alias_normalized, id", (subject_id,))]
            stories = conn.execute(
                """
                SELECT st.id, st.lifecycle, st.created_at, st.updated_at, r.headline, r.summary, r.material_change
                FROM story_subjects ss JOIN stories st ON st.id = ss.story_id AND st.deleted_at IS NULL
                LEFT JOIN story_revisions r ON r.id = (SELECT r2.id FROM story_revisions r2 WHERE r2.story_id = st.id ORDER BY r2.revision_number DESC, r2.id DESC LIMIT 1)
                WHERE ss.subject_id = ? ORDER BY st.updated_at DESC, st.id DESC LIMIT 100
                """,
                (subject_id,),
            ).fetchall()
        finally:
            conn.close()
        context = self.historical_context(subject_id)
        return {
            "subject": {**(_as_dict(subject) or {}), "aliases": aliases},
            "stories": [_as_dict(row) for row in stories],
            "timeline": self.timeline("subject", subject_id),
            "historical_context": context,
        }


class DiagnosticsService:
    """Derive coverage and health from recorded monitor/acquisition/job state."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def monitor(self, monitor_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            monitor = conn.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,)).fetchone()
            if monitor is None:
                raise DomainNotFound("monitor not found")
            activities = conn.execute("SELECT * FROM monitor_activity WHERE monitor_id = ? ORDER BY observed_at DESC, rowid DESC LIMIT 1000", (monitor_id,)).fetchall()
            counts = {"checks": len(activities), "meaningful_change": 0, "content_change": 0, "no_meaningful_change": 0, "partial": 0, "failed_processing": 0}
            for row in activities:
                if row["outcome"] == "relevant_change":
                    counts["meaningful_change"] += 1
                elif row["outcome"] == "changed":
                    counts["content_change"] += 1
                elif row["outcome"] == "no_change":
                    counts["no_meaningful_change"] += 1
                elif row["outcome"] == "partial":
                    counts["partial"] += 1
                elif row["outcome"] == "error":
                    counts["failed_processing"] += 1
            source_ids: list[str] = []
            if monitor["target_type"] == "source":
                source_ids = [monitor["target_id"]]
            elif monitor["target_type"] == "story":
                source_ids = [row[0] for row in conn.execute(
                    """
                    SELECT DISTINCT d.source_id FROM documents d
                    WHERE d.id IN (SELECT document_id FROM story_documents WHERE story_id = ?)
                    OR d.id IN (
                        SELECT dv.document_id FROM document_versions dv
                        JOIN evidence_spans es ON es.document_version_id = dv.id
                        JOIN claim_evidence ce ON ce.evidence_span_id = es.id
                        JOIN claims c ON c.id = ce.claim_id AND c.story_id = ?
                    )
                    ORDER BY d.source_id
                    """,
                    (monitor["target_id"], monitor["target_id"]),
                )]
            elif monitor["target_type"] == "subject":
                source_ids = [row[0] for row in conn.execute(
                    """
                    SELECT DISTINCT d.source_id FROM documents d
                    JOIN document_versions dv ON dv.document_id = d.id
                    JOIN evidence_spans es ON es.document_version_id = dv.id
                    JOIN claim_evidence ce ON ce.evidence_span_id = es.id
                    JOIN claims c ON c.id = ce.claim_id
                    JOIN story_subjects ss ON ss.story_id = c.story_id
                    WHERE ss.subject_id = ? ORDER BY d.source_id
                    """,
                    (monitor["target_id"],),
                )]
            if source_ids:
                acquisition_failures = conn.execute(
                    f"SELECT COUNT(*) FROM acquisition_events WHERE outcome IN ('failed', 'error', 'blocked', 'timeout') AND source_id IN ({_placeholders(source_ids)})",
                    source_ids,
                ).fetchone()[0]
            else:
                acquisition_failures = 0
            latest = activities[0] if activities else None
            if latest is None:
                latest_status = "not_run"
            elif latest["outcome"] == "no_change":
                latest_status = "no_meaningful_change"
            elif latest["outcome"] == "changed":
                latest_status = "content_changed"
            elif latest["outcome"] == "relevant_change":
                latest_status = "meaningful_change"
            elif latest["outcome"] == "error":
                latest_status = "failed_processing"
            else:
                latest_status = "partial"
            counts["failed_acquisition"] = acquisition_failures
            counts["latest_status"] = latest_status
            counts["last_checked_at"] = latest["observed_at"] if latest else None
            return {"monitor": _as_dict(monitor), "coverage": counts, "activities": [_as_dict(row) for row in activities[:100]], "source_ids": source_ids, "interpretation": {"no_meaningful_change": "The monitor ran successfully and recorded no relevant change.", "content_changed": "Acquisition detected changed content whose semantic relevance has not been evaluated yet.", "failed_acquisition": "A source acquisition failed before evidence processing.", "failed_processing": "The monitor recorded an operational processing error."}}
        finally:
            conn.close()

    def coverage(self) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            monitor_ids = [row[0] for row in conn.execute("SELECT id FROM monitors ORDER BY id")]
        finally:
            conn.close()
        items = [self.monitor(identifier) for identifier in monitor_ids]
        return {"items": items, "total": len(items)}

    def health(self) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            integrity = check_database(self.db_path)
            counts = {
                "monitors": conn.execute("SELECT COUNT(*) FROM monitors").fetchone()[0],
                "sources": conn.execute("SELECT COUNT(*) FROM sources WHERE deleted_at IS NULL").fetchone()[0],
                "documents": conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
                "stories": conn.execute("SELECT COUNT(*) FROM stories WHERE deleted_at IS NULL").fetchone()[0],
                "failed_acquisitions": conn.execute("SELECT COUNT(*) FROM acquisition_events WHERE outcome IN ('failed', 'error', 'blocked', 'timeout')").fetchone()[0],
                "failed_processing": conn.execute("SELECT COUNT(*) FROM monitor_activity WHERE outcome = 'error'").fetchone()[0],
                "failed_jobs": conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'failed'").fetchone()[0],
                "no_meaningful_change": conn.execute("SELECT COUNT(*) FROM monitor_activity WHERE outcome = 'no_change'").fetchone()[0],
                "content_changed": conn.execute("SELECT COUNT(*) FROM monitor_activity WHERE outcome = 'changed'").fetchone()[0],
            }
            database = "ok" if integrity.ok else "error"
            status = "unhealthy" if not integrity.ok else "healthy" if counts["failed_acquisitions"] == 0 and counts["failed_processing"] == 0 and counts["failed_jobs"] == 0 else "degraded"
            return {"status": status, "database": database, "issues": [issue.code for issue in integrity.issues], "counts": counts, "distinctions": {"no_meaningful_change": "successful observation with no relevant update", "content_changed": "content changed but relevance is not yet evaluated", "failed_acquisition": "retrieval did not complete", "failed_processing": "retrieval completed or was handed off but processing failed"}}
        except sqlite3.Error as exc:
            return {"status": "unhealthy", "database": "error", "counts": {}, "error": type(exc).__name__}
        finally:
            conn.close()


__all__ = ["ComparisonService", "DiagnosticsService", "SearchService", "WorkbenchService"]
