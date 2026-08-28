"""Evidence-bound conversational answers for the local Newsroom workspace."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import storage
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, utc_now
from .workbench import KnowledgeRetrievalService
from .temporal import TemporalReadService, normalize_as_of


SCOPE_TYPES = frozenset(
    {"global", "story", "claim", "evidence", "document", "report", "question", "subject", "monitor", "note", "entity", "research_task", "source"}
)
PROMPT_LIMIT = 4_000
CONTEXT_LIMIT = 12_000
CITATION_LIMIT = 30
STALE_AFTER_DAYS = 180
TOKEN_RE = re.compile(r"[\w]+(?:[-'][\w]+)*", re.UNICODE)
INJECTION_RE = re.compile(
    r"(?:ignore|disregard|override|forget).{0,60}(?:previous|prior|system|developer|instruction)|"
    r"(?:reveal|show|print|leak).{0,40}(?:system prompt|developer message|hidden prompt)|"
    r"<\s*(?:system|developer|instruction)\b",
    re.IGNORECASE | re.DOTALL,
)
STOP_WORDS = frozenset(
    {
        "about", "after", "been", "being", "does", "from", "have", "what", "when", "where", "which",
        "with", "would", "could", "should", "there", "their", "they", "this", "that", "into", "tell",
        "known", "newsroom", "please", "will", "were",
    }
)
OBJECT_TABLES = {
    "story": ("stories", True),
    "claim": ("claims", False),
    "evidence": ("evidence_spans", False),
    "document": ("documents", False),
    "report": ("living_reports", False),
    "question": ("research_questions", True),
    "subject": ("subjects", True),
    "monitor": ("monitors", False),
    "note": ("notes", False),
    "entity": ("entities", False),
    "research_task": ("research_tasks", False),
    "source": ("sources", True),
}


def _load_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _placeholders(values: Sequence[str]) -> str:
    return ", ".join("?" for _ in values)


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _tokens(prompt: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for token in TOKEN_RE.findall(prompt.casefold()):
        if len(token) < 3 or token in STOP_WORDS or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result[:12]


def _words(value: str | None) -> int:
    return len(TOKEN_RE.findall(value or ""))


def _parse_time(value: str | None):
    if not value:
        return None
    from datetime import datetime, timezone

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_stale(
    value: str | None,
    *,
    stale_after_days: int = STALE_AFTER_DAYS,
    reference_time: str | datetime | None = None,
) -> bool:
    from datetime import datetime, timedelta, timezone

    parsed = _parse_time(value)
    if parsed is None:
        return True
    if reference_time is None:
        reference = datetime.now(timezone.utc)
    else:
        reference = _parse_time(str(reference_time))
        if reference is None:
            return True
    return reference - parsed > timedelta(days=stale_after_days)


class AskService:
    """Persist minimal answer audit data while deriving prose from stored evidence."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        stale_after_days: int = STALE_AFTER_DAYS,
        max_prompt_length: int = PROMPT_LIMIT,
        max_context_units: int = CONTEXT_LIMIT,
        max_citations: int = CITATION_LIMIT,
        hosted_enabled: bool = False,
    ):
        if stale_after_days < 1 or max_prompt_length < 1 or max_context_units < 100 or max_citations < 1:
            raise ValueError("AskService limits must be positive")
        self.db_path = Path(db_path)
        self.stale_after_days = stale_after_days
        self.max_prompt_length = max_prompt_length
        self.max_context_units = max_context_units
        self.max_citations = max_citations
        self.hosted_enabled = hosted_enabled
        self.search = KnowledgeRetrievalService(db_path)
        self.temporal = TemporalReadService(db_path)

    def create_conversation(self, *, scope_type: str = "global", scope_id: str | None = None) -> dict[str, Any]:
        scope_type = self._normalize_scope_type(scope_type)
        if scope_type == "global":
            scope_id = None
        elif not scope_id:
            raise DomainValidation("scope_id is required for an object-scoped conversation")
        now = utc_now()
        identifier = new_id("ask")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_scope(conn, scope_type, scope_id)
                conn.execute(
                    "INSERT INTO ask_conversations(id, scope_type, scope_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (identifier, scope_type, scope_id, now, now),
                )
        finally:
            conn.close()
        return self.get_conversation(identifier)

    def list_conversations(self, *, scope_type: str | None = None, scope_id: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainValidation("conversation page must be >= 1 and page_size must be between 1 and 100")
        if scope_type is not None:
            scope_type = self._normalize_scope_type(scope_type)
        clauses = ["1 = 1"]
        params: list[Any] = []
        for column, value in (("scope_type", scope_type), ("scope_id", scope_id)):
            if value is not None:
                clauses.append(f"c.{column} = ?")
                params.append(value)
        where = " AND ".join(clauses)
        conn = storage.connect(self.db_path)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM ask_conversations c WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT c.*, COUNT(r.id) AS turn_count, MAX(r.turn_number) AS latest_turn_number, (SELECT r2.status FROM ask_runs r2 WHERE r2.conversation_id = c.id ORDER BY r2.turn_number DESC LIMIT 1) AS latest_status FROM ask_conversations c LEFT JOIN ask_runs r ON r.conversation_id = c.id WHERE {where} GROUP BY c.id ORDER BY c.updated_at DESC, c.id DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {"items": [dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def get_conversation(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            conversation = conn.execute("SELECT * FROM ask_conversations WHERE id = ?", (identifier,)).fetchone()
            if conversation is None:
                raise DomainNotFound("Ask Newsroom conversation not found")
            result = dict(conversation)
            result["turns"] = [self._run_result(row) for row in conn.execute("SELECT * FROM ask_runs WHERE conversation_id = ? ORDER BY turn_number, id", (identifier,)).fetchall()]
            return result
        finally:
            conn.close()

    def get_run(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM ask_runs WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("Ask Newsroom run not found")
            return self._run_result(row)
        finally:
            conn.close()

    def cancel(self, identifier: str) -> dict[str, Any]:
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT status FROM ask_runs WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("Ask Newsroom run not found")
                if row[0] in {"queued", "running"}:
                    conn.execute("UPDATE ask_runs SET status = 'cancelled', refusal_code = 'cancelled', completed_at = ? WHERE id = ?", (now, identifier))
            return self.get_run(identifier)
        finally:
            conn.close()

    def ask(
        self,
        conversation_id: str,
        prompt: str,
        *,
        context_budget: int = 4_000,
        provider_mode: str = "local",
        cost_cap_usd: float = 0.0,
        cancel_check: Callable[[], bool] | None = None,
        as_of: str | datetime | None = None,
        retrieval_limit: int | None = None,
        synthesis_router: Any | None = None,
        synthesis_work_id: str | None = None,
    ) -> dict[str, Any]:
        prompt = self._validate_prompt(prompt)
        boundary = normalize_as_of(as_of) if as_of is not None else None
        if context_budget < 100 or context_budget > self.max_context_units:
            raise DomainValidation(f"context_budget must be between 100 and {self.max_context_units}")
        if retrieval_limit is not None and (isinstance(retrieval_limit, bool) or not 1 <= retrieval_limit <= 100):
            raise DomainValidation("retrieval_limit must be between 1 and 100")
        if provider_mode not in {"local", "hosted"}:
            raise DomainValidation("provider_mode must be local or hosted")
        if cost_cap_usd < 0:
            raise DomainValidation("cost_cap_usd cannot be negative")
        conversation = self._conversation(conversation_id)
        run_id, turn_number = self._start_run(conversation_id, prompt, provider_mode)
        fallback_route: str | None = None

        if self._cancelled(run_id, cancel_check):
            return self._finish(run_id, self._cancelled_result(run_id, conversation_id, turn_number))
        if INJECTION_RE.search(prompt):
            return self._finish(run_id, self._refused_result(run_id, conversation_id, turn_number, "prompt_injection", "I can only answer from Newsroom records; instruction-like text was not treated as a command."))
        if provider_mode == "hosted":
            if cost_cap_usd <= 0:
                return self._finish(run_id, self._refused_result(run_id, conversation_id, turn_number, "provider_cost_cap", "Hosted escalation is disabled because this request has no positive cost cap."), provider_route="hosted_blocked")
            if synthesis_router is None and not self.hosted_enabled:
                provider_mode = "local"
                fallback_route = "local_deterministic_fallback"

        try:
            retrieved = self._retrieve(
                prompt,
                conversation["scope_type"],
                conversation["scope_id"],
                context_budget,
                cancel_check,
                run_id,
                as_of=boundary,
                retrieval_limit=retrieval_limit,
            )
            if retrieved.get("cancelled"):
                return self._finish(run_id, self._cancelled_result(run_id, conversation_id, turn_number))
            result = self._compose(
                run_id,
                conversation_id,
                turn_number,
                prompt,
                retrieved,
                context_budget,
                synthesis_router=synthesis_router,
                synthesis_work_id=synthesis_work_id,
            )
            return self._finish(run_id, result, provider_route=fallback_route or result.get("provider_route"))
        except DomainValidation:
            raise
        except Exception:
            failed = self._refused_result(run_id, conversation_id, turn_number, "answer_failed", "The answer could not be completed from the local evidence ledger.")
            failed["status"] = "failed"
            return self._finish(run_id, failed)

    def resolve_citations(self, citations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        conn = storage.connect(self.db_path)
        try:
            return [self._resolve_citation(conn, dict(item)) for item in citations]
        finally:
            conn.close()

    def _normalize_scope_type(self, scope_type: str) -> str:
        value = str(scope_type or "").strip().casefold().replace("-", "_")
        if value == "research_question":
            value = "question"
        if value not in SCOPE_TYPES:
            raise DomainValidation("unsupported Ask Newsroom scope type")
        return value

    def _require_scope(self, conn, scope_type: str, scope_id: str | None) -> None:
        if scope_type == "global":
            return
        table, live = OBJECT_TABLES[scope_type]
        if scope_type == "note":
            row = conn.execute("SELECT 1 FROM notes WHERE id = ? UNION ALL SELECT 1 FROM research_question_notes WHERE id = ?", (scope_id, scope_id)).fetchone()
        else:
            condition = " AND deleted_at IS NULL" if live else ""
            row = conn.execute(f"SELECT 1 FROM {table} WHERE id = ?{condition}", (scope_id,)).fetchone()
        if row is None:
            raise DomainNotFound(f"{scope_type} scope not found")

    def _conversation(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM ask_conversations WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("Ask Newsroom conversation not found")
            return dict(row)
        finally:
            conn.close()

    def _validate_prompt(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            raise DomainValidation("prompt must be a string")
        prompt = prompt.strip()
        if not prompt or len(prompt) > self.max_prompt_length:
            raise DomainValidation(f"prompt must be between 1 and {self.max_prompt_length} characters")
        return prompt

    def _start_run(self, conversation_id: str, prompt: str, provider_mode: str) -> tuple[str, int]:
        identifier = new_id("askrun")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT id FROM ask_conversations WHERE id = ?", (conversation_id,)).fetchone()
                if row is None:
                    raise DomainNotFound("Ask Newsroom conversation not found")
                turn = conn.execute("SELECT COALESCE(MAX(turn_number), 0) + 1 FROM ask_runs WHERE conversation_id = ?", (conversation_id,)).fetchone()[0]
                conn.execute(
                    "INSERT INTO ask_runs(id, conversation_id, turn_number, prompt_hash, prompt_length, status, provider_route, created_at) VALUES (?, ?, ?, ?, ?, 'running', ?, ?)",
                    (identifier, conversation_id, turn, _prompt_hash(prompt), len(prompt), f"{provider_mode}_pending", now),
                )
                conn.execute("UPDATE ask_conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            return identifier, turn
        finally:
            conn.close()

    def _cancelled(self, run_id: str, cancel_check: Callable[[], bool] | None) -> bool:
        if cancel_check is not None and cancel_check():
            self.cancel(run_id)
            return True
        conn = storage.connect(self.db_path)
        try:
            return conn.execute("SELECT status FROM ask_runs WHERE id = ?", (run_id,)).fetchone()[0] == "cancelled"
        finally:
            conn.close()

    def _retrieve(
        self,
        prompt: str,
        scope_type: str,
        scope_id: str | None,
        context_budget: int,
        cancel_check: Callable[[], bool] | None,
        run_id: str,
        *,
        as_of: str | None = None,
        retrieval_limit: int | None = None,
    ) -> dict[str, Any]:
        terms = _tokens(prompt)
        if not terms:
            return {"items": [], "claims": {}, "evidence": {}, "notes": [], "reports": [], "questions": [], "gaps": [], "tasks": [], "terms": [], "packet_ids": [], "grounding_evidence_count": 0, "as_of": as_of, "retrieval_limit": retrieval_limit or 100}
        if self._cancelled(run_id, cancel_check):
            return {"cancelled": True}
        try:
            shared = self.search.retrieve_typed(prompt, max_results=retrieval_limit or 100)
        except DomainValidation:
            shared = {"items": [], "candidate_count": 0, "terms": terms}
        items = {(item["entity_type"], item["entity_id"]): item for item in shared.get("items", [])}

        conn = storage.connect(self.db_path)
        try:
            scope = self._scope_sets(conn, scope_type, scope_id)
            if as_of is not None:
                shared_items = self.temporal.filter_items_as_of(shared.get("items", []), as_of, terms=terms, conn=conn)
            else:
                shared_items = shared.get("items", [])
            items = {(item["entity_type"], item["entity_id"]): item for item in shared_items}
            items = {key: item for key, item in items.items() if self._item_in_scope(item, scope)}
            self._add_report_items(conn, items, terms, scope)
            if as_of is not None:
                items = {
                    (item["entity_type"], item["entity_id"]): item
                    for item in self.temporal.filter_items_as_of(items.values(), as_of, terms=terms, conn=conn)
                }
            claim_ids: set[str] = set()
            evidence_ids: set[str] = set()
            note_ids: set[str] = set()
            question_ids: set[str] = set()
            task_ids: set[str] = set()
            for item in items.values():
                self._expand_item(conn, item, claim_ids, evidence_ids, note_ids, question_ids, task_ids, as_of=as_of)
            claims = self._load_claims(conn, sorted(claim_ids))
            evidence = self._load_evidence(conn, sorted(evidence_ids | {ev["id"] for claim in claims.values() for ev in claim["evidence"]}))
            if as_of is not None:
                historical_claims = self.temporal.claims_as_of(as_of, claim_ids=claims.keys())
                claims = {claim["id"]: claim for claim in historical_claims}
                evidence = {
                    evidence_item["id"]: {**evidence_item, "score": 0.0}
                    for claim in historical_claims
                    for evidence_item in claim["evidence"]
                }
            notes = self._load_notes(conn, sorted(note_ids))
            if as_of is not None:
                boundary_time = _parse_time(as_of)
                notes = [
                    note
                    for note in notes
                    if boundary_time is not None
                    and _parse_time(note.get("created_at")) is not None
                    and _parse_time(note.get("created_at")) <= boundary_time
                    and self.temporal.eligible_as_of("note", note["id"], as_of, conn=conn)
                ]
                notes.extend(
                    {
                        **note,
                        "id": f"research-question:{note['id']}",
                        "citation_type": "question_note",
                        "citation_id": note["id"],
                        "object_type": "research_question",
                        "object_id": note["question_id"],
                    }
                    for note in self.temporal.question_notes_as_of(question_ids, as_of, conn=conn)
                )
                questions = [
                    question
                    for question in (self.temporal.question_as_of(identifier, as_of, conn=conn) for identifier in sorted(question_ids))
                    if question is not None
                ]
            else:
                notes.extend(self._load_question_notes(conn, sorted(question_ids)))
                questions = self._load_questions(conn, sorted(question_ids))
            reports = self._load_reports(conn, [item["entity_id"] for item in items.values() if item["entity_type"] == "report"])
            if as_of is not None:
                historical_reports = []
                for identifier in [item["entity_id"] for item in items.values() if item["entity_type"] == "report"]:
                    try:
                        value = self.temporal.report_as_of(identifier, as_of)
                    except DomainNotFound:
                        continue
                    report = value["report"]
                    revision = value.get("revision") or {}
                    historical_reports.append(
                        {
                            "id": report["id"],
                            "name": report["name"],
                            "current_revision_id": revision.get("id"),
                            "current_status": revision.get("current_status") or report.get("status"),
                            "sections": revision.get("sections", {}),
                        }
                    )
                reports = historical_reports
            gaps = self._load_gaps(conn, sorted(question_ids)) if as_of is None else self.temporal.gaps_as_of(question_ids, as_of, conn=conn)
            gap_task_ids = {gap["task_id"] for gap in gaps if gap.get("task_id")} if as_of is None else set()
            task_identifiers = task_ids | gap_task_ids | {item["entity_id"] for item in items.values() if item["entity_type"] == "research_task"}
            tasks = self._load_tasks(conn, sorted(task_identifiers)) if as_of is None else [
                {**task, "outcome": _load_json(task.get("outcome_json"), {})}
                for task in self.temporal.tasks_as_of(task_identifiers, as_of, conn=conn)
            ]
            correction_story_ids = set(scope.get("stories", set()))
            correction_story_ids.update(
                claim.get("story_id") for claim in claims.values() if claim.get("story_id")
            )
            correction_terms = {"merge", "merged", "split", "correction", "corrected", "moved", "unassign", "unassigned", "duplicate", "extract", "extracted", "lineage"}
            correction_rows = []
            if correction_story_ids:
                placeholders = _placeholders(sorted(correction_story_ids))
                correction_rows = [dict(row) for row in conn.execute(
                    f"""
                    SELECT DISTINCT sc.*
                    FROM story_corrections sc
                    LEFT JOIN claim_story_assignment_history csh ON csh.correction_id = sc.id
                    LEFT JOIN story_lineage sl ON sl.correction_id = sc.id
                    LEFT JOIN story_duplicate_decisions sdd ON sdd.correction_id = sc.id
                    WHERE csh.from_story_id IN ({placeholders}) OR csh.to_story_id IN ({placeholders})
                       OR sl.source_story_id IN ({placeholders}) OR sl.target_story_id IN ({placeholders})
                       OR sdd.source_story_id IN ({placeholders}) OR sdd.destination_story_id IN ({placeholders})
                    ORDER BY sc.occurred_at DESC, sc.id DESC LIMIT 50
                    """,
                    [*sorted(correction_story_ids)] * 6,
                )]
            elif correction_terms.intersection(terms):
                correction_rows = [dict(row) for row in conn.execute(
                    "SELECT * FROM story_corrections ORDER BY occurred_at DESC, id DESC LIMIT 50"
                )]
            if as_of is not None:
                correction_boundary = _parse_time(as_of)
                correction_rows = [
                    row
                    for row in correction_rows
                    if (occurred := _parse_time(row.get("occurred_at"))) is not None
                    and correction_boundary is not None
                    and occurred <= correction_boundary
                ]
            context_units = 0
            selected_evidence: dict[str, dict[str, Any]] = {}
            for evidence_id, item in sorted(evidence.items(), key=lambda pair: (float(pair[1].get("score", 0)), pair[0])):
                units = max(1, _words(item.get("excerpt")))
                if context_units + units > context_budget and selected_evidence:
                    continue
                selected_evidence[evidence_id] = item
                context_units += units
            packet_ids: set[str] = set()
            for item in items.values():
                packet_ids.add(f"{item['entity_type']}:{item['entity_id']}")
            for identifier in claims:
                packet_ids.add(f"claim:{identifier}")
            for identifier, item in selected_evidence.items():
                packet_ids.add(f"evidence:{identifier}")
                if item.get("document_id"):
                    packet_ids.add(f"document:{item['document_id']}")
                if item.get("source_id"):
                    packet_ids.add(f"source:{item['source_id']}")
            for question in questions:
                packet_ids.add(f"question:{question['id']}")
            for note in notes:
                note_type = note.get("citation_type", "note")
                note_id = note.get("citation_id", note.get("id"))
                if note_id:
                    packet_ids.add(f"{note_type}:{note_id}")
            for gap in gaps:
                packet_ids.add(f"research_gap:{gap['id']}")
            for task in tasks:
                packet_ids.add(f"research_task:{task['id']}")
            for correction in correction_rows:
                packet_ids.add(f"story_correction:{correction['id']}")
            for report in reports:
                packet_ids.add(f"report:{report['id']}")
                if report.get("current_revision_id"):
                    packet_ids.add(f"report_revision:{report['current_revision_id']}")
            return {
                "items": list(items.values()),
                "claims": claims,
                "evidence": selected_evidence,
                "notes": notes,
                "questions": questions,
                "reports": reports,
                "gaps": gaps,
                "tasks": tasks,
                "corrections": correction_rows,
                "terms": terms,
                "context_units": context_units,
                "context_truncated": len(selected_evidence) < len(evidence),
                "scope": {"type": scope_type, "id": scope_id},
                "packet_ids": sorted(packet_ids),
                "grounding_evidence_count": sum(
                    1
                    for claim in claims.values()
                    if claim.get("state") != "retracted"
                    for evidence in claim.get("evidence", [])
                    if evidence["id"] in selected_evidence
                ),
                "retrieval_ranking": shared.get("ranking", "exact_match_then_bm25_then_entity_type_then_entity_id"),
                "as_of": as_of,
                "retrieval_limit": retrieval_limit or 100,
            }
        finally:
            conn.close()

    def _scope_sets(self, conn, scope_type: str, scope_id: str | None) -> dict[str, Any]:
        empty = {key: set() for key in ("stories", "claims", "evidence", "documents", "subjects", "questions", "monitors", "reports", "notes", "entities", "gaps", "tasks", "sources")}
        empty["_primary_type"] = scope_type
        empty["_primary_id"] = scope_id
        if scope_type == "global":
            empty["all"] = {"*"}
            return empty
        if scope_type == "story":
            empty["stories"].add(scope_id)
        elif scope_type == "claim":
            empty["claims"].add(scope_id)
            row = conn.execute("SELECT story_id FROM claims WHERE id = ?", (scope_id,)).fetchone()
            if row and row[0] is not None:
                empty["stories"].add(row[0])
        elif scope_type == "evidence":
            empty["evidence"].add(scope_id)
            row = conn.execute("SELECT dv.document_id FROM evidence_spans es JOIN document_versions dv ON dv.id = es.document_version_id WHERE es.id = ?", (scope_id,)).fetchone()
            if row:
                empty["documents"].add(row[0])
        elif scope_type == "document":
            empty["documents"].add(scope_id)
        elif scope_type == "subject":
            empty["subjects"].add(scope_id)
            empty["stories"].update(row[0] for row in conn.execute("SELECT story_id FROM story_subjects WHERE subject_id = ?", (scope_id,)))
        elif scope_type == "question":
            empty["questions"].add(scope_id)
        elif scope_type == "monitor":
            empty["monitors"].add(scope_id)
            row = conn.execute("SELECT target_type, target_id FROM monitors WHERE id = ?", (scope_id,)).fetchone()
            if row and row[0] == "story":
                empty["stories"].add(row[1])
            elif row and row[0] == "subject":
                empty["subjects"].add(row[1])
            elif row and row[0] == "research_question":
                empty["questions"].add(row[1])
            elif row and row[0] == "source":
                empty["documents"].update(item[0] for item in conn.execute("SELECT id FROM documents WHERE source_id = ?", (row[1],)))
        elif scope_type == "report":
            empty["reports"].add(scope_id)
        elif scope_type == "note":
            empty["notes"].add(scope_id)
        elif scope_type == "entity":
            empty["entities"].add(scope_id)
            empty["claims"].update(row[0] for row in conn.execute("SELECT claim_id FROM claim_entities WHERE entity_id = ?", (scope_id,)))
            empty["stories"].update(row[0] for row in conn.execute(
                """
                SELECT story_id FROM story_entities WHERE entity_id = ? AND authority = 'manual'
                UNION
                SELECT c.story_id FROM claims c JOIN claim_entities ce ON ce.claim_id = c.id
                WHERE ce.entity_id = ? AND c.story_id IS NOT NULL
                """,
                (scope_id, scope_id),
            ))
            empty["questions"].update(row[0] for row in conn.execute("SELECT question_id FROM research_question_entities WHERE entity_id = ?", (scope_id,)))
            empty["gaps"].update(row[0] for row in conn.execute("SELECT gap_id FROM research_gap_entities WHERE entity_id = ?", (scope_id,)))
            empty["tasks"].update(row[0] for row in conn.execute("SELECT task_id FROM research_task_entities WHERE entity_id = ?", (scope_id,)))
        elif scope_type == "research_task":
            empty["tasks"].add(scope_id)
            row = conn.execute("SELECT question_id, gap_id FROM research_tasks WHERE id = ?", (scope_id,)).fetchone()
            if row:
                empty["questions"].add(row[0])
                empty["gaps"].add(row[1])
        elif scope_type == "source":
            empty["sources"].add(scope_id)
            empty["documents"].update(row[0] for row in conn.execute("SELECT id FROM documents WHERE source_id = ?", (scope_id,)))
        if empty["stories"]:
            empty["claims"].update(row[0] for row in conn.execute("SELECT id FROM claims WHERE story_id IN ({})".format(_placeholders(empty["stories"])), tuple(empty["stories"])))
        if empty["claims"]:
            empty["evidence"].update(row[0] for row in conn.execute("SELECT evidence_span_id FROM claim_evidence WHERE claim_id IN ({})".format(_placeholders(empty["claims"])), tuple(empty["claims"])))
        if empty["documents"]:
            empty["evidence"].update(row[0] for row in conn.execute("SELECT es.id FROM evidence_spans es JOIN document_versions dv ON dv.id = es.document_version_id WHERE dv.document_id IN ({})".format(_placeholders(empty["documents"])), tuple(empty["documents"])))
        if empty["evidence"]:
            empty["claims"].update(row[0] for row in conn.execute("SELECT claim_id FROM claim_evidence WHERE evidence_span_id IN ({})".format(_placeholders(empty["evidence"])), tuple(empty["evidence"])))
        if empty["questions"]:
            empty["claims"].update(row[0] for row in conn.execute("SELECT claim_id FROM research_question_claims WHERE question_id IN ({})".format(_placeholders(empty["questions"])), tuple(empty["questions"])))
            empty["evidence"].update(row[0] for row in conn.execute("SELECT evidence_span_id FROM research_question_evidence WHERE question_id IN ({})".format(_placeholders(empty["questions"])), tuple(empty["questions"])))
            empty["gaps"].update(row[0] for row in conn.execute("SELECT id FROM research_question_gaps WHERE question_id IN ({})".format(_placeholders(empty["questions"])), tuple(empty["questions"])))
        if empty["gaps"]:
            empty["tasks"].update(row[0] for row in conn.execute("SELECT id FROM research_tasks WHERE gap_id IN ({})".format(_placeholders(empty["gaps"])), tuple(empty["gaps"])))
        return empty

    def _item_in_scope(self, item: Mapping[str, Any], scope: Mapping[str, Any]) -> bool:
        if "all" in scope:
            return True
        entity = item["entity_type"]
        identifier = item["entity_id"]
        mapping = {"story": "stories", "claim": "claims", "evidence": "evidence", "document": "documents", "subject": "subjects", "question": "questions", "monitor": "monitors", "note": "notes", "report": "reports", "entity": "entities", "research_task": "tasks", "source": "sources"}
        primary_type = scope.get("_primary_type")
        if primary_type == "claim":
            return (entity == "claim" and identifier == scope.get("_primary_id")) or (entity == "evidence" and identifier in scope.get("evidence", set())) or (entity == "document" and identifier in scope.get("documents", set()))
        if primary_type == "evidence":
            return (entity == "evidence" and identifier == scope.get("_primary_id")) or (entity == "claim" and identifier in scope.get("claims", set())) or (entity == "document" and identifier in scope.get("documents", set()))
        if primary_type == "document":
            return entity in {"document", "evidence", "claim"} and identifier in scope.get(mapping.get(entity, ""), set())
        if primary_type == "question":
            return entity in {"question", "claim", "evidence", "note"} and (identifier in scope.get(mapping.get(entity, ""), set()) or item.get("question_id") in scope.get("questions", set()))
        if primary_type == "note":
            return entity == "note" and identifier == scope.get("_primary_id")
        if primary_type == "entity":
            return entity == "entity" and identifier == scope.get("_primary_id") or item.get("entity_id") in scope.get("entities", set()) or item.get("entity_id") in scope.get("claims", set()) and entity == "claim" or item.get("question_id") in scope.get("questions", set())
        if primary_type == "research_task":
            return entity == "research_task" and identifier == scope.get("_primary_id") or item.get("question_id") in scope.get("questions", set()) or item.get("entity_id") in scope.get("claims", set()) and entity == "claim"
        if primary_type == "report":
            return entity in {"report", "claim", "evidence"} and identifier in scope.get(mapping.get(entity, ""), set())
        if identifier in scope.get(mapping.get(entity, ""), set()):
            return True
        for key, scope_key in (("story_id", "stories"), ("document_id", "documents"), ("subject_id", "subjects"), ("question_id", "questions"), ("monitor_id", "monitors"), ("entity_id", "entities")):
            if item.get(key) and item[key] in scope.get(scope_key, set()):
                return True
        return False

    def _add_report_items(self, conn, items: dict[tuple[str, str], dict[str, Any]], terms: Sequence[str], scope: Mapping[str, set[str]]) -> None:
        if "all" in scope:
            where = " OR ".join("LOWER(lr.name || ' ' || COALESCE(rr.sections_json, '')) LIKE ?" for _ in terms)
            params = [f"%{term}%" for term in terms]
            rows = conn.execute(f"SELECT lr.id, lr.name, lr.current_revision_id FROM living_reports lr LEFT JOIN report_revisions rr ON rr.id = lr.current_revision_id WHERE {where} ORDER BY lr.updated_at DESC LIMIT 20", params).fetchall() if terms else []
        elif scope.get("reports"):
            rows = conn.execute("SELECT lr.id, lr.name, lr.current_revision_id FROM living_reports lr WHERE lr.id IN ({})".format(_placeholders(scope["reports"])), tuple(scope["reports"])).fetchall()
        else:
            rows = []
        for row in rows:
            items[("report", row["id"])] = {"entity_type": "report", "entity_id": row["id"], "title": row["name"], "body": "living report", "score": 0.0, "report_revision_id": row["current_revision_id"]}

    def _expand_item(
        self,
        conn,
        item: Mapping[str, Any],
        claim_ids: set[str],
        evidence_ids: set[str],
        note_ids: set[str],
        question_ids: set[str],
        task_ids: set[str],
        *,
        as_of: str | None = None,
    ) -> None:
        entity, identifier = item["entity_type"], item["entity_id"]
        if entity == "claim":
            claim_ids.add(identifier)
        elif entity == "evidence":
            evidence_ids.add(identifier)
            claim_ids.update(row[0] for row in conn.execute("SELECT claim_id FROM claim_evidence WHERE evidence_span_id = ?", (identifier,)))
        elif entity == "story":
            claim_ids.update(row[0] for row in conn.execute("SELECT id FROM claims WHERE story_id = ?", (identifier,)))
        elif entity == "document":
            evidence_ids.update(row[0] for row in conn.execute("SELECT es.id FROM evidence_spans es JOIN document_versions dv ON dv.id = es.document_version_id WHERE dv.document_id = ?", (identifier,)))
        elif entity == "subject":
            claim_ids.update(row[0] for row in conn.execute("SELECT c.id FROM claims c JOIN story_subjects ss ON ss.story_id = c.story_id WHERE ss.subject_id = ?", (identifier,)))
        elif entity == "question":
            question_ids.add(identifier)
            boundary = " AND julianday(created_at) <= julianday(?)" if as_of is not None else ""
            claim_params = (identifier, as_of) if as_of is not None else (identifier,)
            evidence_params = (identifier, as_of) if as_of is not None else (identifier,)
            claim_ids.update(row[0] for row in conn.execute(f"SELECT claim_id FROM research_question_claims WHERE question_id = ?{boundary}", claim_params))
            evidence_ids.update(row[0] for row in conn.execute(f"SELECT evidence_span_id FROM research_question_evidence WHERE question_id = ?{boundary}", evidence_params))
        elif entity == "note":
            if identifier.startswith("research-question:"):
                question_ids.add(identifier.split(":", 1)[1])
            else:
                note_ids.add(identifier)
        elif entity == "report":
            revision_id = item.get("report_revision_id")
            if revision_id:
                claim_ids.update(row[0] for row in conn.execute("SELECT claim_id FROM report_revision_claims WHERE revision_id = ?", (revision_id,)))
        elif entity == "entity":
            claim_ids.update(row[0] for row in conn.execute("SELECT claim_id FROM claim_entities WHERE entity_id = ?", (identifier,)))
            question_ids.update(row[0] for row in conn.execute("SELECT question_id FROM research_question_entities WHERE entity_id = ?", (identifier,)))
        elif entity == "research_task":
            task_ids.add(identifier)
            row = conn.execute("SELECT question_id, gap_id FROM research_tasks WHERE id = ?", (identifier,)).fetchone()
            if row:
                question_ids.add(row[0])
                boundary = " AND julianday(created_at) <= julianday(?)" if as_of is not None else ""
                params = (row[0], as_of) if as_of is not None else (row[0],)
                claim_ids.update(item[0] for item in conn.execute(f"SELECT claim_id FROM research_question_claims WHERE question_id = ?{boundary}", params))
        elif entity == "source":
            document_ids = [row[0] for row in conn.execute("SELECT id FROM documents WHERE source_id = ?", (identifier,))]
            if document_ids:
                evidence_ids.update(row[0] for row in conn.execute("SELECT es.id FROM evidence_spans es JOIN document_versions dv ON dv.id = es.document_version_id WHERE dv.document_id IN ({})".format(_placeholders(document_ids)), tuple(document_ids)))
                claim_ids.update(row[0] for row in conn.execute("SELECT DISTINCT claim_id FROM claim_evidence ce JOIN evidence_spans es ON es.id = ce.evidence_span_id JOIN document_versions dv ON dv.id = es.document_version_id WHERE dv.document_id IN ({})".format(_placeholders(document_ids)), tuple(document_ids)))

    def _expand_scope(self, scope: Mapping[str, set[str]], claim_ids: set[str], evidence_ids: set[str], note_ids: set[str], question_ids: set[str], task_ids: set[str]) -> None:
        claim_ids.update(scope.get("claims", set()))
        evidence_ids.update(scope.get("evidence", set()))
        note_ids.update(scope.get("notes", set()))
        question_ids.update(scope.get("questions", set()))
        task_ids.update(scope.get("tasks", set()))

    def _load_claims(self, conn, identifiers: Sequence[str]) -> dict[str, dict[str, Any]]:
        if not identifiers:
            return {}
        rows = conn.execute(
            """
            SELECT c.id, c.proposition, c.state, c.importance, c.accepted_at, c.story_id,
                   ce.relationship, es.id AS evidence_id, es.excerpt, es.locator_type, es.locator_value,
                   dv.id AS document_version_id, dv.retrieved_at, d.id AS document_id, d.title AS document_title,
                   d.canonical_url, s.id AS source_id, s.name AS source_name
            FROM claims c LEFT JOIN claim_evidence ce ON ce.claim_id = c.id
            LEFT JOIN evidence_spans es ON es.id = ce.evidence_span_id
            LEFT JOIN document_versions dv ON dv.id = es.document_version_id
            LEFT JOIN documents d ON d.id = dv.document_id
            LEFT JOIN sources s ON s.id = d.source_id
            WHERE c.id IN ({}) ORDER BY c.id, es.id
            """.format(_placeholders(identifiers)),
            tuple(identifiers),
        ).fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = result.setdefault(row["id"], {"id": row["id"], "proposition": row["proposition"], "state": row["state"], "importance": row["importance"], "accepted_at": row["accepted_at"], "story_id": row["story_id"], "evidence": []})
            if row["evidence_id"]:
                item["evidence"].append({"id": row["evidence_id"], "excerpt": row["excerpt"], "relationship": row["relationship"], "locator_type": row["locator_type"], "locator_value": row["locator_value"], "document_version_id": row["document_version_id"], "retrieved_at": row["retrieved_at"], "document_id": row["document_id"], "document_title": row["document_title"], "canonical_url": row["canonical_url"], "source_id": row["source_id"], "source_name": row["source_name"]})
        return result

    def _load_evidence(self, conn, identifiers: Sequence[str]) -> dict[str, dict[str, Any]]:
        if not identifiers:
            return {}
        rows = conn.execute(
            """
            SELECT es.id, es.excerpt, es.locator_type, es.locator_value, dv.id AS document_version_id,
                   dv.retrieved_at, d.id AS document_id, d.title AS document_title, d.canonical_url,
                   s.id AS source_id, s.name AS source_name
            FROM evidence_spans es JOIN document_versions dv ON dv.id = es.document_version_id
            JOIN documents d ON d.id = dv.document_id JOIN sources s ON s.id = d.source_id
            WHERE es.id IN ({}) ORDER BY es.id
            """.format(_placeholders(identifiers)), tuple(identifiers)
        ).fetchall()
        return {row["id"]: dict(row) for row in rows}

    def _load_notes(self, conn, identifiers: Sequence[str]) -> list[dict[str, Any]]:
        if not identifiers:
            return []
        return [dict(row) for row in conn.execute("SELECT id, object_type, object_id, note_type, body, created_at FROM notes WHERE id IN ({}) ORDER BY created_at, id".format(_placeholders(identifiers)), tuple(identifiers)).fetchall()]

    def _load_question_notes(self, conn, identifiers: Sequence[str]) -> list[dict[str, Any]]:
        if not identifiers:
            return []
        return [
            {
                **dict(row),
                "id": f"research-question:{row['id']}",
                "citation_type": "question_note",
                "citation_id": row["id"],
                "object_type": "research_question",
                "object_id": row["question_id"],
            }
            for row in conn.execute(
                "SELECT id, question_id, note_type, body, created_at FROM research_question_notes WHERE question_id IN ({}) ORDER BY created_at, id".format(_placeholders(identifiers)),
                tuple(identifiers),
            ).fetchall()
        ]

    def _load_questions(self, conn, identifiers: Sequence[str]) -> list[dict[str, Any]]:
        if not identifiers:
            return []
        return [dict(row) for row in conn.execute("SELECT id, question, status, priority, resolution_note, assessment_state, assessment_explanation FROM research_questions WHERE id IN ({}) ORDER BY id".format(_placeholders(identifiers)), tuple(identifiers)).fetchall()]

    def _load_gaps(self, conn, identifiers: Sequence[str]) -> list[dict[str, Any]]:
        if not identifiers:
            return []
        rows = conn.execute(
            """
            SELECT g.id, g.question_id, g.gap_type, g.description, g.status,
                   (SELECT t.id FROM research_tasks t WHERE t.gap_id = g.id ORDER BY t.created_at DESC, t.id DESC LIMIT 1) AS task_id
            FROM research_question_gaps g
            WHERE g.question_id IN ({}) ORDER BY g.question_id, g.created_at, g.id
            """.format(_placeholders(identifiers)),
            tuple(identifiers),
        ).fetchall()
        return [dict(row) for row in rows]

    def _load_tasks(self, conn, identifiers: Sequence[str]) -> list[dict[str, Any]]:
        if not identifiers:
            return []
        rows = conn.execute(
            "SELECT id, question_id, gap_id, task_no, mode, status, outcome_json, error_code FROM research_tasks WHERE id IN ({}) ORDER BY created_at, id".format(_placeholders(identifiers)),
            tuple(identifiers),
        ).fetchall()
        return [{**dict(row), "outcome": _load_json(row["outcome_json"], {})} for row in rows]

    def _load_reports(self, conn, identifiers: Sequence[str]) -> list[dict[str, Any]]:
        if not identifiers:
            return []
        rows = conn.execute("SELECT lr.id, lr.name, lr.current_revision_id, rr.current_status, rr.sections_json FROM living_reports lr LEFT JOIN report_revisions rr ON rr.id = lr.current_revision_id WHERE lr.id IN ({}) ORDER BY lr.id".format(_placeholders(identifiers)), tuple(identifiers)).fetchall()
        return [{**dict(row), "sections": _load_json(row["sections_json"], {})} for row in rows]

    def _compose(
        self,
        run_id: str,
        conversation_id: str,
        turn_number: int,
        prompt: str,
        retrieved: Mapping[str, Any],
        context_budget: int,
        *,
        synthesis_router: Any | None = None,
        synthesis_work_id: str | None = None,
    ) -> dict[str, Any]:
        if synthesis_router is not None:
            return self._compose_with_router(
                run_id,
                conversation_id,
                turn_number,
                prompt,
                retrieved,
                context_budget,
                synthesis_router,
                synthesis_work_id=synthesis_work_id,
            )
        citation_map: dict[tuple[str, str], dict[str, Any]] = {}
        statements: list[dict[str, Any]] = []
        packet_ids = set(retrieved.get("packet_ids", []))

        def cite(object_type: str, object_id: str, label: str, *, kind: str, **extra: Any) -> str:
            if packet_ids and f"{object_type}:{object_id}" not in packet_ids:
                return ""
            key = (object_type, object_id)
            existing = citation_map.get(key)
            if existing:
                return existing["id"]
            if len(citation_map) >= self.max_citations:
                return ""
            identifier = f"cite_{len(citation_map) + 1}"
            citation_map[key] = {"id": identifier, "object_type": object_type, "object_id": object_id, "label": label[:300], "kind": kind, **extra}
            return identifier

        def add_statement(text: str, classification: str, citation_ids: Sequence[str]) -> None:
            ids = [value for value in citation_ids if value]
            if not text.strip() or not ids:
                return
            statements.append({"id": f"statement_{len(statements) + 1}", "text": text[:2_000], "classification": classification, "citation_ids": list(dict.fromkeys(ids))})

        stale_count = 0
        story_ids: set[str] = set()
        claims_list = list(retrieved.get("claims", {}).values())
        conflicting_claim_ids: set[str] = set()
        conflict_pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for index, left in enumerate(claims_list):
            left_tokens = set(TOKEN_RE.findall(left.get("proposition", "").casefold()))
            left_negated = bool(left_tokens & {"no", "not", "never", "without", "denied", "denies"})
            left_base = left_tokens - {"no", "not", "never", "without", "denied", "denies", "did", "does"}
            for right in claims_list[index + 1:]:
                right_tokens = set(TOKEN_RE.findall(right.get("proposition", "").casefold()))
                right_negated = bool(right_tokens & {"no", "not", "never", "without", "denied", "denies"})
                right_base = right_tokens - {"no", "not", "never", "without", "denied", "denies", "did", "does"}
                overlap = len(left_base & right_base) / max(1, min(len(left_base), len(right_base)))
                if left_negated != right_negated and overlap >= 0.7:
                    conflicting_claim_ids.update((left["id"], right["id"]))
                    conflict_pairs.append((left, right))
        for claim in retrieved.get("claims", {}).values():
            if claim.get("story_id") is not None:
                story_ids.add(claim["story_id"])
            claim_citation = cite("claim", claim["id"], claim["proposition"], kind="claim", state=claim["state"])
            evidence_citations: list[str] = []
            support = []
            contradictions = []
            for evidence in claim["evidence"]:
                if evidence["id"] not in retrieved.get("evidence", {}):
                    continue
                evidence_citation = cite(
                    "evidence", evidence["id"], evidence["excerpt"], kind="evidence",
                    document_id=evidence["document_id"], document_version_id=evidence["document_version_id"],
                    source_id=evidence["source_id"], retrieved_at=evidence["retrieved_at"],
                    locator_type=evidence["locator_type"], locator_value=evidence["locator_value"],
                )
                evidence_citations.append(evidence_citation)
                (contradictions if evidence["relationship"] == "contradicts" else support).append(evidence)
                if _is_stale(evidence["retrieved_at"], stale_after_days=self.stale_after_days, reference_time=retrieved.get("as_of")):
                    stale_count += 1
            source_citations = []
            source_pairs = {(evidence.get("source_id"), evidence.get("source_name")) for evidence in claim["evidence"] if evidence["id"] in retrieved.get("evidence", {}) and evidence.get("source_id")}
            for source_id, source_name in sorted(source_pairs):
                source_citations.append(cite("source", source_id, source_name or source_id, kind="source"))
            all_citations = [claim_citation, *evidence_citations, *source_citations]
            if claim["id"] in conflicting_claim_ids:
                continue
            if contradictions or claim["state"] == "disputed":
                add_statement(f"The record conflicts about: {claim['proposition']}", "contradiction", all_citations)
            elif support and claim["state"] in {"supported", "partially_supported"}:
                add_statement(claim["proposition"], "fact", all_citations)
            elif all_citations:
                add_statement(f"The record does not fully establish: {claim['proposition']}", "uncertainty", all_citations)

        for left, right in conflict_pairs:
            left_citation = cite("claim", left["id"], left["proposition"], kind="claim", state=left["state"])
            right_citation = cite("claim", right["id"], right["proposition"], kind="claim", state=right["state"])
            evidence_citations = []
            for claim in (left, right):
                evidence_citations.extend(
                    cite("evidence", evidence["id"], evidence["excerpt"], kind="evidence", document_id=evidence.get("document_id"), document_version_id=evidence.get("document_version_id"), source_id=evidence.get("source_id"), retrieved_at=evidence.get("retrieved_at"), locator_type=evidence.get("locator_type"), locator_value=evidence.get("locator_value"))
                    for evidence in claim["evidence"]
                    if evidence["id"] in retrieved.get("evidence", {})
                )
            add_statement(f"The retrieved Claims disagree: {left['proposition']} / {right['proposition']}", "contradiction", [left_citation, right_citation, *evidence_citations])

        for note in retrieved.get("notes", []):
            citation_type = note.get("citation_type", "note")
            citation_id = note.get("citation_id", note["id"])
            note_citation = cite(citation_type, citation_id, note["body"], kind=note["note_type"])
            if note["note_type"] == "hypothesis":
                add_statement(f"User hypothesis (not verified): {note['body']}", "user_hypothesis", [note_citation])
            else:
                add_statement(f"User note: {note['body']}", "context", [note_citation])

        for question in retrieved.get("questions", []):
            question_citation = cite("question", question["id"], question["question"], kind="question", state=question["status"], assessment_state=question.get("assessment_state"))
            if question["status"] != "resolved" or question.get("assessment_state") not in {"supported", "resolved"}:
                add_statement(f"Question lifecycle: {question['status']}. Evidence assessment: {question.get('assessment_state', 'open')}. {question['question']}", "uncertainty", [question_citation])

        for gap in retrieved.get("gaps", []):
            if gap.get("status") in {"open", "pursuing"}:
                gap_citation = cite("research_gap", gap["id"], gap["description"], kind="research_gap", question_id=gap["question_id"], state=gap["status"])
                add_statement(f"Open evidence gap: {gap['description']}", "uncertainty", [gap_citation])

        for task in retrieved.get("tasks", []):
            task_citation = cite("research_task", task["id"], f"Research task {task['task_no']}", kind="research_task", question_id=task["question_id"], gap_id=task["gap_id"], state=task["status"])
            if task.get("status") not in {"completed", "completed_with_evidence"}:
                add_statement(f"Research task state: {task['status']}", "uncertainty", [task_citation])

        for correction in retrieved.get("corrections", []):
            correction_citation = cite(
                "story_correction",
                correction["id"],
                correction.get("operation_type", "Story correction"),
                kind="story_correction",
                reason_code=correction.get("reason_code"),
                origin=correction.get("origin"),
                occurred_at=correction.get("occurred_at"),
            )
            reason = correction.get("reason") or "No human reason was recorded."
            operation = str(correction.get("operation_type", "correction")).replace("_", " ")
            add_statement(f"Story organization history: {operation}; {reason}", "context", [correction_citation])

        for report in retrieved.get("reports", []):
            citation_type = "report_revision" if report["current_revision_id"] else "report"
            citation_id = report["current_revision_id"] or report["id"]
            report_citation = cite(citation_type, citation_id, report["name"], kind="report", report_id=report["id"])
            status = report.get("current_status")
            if status:
                add_statement(f"Report status: {status}", "fact", [report_citation])

        for item in retrieved.get("items", []):
            if item["entity_type"] in {"story", "subject", "document", "entity", "source", "watch", "monitor"}:
                cite(item["entity_type"], item["entity_id"], item.get("title", item["entity_id"]), kind=item["entity_type"])

        source_ids = {evidence.get("source_id") for evidence in retrieved.get("evidence", {}).values() if evidence.get("source_id")}
        document_ids = {evidence.get("document_id") for evidence in retrieved.get("evidence", {}).values() if evidence.get("document_id")}
        if source_ids and statements:
            source_citations = [cite("source", source_id, next((evidence.get("source_name") for evidence in retrieved.get("evidence", {}).values() if evidence.get("source_id") == source_id), source_id), kind="source") for source_id in sorted(source_ids)]
            add_statement(f"The retrieved material represents {len(source_ids)} distinct Source record{'' if len(source_ids) == 1 else 's'} across {len(document_ids)} Document{'' if len(document_ids) == 1 else 's'}; Documents may share known dependency groups, so this is not proof of separate confirmation.", "context", source_citations)

        fact_citations = [citation_id for statement in statements if statement["classification"] == "fact" for citation_id in statement["citation_ids"]]
        if fact_citations and re.search(r"\b(?:why|how|suggest|likely|mean|implication)\b", prompt.casefold()):
            add_statement("Inference from the retrieved record: the cited observations are related to the question, but this interpretation is not itself a stored Claim.", "inference", fact_citations[:5])
        ambiguous = retrieved.get("scope", {}).get("type") == "global" and len(story_ids) > 1
        story_citations = [citation["id"] for citation in citation_map.values() if citation["object_type"] == "story"]
        if ambiguous:
            add_statement("Several Stories match this question; the answer is qualified by that ambiguity.", "uncertainty", story_citations or [citation["id"] for citation in citation_map.values()][:1])
        if stale_count and statements:
            add_statement("Some supporting Evidence is stale and should be rechecked before treating it as current.", "uncertainty", [citation["id"] for citation in citation_map.values() if citation["kind"] == "evidence"][:3])
        if retrieved.get("context_truncated") and statements:
            add_statement("The context budget excluded lower-ranked records; this answer is limited to the retrieved evidence.", "uncertainty", [citation["id"] for citation in citation_map.values()][:1])

        if retrieved.get("as_of") and citation_map:
            add_statement(
                f"As of {retrieved['as_of']}, this answer is limited to knowledge available by that time; later evidence and corrections are excluded.",
                "context",
                [next(iter(citation_map.values()))["id"]],
            )

        citations = list(citation_map.values())
        conn = storage.connect(self.db_path)
        try:
            citations = [self._resolve_citation(conn, citation, packet_ids=packet_ids, as_of=retrieved.get("as_of")) for citation in citations]
        finally:
            conn.close()
        if not retrieved.get("grounding_evidence_count"):
            return self._refused_result(run_id, conversation_id, turn_number, "insufficient_evidence", "Newsroom does not have enough qualifying Claim and Evidence records to answer that question.", retrieval=self._retrieval_metadata(retrieved, context_budget), citations=citations)
        status = "qualified" if any(item["classification"] in {"uncertainty", "contradiction"} for item in statements) else "answered"
        answer_lines = [f"{item['classification'].replace('_', ' ').capitalize()}: {item['text']} [{', '.join(item['citation_ids'])}]" for item in statements]
        return {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "status": status,
            "answer": "\n".join(answer_lines)[:12_000],
            "statements": statements,
            "citations": citations,
            "retrieval": self._retrieval_metadata(retrieved, context_budget, stale_count=stale_count, ambiguous=ambiguous),
            "provider_route": "local_deterministic",
            "estimated_cost_usd": 0.0,
            "refusal_code": None,
        }

    def _compose_with_router(
        self,
        run_id: str,
        conversation_id: str,
        turn_number: int,
        prompt: str,
        retrieved: Mapping[str, Any],
        context_budget: int,
        synthesis_router: Any,
        *,
        synthesis_work_id: str | None,
    ) -> dict[str, Any]:
        """Use the richer Full retrieval packet with a contract-bound provider."""
        from .ai import ClaimDraft

        drafts = [
            ClaimDraft(
                proposition=" ".join(
                    filter(
                        None,
                        (
                            claim.get("proposition"),
                            *(
                                f"Evidence: {evidence.get('excerpt')}"
                                for evidence in claim.get("evidence", [])
                                if evidence.get("id") in retrieved.get("evidence", {})
                            ),
                        ),
                    )
                )
            )
            for claim in retrieved.get("claims", {}).values()
        ]
        if not retrieved.get("grounding_evidence_count") or not drafts:
            return self._refused_result(
                run_id,
                conversation_id,
                turn_number,
                "insufficient_evidence",
                "Newsroom does not have enough qualifying Claim and Evidence records to answer that question.",
                retrieval=self._retrieval_metadata(retrieved, context_budget),
            )
        output = synthesis_router.synthesis(prompt, drafts, work_id=synthesis_work_id)
        successful = [
            event
            for event in getattr(synthesis_router, "last_execution_events", ())
            if getattr(event, "outcome", None) in {"succeeded", "low_confidence"}
        ]
        event = successful[-1] if successful else None
        citations: list[dict[str, Any]] = []
        seen_documents: set[str] = set()
        for claim in retrieved.get("claims", {}).values():
            for evidence in claim.get("evidence", []):
                if evidence.get("id") not in retrieved.get("evidence", {}) or evidence.get("document_id") in seen_documents:
                    continue
                document_id = evidence.get("document_id")
                if not document_id:
                    continue
                seen_documents.add(document_id)
                citations.append(
                    {
                        "id": f"cite_{len(citations) + 1}",
                        "object_type": "evidence",
                        "object_id": evidence["id"],
                        "document_id": document_id,
                        "document_version_id": evidence.get("document_version_id"),
                        "source_id": evidence.get("source_id"),
                        "label": evidence.get("excerpt", "")[:300],
                        "kind": "evidence",
                        "retrieved_at": evidence.get("retrieved_at"),
                    }
                )
                if len(citations) >= self.max_citations:
                    break
            if len(citations) >= self.max_citations:
                break
        conn = storage.connect(self.db_path)
        try:
            citations = [
                self._resolve_citation(
                    conn,
                    citation,
                    packet_ids=set(retrieved.get("packet_ids", [])),
                    as_of=retrieved.get("as_of"),
                )
                for citation in citations
            ]
        finally:
            conn.close()
        answer = output.model_dump() if hasattr(output, "model_dump") else dict(output)
        route = getattr(event, "route", "execution_unavailable") if event is not None else "execution_unavailable"
        cost = float(getattr(event, "estimated_cost_usd", 0.0) or 0.0) if event is not None else 0.0
        return {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "status": "answered",
            "answer": str(answer.get("summary") or answer.get("headline") or ""),
            "statements": [],
            "citations": citations,
            "retrieval": self._retrieval_metadata(retrieved, context_budget),
            "provider_route": route,
            "estimated_cost_usd": cost,
            "refusal_code": None,
        }

    def _retrieval_metadata(self, retrieved: Mapping[str, Any], context_budget: int, *, stale_count: int = 0, ambiguous: bool = False) -> dict[str, Any]:
        items = list(retrieved.get("items", []))
        return {
            "candidate_count": len(items),
            "entity_types": sorted({item["entity_type"] for item in items}),
            "correction_count": len(retrieved.get("corrections", [])),
            "retrieved_object_ids": [f"{item['entity_type']}:{item['entity_id']}" for item in items[:100]],
            "packet_ids": sorted(retrieved.get("packet_ids", []))[:300],
            "context_units": int(retrieved.get("context_units", 0)),
            "context_budget": context_budget,
            "context_truncated": bool(retrieved.get("context_truncated")),
            "stale_evidence_count": stale_count,
            "ambiguous": ambiguous,
            "scope": retrieved.get("scope", {}),
            "query_term_count": len(retrieved.get("terms", [])),
            "research_options": [
                {"question_id": gap["question_id"], "gap_id": gap["id"], "description": gap["description"], "status": gap["status"]}
                for gap in retrieved.get("gaps", []) if gap.get("status") in {"open", "pursuing"}
            ][:20],
            "grounding_evidence_count": int(retrieved.get("grounding_evidence_count", 0)),
            "retrieval_ranking": retrieved.get("retrieval_ranking"),
            "retrieval_limit": int(retrieved.get("retrieval_limit", 100)),
            "as_of": retrieved.get("as_of"),
        }

    def _refused_result(self, run_id: str, conversation_id: str, turn_number: int, code: str, message: str, *, retrieval: dict[str, Any] | None = None, citations: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "status": "refused",
            "answer": message,
            "statements": [],
            "citations": citations or [],
            "retrieval": retrieval or {"candidate_count": 0, "entity_types": [], "retrieved_object_ids": [], "packet_ids": [], "context_units": 0, "context_budget": 0, "context_truncated": False, "stale_evidence_count": 0, "ambiguous": False, "scope": {}, "query_term_count": 0, "research_options": []},
            "provider_route": "local_deterministic",
            "estimated_cost_usd": 0.0,
            "refusal_code": code,
        }

    def _cancelled_result(self, run_id: str, conversation_id: str, turn_number: int) -> dict[str, Any]:
        result = self._refused_result(run_id, conversation_id, turn_number, "cancelled", "This Ask Newsroom run was cancelled.")
        result["status"] = "cancelled"
        return result

    def _finish(self, run_id: str, result: dict[str, Any], *, provider_route: str | None = None) -> dict[str, Any]:
        now = utc_now()
        route = provider_route or result.get("provider_route", "local_deterministic")
        conn = storage.connect(self.db_path)
        prompt_row = None
        try:
            with storage.write_tx(conn):
                conn.execute(
                    "UPDATE ask_runs SET status = ?, answer_json = ?, retrieval_json = ?, citations_json = ?, refusal_code = ?, context_units = ?, provider_route = ?, estimated_cost_usd = ?, completed_at = ? WHERE id = ?",
                    (result["status"], json.dumps({"answer": result.get("answer", ""), "statements": result.get("statements", [])}, sort_keys=True), json.dumps(result.get("retrieval", {}), sort_keys=True), json.dumps(result.get("citations", []), sort_keys=True), result.get("refusal_code"), int(result.get("retrieval", {}).get("context_units", 0)), route, float(result.get("estimated_cost_usd", 0.0)), now, run_id),
                )
                conn.execute("UPDATE ask_conversations SET updated_at = ? WHERE id = (SELECT conversation_id FROM ask_runs WHERE id = ?)", (now, run_id))
                prompt_row = conn.execute("SELECT prompt_hash, prompt_length FROM ask_runs WHERE id = ?", (run_id,)).fetchone()
        finally:
            conn.close()
        result["provider_route"] = route
        if prompt_row is not None:
            result["prompt_hash"] = prompt_row["prompt_hash"]
            result["prompt_length"] = prompt_row["prompt_length"]
        return result

    def _run_result(self, row) -> dict[str, Any]:
        answer = _load_json(row["answer_json"], {})
        return {
            "run_id": row["id"],
            "conversation_id": row["conversation_id"],
            "turn_number": row["turn_number"],
            "prompt_hash": row["prompt_hash"],
            "prompt_length": row["prompt_length"],
            "status": row["status"],
            "answer": answer.get("answer", ""),
            "statements": answer.get("statements", []),
            "retrieval": _load_json(row["retrieval_json"], {}),
            "citations": _load_json(row["citations_json"], []),
            "refusal_code": row["refusal_code"],
            "context_units": row["context_units"],
            "provider_route": row["provider_route"],
            "estimated_cost_usd": row["estimated_cost_usd"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
        }

    def _resolve_citation(self, conn, citation: dict[str, Any], *, packet_ids: set[str] | None = None, as_of: str | None = None) -> dict[str, Any]:
        object_type = citation.get("object_type")
        object_id = citation.get("object_id")
        if not isinstance(object_type, str) or not isinstance(object_id, str):
            raise DomainValidation("citation object type and object id are required")
        if packet_ids and f"{object_type}:{object_id}" not in packet_ids:
            raise DomainConflict(f"citation target {object_id} was not part of the retrieval packet")
        table_map = {
            "story": ("stories", "id", "deleted_at IS NULL"),
            "claim": ("claims", "id", "1 = 1"),
            "evidence": ("evidence_spans", "id", "1 = 1"),
            "document": ("documents", "id", "1 = 1"),
            "report": ("living_reports", "id", "1 = 1"),
            "report_revision": ("report_revisions", "id", "1 = 1"),
            "question": ("research_questions", "id", "deleted_at IS NULL"),
            "subject": ("subjects", "id", "deleted_at IS NULL"),
            "monitor": ("monitors", "id", "1 = 1"),
            "note": ("notes", "id", "1 = 1"),
            "question_note": ("research_question_notes", "id", "1 = 1"),
            "source": ("sources", "id", "deleted_at IS NULL"),
            "entity": ("entities", "id", "status <> 'merged'"),
            "research_gap": ("research_question_gaps", "id", "1 = 1"),
            "research_task": ("research_tasks", "id", "1 = 1"),
            "watch": ("watches", "id", "1 = 1"),
            "article_analysis": ("article_analyses", "id", "1 = 1"),
            "story_correction": ("story_corrections", "id", "1 = 1"),
        }
        definition = table_map.get(object_type)
        if definition is None:
            raise DomainValidation("citation object type is not resolvable")
        table, key, condition = definition
        found = conn.execute(f"SELECT 1 FROM {table} WHERE {key} = ? AND {condition}", (object_id,)).fetchone()
        if found is None:
            raise DomainConflict(f"citation target {object_id} could not be resolved")
        if as_of is not None and not self.temporal.eligible_as_of(
            object_type, object_id, as_of, conn=conn
        ):
            raise DomainConflict(f"citation target {object_id} was not eligible at as_of")
        citation["resolvable"] = True
        return citation


__all__ = ["AskService", "SCOPE_TYPES"]
