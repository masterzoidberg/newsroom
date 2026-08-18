"""Persistent monitor policies, scope approval, and local relevance evaluation.

The module keeps monitoring state in SQLite and makes scope changes explicit. A
monitor evaluates the last approved scope snapshot; pending or rejected
suggestions never enter that snapshot and therefore cannot create broader work.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import storage
from .acquisition import (
    AcquisitionBlocked,
    AcquisitionError,
    AcquisitionService,
    AcquisitionTimeout,
    AcquisitionTooLarge,
    FeedParseError,
)
from .ai import LocalRelevanceProvider, RelevanceOutput
from .domain import DomainConflict, DomainNotFound, DomainValidation, new_id, normalized_text, utc_now
from .jobs import BudgetService, MONITOR_CHECK_JOB_TYPE
from .worker import RetryableJobFailure


TARGET_TABLES = {
    "topic": "topics",
    "subject": "subjects",
    "story": "stories",
    "source": "sources",
    "research_question": "research_questions",
}
ALLOWED_CHANNELS = frozenset({"rss", "atom", "direct_http", "page", "search", "api", "local"})
POLICY_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
SUGGESTION_TYPES = frozenset(
    {"term", "synonym", "acronym", "alias", "broader", "narrower", "related_concept", "ambiguity", "exclude"}
)


def _timestamp(value: str | datetime | None = None) -> str:
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        parsed = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise DomainValidation("timestamp must be an ISO-8601 value") from exc
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _plus_seconds(value: str, seconds: int) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _timestamp(parsed + timedelta(seconds=seconds))


def _seconds_between(later: str, earlier: str) -> int:
    later_dt = datetime.fromisoformat(later.replace("Z", "+00:00"))
    earlier_dt = datetime.fromisoformat(earlier.replace("Z", "+00:00"))
    return max(1, int((later_dt - earlier_dt).total_seconds()))


def _decode(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError) as exc:
        raise DomainValidation("stored monitor JSON is invalid") from exc


def _json_object(value: Any, field: str) -> str:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise DomainValidation(f"{field} must be an object")
    try:
        encoded = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise DomainValidation(f"{field} must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > 20_000:
        raise DomainValidation(f"{field} exceeds the 20KB limit")
    return encoded


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DomainValidation(f"{field} must be a nonnegative integer")
    return value


def _bounded_seconds(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 31_536_000:
        raise DomainValidation(f"{field} must be an integer between 1 and 31536000")
    return value


def _as_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _page(conn: sqlite3.Connection, table: str, *, where: str = "1 = 1", params: Sequence[Any] = (), page: int = 1, page_size: int = 25, order_by: str = "id") -> dict[str, Any]:
    if isinstance(page, bool) or isinstance(page_size, bool) or page < 1 or not 1 <= page_size <= 100:
        raise DomainValidation("page must be >= 1 and page_size must be between 1 and 100")
    query_params = list(params)
    total = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", query_params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE {where} ORDER BY {order_by} LIMIT ? OFFSET ?",
        [*query_params, page_size, (page - 1) * page_size],
    ).fetchall()
    return {"items": [_as_dict(row) for row in rows], "page": page, "page_size": page_size, "total": total}


def _policy_output(row: sqlite3.Row) -> dict[str, Any]:
    result = _as_dict(row)
    for field in ("allowed_channels", "escalation_rules", "backoff_rules", "retirement_criteria"):
        result[field] = _decode(result[field], [] if field == "allowed_channels" else {})
    return result


def _monitor_output(row: sqlite3.Row) -> dict[str, Any]:
    return _as_dict(row)


class MonitoringPolicyService:
    """CRUD and validation for monitor policy budgets and cadence bounds."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _validated(self, data: Mapping[str, Any], *, existing: Mapping[str, Any] | None = None) -> dict[str, Any]:
        source = {**(existing or {}), **dict(data)}
        name = str(source.get("name", "")).strip()
        if not name or len(name) > 200:
            raise DomainValidation("policy name must be between 1 and 200 characters")
        channels = source.get("allowed_channels", [])
        if not isinstance(channels, Sequence) or isinstance(channels, (str, bytes)):
            raise DomainValidation("allowed_channels must be an array")
        channels = [str(channel).strip().casefold() for channel in channels]
        if len(channels) != len(set(channels)) or any(channel not in ALLOWED_CHANNELS for channel in channels):
            raise DomainValidation("allowed_channels contains an unsupported or duplicate channel")
        base = _bounded_seconds(source.get("base_cadence_seconds"), "base_cadence_seconds")
        minimum = _bounded_seconds(source.get("min_cadence_seconds"), "min_cadence_seconds")
        maximum = _bounded_seconds(source.get("max_cadence_seconds"), "max_cadence_seconds")
        if not minimum <= base <= maximum:
            raise DomainValidation("cadence bounds must satisfy min <= base <= max")
        priority = str(source.get("priority", "normal")).casefold()
        if priority not in POLICY_PRIORITIES:
            raise DomainValidation("priority must be low, normal, high, or urgent")
        paid_budget = source.get("paid_budget_usd", 0.0)
        if isinstance(paid_budget, bool) or not isinstance(paid_budget, (int, float)) or not math.isfinite(float(paid_budget)) or paid_budget < 0:
            raise DomainValidation("paid_budget_usd must be a finite nonnegative number")
        return {
            "name": name,
            "allowed_channels": channels,
            "base_cadence_seconds": base,
            "min_cadence_seconds": minimum,
            "max_cadence_seconds": maximum,
            "priority": priority,
            "query_budget": _nonnegative_int(source.get("query_budget", 0), "query_budget"),
            "paid_budget_usd": float(paid_budget),
            "local_model_budget": _nonnegative_int(source.get("local_model_budget", 0), "local_model_budget"),
            "escalation_rules": dict(source.get("escalation_rules") or {}),
            "backoff_rules": dict(source.get("backoff_rules") or {}),
            "retirement_criteria": dict(source.get("retirement_criteria") or {}),
        }

    def create(self, data: Mapping[str, Any]) -> dict[str, Any]:
        identifier = str(data.get("id") or new_id("pol"))
        now = utc_now()
        values = self._validated(data)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    INSERT INTO monitoring_policies
                        (id, name, allowed_channels, base_cadence_seconds, min_cadence_seconds,
                         max_cadence_seconds, priority, query_budget, paid_budget_usd,
                         local_model_budget, escalation_rules, backoff_rules, retirement_criteria,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identifier,
                        values["name"],
                        json.dumps(values["allowed_channels"], separators=(",", ":")),
                        values["base_cadence_seconds"],
                        values["min_cadence_seconds"],
                        values["max_cadence_seconds"],
                        values["priority"],
                        values["query_budget"],
                        values["paid_budget_usd"],
                        values["local_model_budget"],
                        _json_object(values["escalation_rules"], "escalation_rules"),
                        _json_object(values["backoff_rules"], "backoff_rules"),
                        _json_object(values["retirement_criteria"], "retirement_criteria"),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("monitoring policy already exists") from exc
        finally:
            conn.close()
        return self.get(identifier)

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM monitoring_policies WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("monitoring policy not found")
            return _policy_output(row)
        finally:
            conn.close()

    def list(self, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            result = _page(conn, "monitoring_policies", page=page, page_size=page_size, order_by="name COLLATE NOCASE, id")
            result["items"] = [_policy_output(conn.execute("SELECT * FROM monitoring_policies WHERE id = ?", (item["id"],)).fetchone()) for item in result["items"]]
            return result
        finally:
            conn.close()

    def update(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        current = self.get(identifier)
        values = self._validated(data, existing=current)
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                result = conn.execute(
                    """
                    UPDATE monitoring_policies SET name = ?, allowed_channels = ?,
                        base_cadence_seconds = ?, min_cadence_seconds = ?, max_cadence_seconds = ?,
                        priority = ?, query_budget = ?, paid_budget_usd = ?, local_model_budget = ?,
                        escalation_rules = ?, backoff_rules = ?, retirement_criteria = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        values["name"],
                        json.dumps(values["allowed_channels"], separators=(",", ":")),
                        values["base_cadence_seconds"],
                        values["min_cadence_seconds"],
                        values["max_cadence_seconds"],
                        values["priority"],
                        values["query_budget"],
                        values["paid_budget_usd"],
                        values["local_model_budget"],
                        _json_object(values["escalation_rules"], "escalation_rules"),
                        _json_object(values["backoff_rules"], "backoff_rules"),
                        _json_object(values["retirement_criteria"], "retirement_criteria"),
                        now,
                        identifier,
                    ),
                )
                if result.rowcount != 1:
                    raise DomainNotFound("monitoring policy not found")
        finally:
            conn.close()
        return self.get(identifier)


_TOKEN_RE = re.compile(r"[\w][\w-]*", re.UNICODE)


def _tokens(value: str) -> set[str]:
    return {item.casefold() for item in _TOKEN_RE.findall(value)}


def _contains(text: str, term: str) -> bool:
    normalized_term = normalized_text(term)
    if not normalized_term:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized_text(text)) is not None


@dataclass(frozen=True)
class RelevanceScope:
    exact_terms: tuple[str, ...] = ()
    vocabulary: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    concepts: tuple[str, ...] = ()
    semantic_terms: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    semantic_threshold: float = 0.6

    def __post_init__(self):
        for field in ("exact_terms", "vocabulary", "entities", "concepts", "semantic_terms", "exclusions"):
            values = tuple(str(item).strip() for item in getattr(self, field) if str(item).strip())
            object.__setattr__(self, field, values)
        if not 0.0 <= self.semantic_threshold <= 1.0:
            raise DomainValidation("semantic_threshold must be between 0 and 1")

    def all_terms(self) -> tuple[str, ...]:
        return self.exact_terms + self.vocabulary + self.entities + self.concepts + self.semantic_terms

    def as_dict(self) -> dict[str, Any]:
        return {
            "exact_terms": list(self.exact_terms),
            "vocabulary": list(self.vocabulary),
            "entities": list(self.entities),
            "concepts": list(self.concepts),
            "semantic_terms": list(self.semantic_terms),
            "exclusions": list(self.exclusions),
            "semantic_threshold": self.semantic_threshold,
        }


@dataclass(frozen=True)
class RelevanceResult:
    relevant: bool
    stage: str
    score: float
    matched_terms: tuple[str, ...] = ()
    reason: str = ""
    paid_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "relevant": self.relevant,
            "stage": self.stage,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
            "reason": self.reason,
            "paid_used": self.paid_used,
        }


class RelevanceCascade:
    """Deterministic, local-first relevance cascade with no paid fallback."""

    def __init__(
        self,
        *,
        semantic_similarity: Callable[[str, Sequence[str]], float] | None = None,
        ai_classifier: Callable[[str, RelevanceScope], tuple[bool, float, str] | RelevanceOutput | Mapping[str, Any]] | None = None,
    ):
        self.semantic_similarity = semantic_similarity or self._local_similarity
        self.ai_classifier = ai_classifier or self._local_classifier

    @staticmethod
    def _local_similarity(text: str, terms: Sequence[str]) -> float:
        candidate = _tokens(text)
        if not candidate or not terms:
            return 0.0
        scores = []
        for term in terms:
            target = _tokens(term)
            if not target:
                continue
            scores.append(len(candidate & target) / len(candidate | target))
        return max(scores, default=0.0)

    @staticmethod
    def _local_classifier(text: str, scope: RelevanceScope) -> RelevanceOutput:
        return LocalRelevanceProvider().classify(text, scope.all_terms())

    def evaluate(self, text: str, scope: RelevanceScope) -> RelevanceResult:
        text = str(text).strip()
        if not text:
            raise DomainValidation("candidate text must not be empty")
        excluded = tuple(term for term in scope.exclusions if _contains(text, term))
        if excluded:
            return RelevanceResult(False, "excluded", 1.0, excluded, "candidate matched an explicit exclusion")
        for stage, terms in (
            ("exact", scope.exact_terms),
            ("vocabulary", scope.vocabulary),
            ("entity", scope.entities),
            ("concept", scope.concepts),
        ):
            matched = tuple(term for term in terms if _contains(text, term))
            if matched:
                return RelevanceResult(True, stage, 1.0, matched, f"{stage} scope match")
        semantic_score = float(self.semantic_similarity(text, scope.semantic_terms or scope.concepts))
        if not math.isfinite(semantic_score) or not 0.0 <= semantic_score <= 1.0:
            raise DomainValidation("semantic similarity must be a finite value between 0 and 1")
        if semantic_score >= scope.semantic_threshold:
            return RelevanceResult(True, "semantic", semantic_score, (), "semantic similarity exceeded threshold")
        output = self.ai_classifier(text, scope)
        if isinstance(output, RelevanceOutput):
            relevant, confidence, signal = output.relevant, output.confidence, output.signal
        elif isinstance(output, Mapping):
            parsed = RelevanceOutput.model_validate(output)
            relevant, confidence, signal = parsed.relevant, parsed.confidence, parsed.signal
        else:
            try:
                relevant, confidence, signal = output
            except (TypeError, ValueError) as exc:
                raise DomainValidation("AI classifier must return (relevant, confidence, signal)") from exc
            if isinstance(relevant, bool) is False or not 0.0 <= float(confidence) <= 1.0 or not str(signal).strip():
                raise DomainValidation("AI classifier returned an invalid result")
        accepted = bool(relevant) and float(confidence) >= scope.semantic_threshold
        return RelevanceResult(accepted, "ai" if accepted else "none", float(confidence), (), str(signal), False)


def _scope_for_target(conn: sqlite3.Connection, target_type: str, target_id: str) -> RelevanceScope:
    table = TARGET_TABLES.get(target_type)
    if table is None:
        raise DomainValidation("unsupported monitor target type")
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (target_id,)).fetchone()
    if row is None:
        raise DomainNotFound("monitor target not found")
    if target_type == "topic":
        terms = conn.execute(
            "SELECT term, term_type, concept_kind FROM topic_terms WHERE topic_id = ? ORDER BY id",
            (target_id,),
        ).fetchall()
        return RelevanceScope(
            exact_terms=tuple(term[0] for term in terms if term[1] == "include" and term[2] == "term"),
            vocabulary=tuple(term[0] for term in terms if term[1] == "alias"),
            entities=tuple(term[0] for term in terms if term[1] == "entity"),
            concepts=tuple(term[0] for term in terms if term[2] == "related_concept"),
            semantic_terms=tuple(term[0] for term in terms if term[1] != "exclude"),
            exclusions=tuple(term[0] for term in terms if term[1] == "exclude"),
        )
    if target_type == "subject":
        aliases = tuple(item[0] for item in conn.execute("SELECT alias FROM subject_aliases WHERE subject_id = ? ORDER BY id", (target_id,)))
        return RelevanceScope(exact_terms=(row[1],), vocabulary=aliases, entities=(row[1],))
    if target_type == "source":
        values = tuple(str(row[index]) for index in (1, 2, 3) if row[index])
        return RelevanceScope(exact_terms=values)
    if target_type == "story":
        revision = conn.execute(
            "SELECT headline, summary, why_it_matters FROM story_revisions WHERE story_id = ? ORDER BY revision_number DESC LIMIT 1",
            (target_id,),
        ).fetchone()
        values = tuple(str(item) for item in (revision or ()) if item)
        return RelevanceScope(exact_terms=(values[0],) if values else (), concepts=values[1:], semantic_terms=values)
    return RelevanceScope(exact_terms=(row[1],))


class MonitorService:
    """Validated monitor lifecycle, append-only activity, and scope snapshots."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @staticmethod
    def _target_exists(conn: sqlite3.Connection, target_type: str, target_id: str) -> bool:
        table = TARGET_TABLES.get(target_type)
        if table is None:
            raise DomainValidation("target_type is unsupported")
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (target_id,)).fetchone()
        if row is None:
            return False
        columns = set(row.keys())
        if "deleted_at" in columns and row["deleted_at"] is not None:
            return False
        return True

    @staticmethod
    def _write_scope_history(conn: sqlite3.Connection, monitor_id: str, scope: RelevanceScope, *, change_type: str, changed_by: str | None, created_at: str) -> bool:
        encoded = json.dumps(scope.as_dict(), sort_keys=True, separators=(",", ":"))
        previous = conn.execute(
            "SELECT scope_json FROM monitor_scope_history WHERE monitor_id = ? ORDER BY version DESC LIMIT 1",
            (monitor_id,),
        ).fetchone()
        if previous is not None and previous[0] == encoded:
            return False
        version = conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM monitor_scope_history WHERE monitor_id = ?", (monitor_id,)).fetchone()[0]
        conn.execute(
            "INSERT INTO monitor_scope_history(id, monitor_id, version, scope_json, change_type, changed_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id("scopehist"), monitor_id, version, encoded, change_type, changed_by, created_at),
        )
        return True

    def create(self, data: Mapping[str, Any]) -> dict[str, Any]:
        target_type = str(data.get("target_type", ""))
        target_id = str(data.get("target_id", ""))
        policy_id = str(data.get("policy_id", ""))
        if target_type not in TARGET_TABLES or not target_id or not policy_id:
            raise DomainValidation("target_type, target_id, and policy_id are required")
        identifier = str(data.get("id") or new_id("mon"))
        now = _timestamp(data.get("created_at") or utc_now())
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if not self._target_exists(conn, target_type, target_id):
                    raise DomainNotFound("monitor target not found")
                policy = conn.execute("SELECT * FROM monitoring_policies WHERE id = ?", (policy_id,)).fetchone()
                if policy is None:
                    raise DomainNotFound("monitoring policy not found")
                next_check_at = data.get("next_check_at")
                if next_check_at is None:
                    next_check_at = _plus_seconds(now, int(policy["base_cadence_seconds"]))
                else:
                    next_check_at = _timestamp(next_check_at)
                enabled = data.get("enabled", True)
                if not isinstance(enabled, bool):
                    raise DomainValidation("enabled must be boolean")
                conn.execute(
                    """
                    INSERT INTO monitors(id, target_type, target_id, policy_id, enabled, next_check_at,
                                         last_run_at, last_result, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                    """,
                    (identifier, target_type, target_id, policy_id, int(enabled), next_check_at, now, now),
                )
                self._write_scope_history(
                    conn,
                    identifier,
                    _scope_for_target(conn, target_type, target_id),
                    change_type="initial",
                    changed_by=data.get("created_by"),
                    created_at=now,
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("monitor already exists for this target") from exc
        finally:
            conn.close()
        return self.get(identifier)

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM monitors WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("monitor not found")
            return _monitor_output(row)
        finally:
            conn.close()

    def list(self, *, enabled: bool | None = None, target_type: str | None = None, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        clauses = []
        params: list[Any] = []
        if enabled is not None:
            clauses.append("enabled = ?")
            params.append(int(enabled))
        if target_type is not None:
            if target_type not in TARGET_TABLES:
                raise DomainValidation("target_type is unsupported")
            clauses.append("target_type = ?")
            params.append(target_type)
        conn = storage.connect(self.db_path)
        try:
            return _page(conn, "monitors", where=" AND ".join(clauses) or "1 = 1", params=params, page=page, page_size=page_size, order_by="next_check_at, id")
        finally:
            conn.close()

    def update(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        current = self.get(identifier)
        allowed = {"policy_id", "enabled", "next_check_at"}
        values = {key: value for key, value in data.items() if key in allowed}
        if not values:
            raise DomainValidation("at least one monitor field must be supplied")
        if "enabled" in values and not isinstance(values["enabled"], bool):
            raise DomainValidation("enabled must be boolean")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if values.get("enabled") is True and not self._target_exists(
                    conn, current["target_type"], current["target_id"]
                ):
                    raise DomainNotFound("monitor target not found")
                policy_id = values.get("policy_id", current["policy_id"])
                if conn.execute("SELECT 1 FROM monitoring_policies WHERE id = ?", (policy_id,)).fetchone() is None:
                    raise DomainNotFound("monitoring policy not found")
                if "next_check_at" in values:
                    values["next_check_at"] = _timestamp(values["next_check_at"]) if values["next_check_at"] is not None else None
                conn.execute(
                    "UPDATE monitors SET policy_id = ?, enabled = ?, next_check_at = ?, updated_at = ? WHERE id = ?",
                    (policy_id, int(values.get("enabled", current["enabled"])), values.get("next_check_at", current["next_check_at"]), utc_now(), identifier),
                )
        finally:
            conn.close()
        return self.get(identifier)

    def disable(self, identifier: str) -> dict[str, Any]:
        return self.update(identifier, {"enabled": False})

    def enable(self, identifier: str, *, next_check_at: str | None = None) -> dict[str, Any]:
        values: dict[str, Any] = {"enabled": True}
        if next_check_at is not None:
            values["next_check_at"] = next_check_at
        return self.update(identifier, values)

    def record_activity(
        self,
        identifier: str,
        outcome: str,
        *,
        new_items: int = 0,
        changed_items: int = 0,
        relevant_items: int = 0,
        error_code: str | None = None,
        observed_at: str | datetime | None = None,
    ) -> dict[str, Any]:
        if outcome not in {"no_change", "changed", "relevant_change", "partial", "error"}:
            raise DomainValidation("unsupported monitor activity outcome")
        counts = {"new_items": new_items, "changed_items": changed_items, "relevant_items": relevant_items}
        for field, value in counts.items():
            _nonnegative_int(value, field)
        observed = _timestamp(observed_at)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute(
                    "SELECT m.*, p.base_cadence_seconds, p.min_cadence_seconds, p.max_cadence_seconds, p.backoff_rules, p.retirement_criteria FROM monitors m JOIN monitoring_policies p ON p.id = m.policy_id WHERE m.id = ?",
                    (identifier,),
                ).fetchone()
                if row is None:
                    raise DomainNotFound("monitor not found")
                conn.execute(
                    "INSERT INTO monitor_activity(id, monitor_id, outcome, new_items, changed_items, relevant_items, error_code, observed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (new_id("activity"), identifier, outcome, new_items, changed_items, relevant_items, error_code, observed, observed),
                )
                if row["last_run_at"] and row["next_check_at"]:
                    current_interval = _seconds_between(row["next_check_at"], row["last_run_at"])
                else:
                    current_interval = int(row["base_cadence_seconds"])
                backoff = _decode(row["backoff_rules"], {})
                if outcome == "no_change":
                    multiplier = float(backoff.get("no_change_multiplier", 2.0))
                elif outcome == "error":
                    multiplier = float(backoff.get("error_multiplier", 2.0))
                else:
                    # 'changed' and reserved 'partial': content changed, but
                    # semantic relevance is not yet evaluated. Keep the current
                    # polling interval; do not drop to min_cadence (reserved
                    # for a confirmed relevant_change) and do not back off.
                    multiplier = 1.0
                if not math.isfinite(multiplier) or multiplier < 1.0 or multiplier > 10.0:
                    raise DomainValidation("backoff multipliers must be between 1 and 10")
                if outcome == "relevant_change":
                    cadence = int(row["min_cadence_seconds"])
                else:
                    cadence = round(current_interval * multiplier)
                cadence = max(int(row["min_cadence_seconds"]), min(int(row["max_cadence_seconds"]), max(1, cadence)))
                consecutive_errors = 0
                for activity_row in conn.execute(
                    "SELECT outcome FROM monitor_activity WHERE monitor_id = ? ORDER BY observed_at DESC, id DESC LIMIT 100",
                    (identifier,),
                ):
                    if activity_row[0] != "error":
                        break
                    consecutive_errors += 1
                retirement = _decode(row["retirement_criteria"], {})
                max_errors = retirement.get("max_consecutive_errors")
                retired = isinstance(max_errors, int) and max_errors > 0 and consecutive_errors >= max_errors and outcome == "error"
                next_check = None if retired else _plus_seconds(observed, cadence)
                last_result = "retired" if retired else outcome
                conn.execute(
                    "UPDATE monitors SET enabled = ?, next_check_at = ?, last_run_at = ?, last_result = ?, updated_at = ? WHERE id = ?",
                    (0 if retired else row["enabled"], next_check, observed, last_result, observed, identifier),
                )
        finally:
            conn.close()
        return self.get(identifier)

    def activity(self, identifier: str, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            if conn.execute("SELECT 1 FROM monitors WHERE id = ?", (identifier,)).fetchone() is None:
                raise DomainNotFound("monitor not found")
            return _page(conn, "monitor_activity", where="monitor_id = ?", params=(identifier,), page=page, page_size=page_size, order_by="observed_at DESC, id DESC")
        finally:
            conn.close()

    def scope_history(self, identifier: str, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            if conn.execute("SELECT 1 FROM monitors WHERE id = ?", (identifier,)).fetchone() is None:
                raise DomainNotFound("monitor not found")
            result = _page(conn, "monitor_scope_history", where="monitor_id = ?", params=(identifier,), page=page, page_size=page_size, order_by="version DESC")
            for item in result["items"]:
                item["scope"] = _decode(item.pop("scope_json"), {})
            return result
        finally:
            conn.close()

    def scope(self, identifier: str) -> RelevanceScope:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT scope_json FROM monitor_scope_history WHERE monitor_id = ? ORDER BY version DESC LIMIT 1", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("monitor scope not found")
            data = _decode(row[0], {})
            return RelevanceScope(**data)
        finally:
            conn.close()

    def refresh_topic_scopes(self, topic_id: str, *, changed_by: str | None = None, change_type: str = "approved") -> int:
        now = utc_now()
        conn = storage.connect(self.db_path)
        changed = 0
        try:
            with storage.write_tx(conn):
                if conn.execute("SELECT 1 FROM topics WHERE id = ? AND deleted_at IS NULL", (topic_id,)).fetchone() is None:
                    raise DomainNotFound("topic not found")
                rows = conn.execute("SELECT id FROM monitors WHERE target_type = 'topic' AND target_id = ?", (topic_id,)).fetchall()
                scope = _scope_for_target(conn, "topic", topic_id)
                for row in rows:
                    changed += int(self._write_scope_history(conn, row[0], scope, change_type=change_type, changed_by=changed_by, created_at=now))
        finally:
            conn.close()
        return changed

    def relevance(self, identifier: str, text: str) -> RelevanceResult:
        return RelevanceCascade().evaluate(text, self.scope(identifier))


class ScopeSuggestionService:
    """AI-assisted vocabulary candidates with explicit approval before activation."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def create(self, topic_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        suggestion_type = str(data.get("suggestion_type", ""))
        value = str(data.get("value", "")).strip()
        if suggestion_type not in SUGGESTION_TYPES:
            raise DomainValidation("unsupported vocabulary suggestion type")
        if not value or len(value) > 300:
            raise DomainValidation("suggestion value must be between 1 and 300 characters")
        source = str(data.get("source", "ai"))
        if source not in {"ai", "user"}:
            raise DomainValidation("suggestion source must be ai or user")
        rationale = str(data.get("rationale", ""))
        if len(rationale) > 2_000:
            raise DomainValidation("suggestion rationale exceeds 2000 characters")
        identifier = str(data.get("id") or new_id("vocab"))
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                if conn.execute("SELECT 1 FROM topics WHERE id = ? AND deleted_at IS NULL", (topic_id,)).fetchone() is None:
                    raise DomainNotFound("topic not found")
                conn.execute(
                    "INSERT INTO vocabulary_suggestions(id, topic_id, suggestion_type, value, value_normalized, rationale, source, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                    (identifier, topic_id, suggestion_type, value, normalized_text(value), rationale, source, now),
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("vocabulary suggestion already exists") from exc
        finally:
            conn.close()
        return self.get(identifier)

    def get(self, identifier: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute("SELECT * FROM vocabulary_suggestions WHERE id = ?", (identifier,)).fetchone()
            if row is None:
                raise DomainNotFound("vocabulary suggestion not found")
            return _as_dict(row)
        finally:
            conn.close()

    def list(self, topic_id: str, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            return _page(conn, "vocabulary_suggestions", where="topic_id = ?", params=(topic_id,), page=page, page_size=page_size, order_by="created_at DESC, id DESC")
        finally:
            conn.close()

    def suggest_from_text(self, topic_id: str, text: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not 1 <= limit <= 50:
            raise DomainValidation("suggestion limit must be between 1 and 50")
        candidates: list[tuple[str, str, str]] = []
        for token in _TOKEN_RE.findall(str(text)):
            if len(token) < 3 or token.casefold() in {"the", "and", "for", "with", "from", "this", "that"}:
                continue
            suggestion_type = "acronym" if token.isupper() and len(token) <= 8 else "term"
            candidates.append((suggestion_type, token, "local candidate extracted from monitor context"))
        created: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for suggestion_type, value, rationale in candidates:
            key = suggestion_type, normalized_text(value)
            if key in seen:
                continue
            seen.add(key)
            try:
                created.append(self.create(topic_id, {"suggestion_type": suggestion_type, "value": value, "rationale": rationale, "source": "ai"}))
            except DomainConflict:
                continue
            if len(created) >= limit:
                break
        return created

    def review(self, identifier: str, *, approved: bool, reviewed_by: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        topic_id = None
        try:
            with storage.write_tx(conn):
                row = conn.execute("SELECT * FROM vocabulary_suggestions WHERE id = ?", (identifier,)).fetchone()
                if row is None:
                    raise DomainNotFound("vocabulary suggestion not found")
                if row["status"] != "pending":
                    raise DomainConflict("vocabulary suggestion has already been reviewed")
                topic_id = row["topic_id"]
                now = utc_now()
                if approved:
                    mapping = {
                        "term": ("include", "term"),
                        "synonym": ("alias", "term"),
                        "alias": ("alias", "term"),
                        "acronym": ("alias", "acronym"),
                        "broader": ("include", "related_concept"),
                        "narrower": ("include", "related_concept"),
                        "related_concept": ("include", "related_concept"),
                        "exclude": ("exclude", "term"),
                    }
                    if row["suggestion_type"] in mapping:
                        term_type, concept_kind = mapping[row["suggestion_type"]]
                        exists = conn.execute(
                            "SELECT 1 FROM topic_terms WHERE topic_id = ? AND term_normalized = ? AND term_type = ?",
                            (topic_id, row["value_normalized"], term_type),
                        ).fetchone()
                        if exists is None:
                            conn.execute(
                                "INSERT INTO topic_terms(id, topic_id, term, term_normalized, term_type, weight, created_at, concept_kind) VALUES (?, ?, ?, ?, ?, 1.0, ?, ?)",
                                (new_id("term"), topic_id, row["value"], row["value_normalized"], term_type, now, concept_kind),
                            )
                conn.execute(
                    "UPDATE vocabulary_suggestions SET status = ?, reviewed_at = ?, reviewed_by = ? WHERE id = ?",
                    ("approved" if approved else "rejected", now, reviewed_by, identifier),
                )
        finally:
            conn.close()
        if approved and topic_id:
            MonitorService(self.db_path).refresh_topic_scopes(topic_id, changed_by=reviewed_by, change_type="approved")
        return self.get(identifier)


class MonitorExecutionService:
    """Allow-listed local monitor job handler with bounded source acquisition."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        acquisition_service: AcquisitionService | None = None,
        monitor_service: MonitorService | None = None,
        budget_service: BudgetService | None = None,
    ):
        self.db_path = Path(db_path)
        self.monitors = monitor_service or MonitorService(db_path)
        self.acquisition = acquisition_service or AcquisitionService(db_path)
        self.budgets = budget_service or BudgetService(db_path)

    def handle(self, job: Mapping[str, Any]) -> dict[str, Any]:
        payload = job.get("payload", {})
        if not isinstance(payload, Mapping):
            raise DomainValidation("monitor job payload must be an object")
        monitor_id = payload.get("monitor_id") or job.get("monitor_id")
        if not monitor_id:
            raise DomainValidation("monitor job is missing monitor_id")
        monitor_id = str(monitor_id)
        observed_at = str(job.get("updated_at") or utc_now())

        # Check if caller explicitly supplied candidate_text (manual/unit test relevance path)
        candidate = payload.get("candidate_text")
        if candidate is not None:
            result = self.monitors.relevance(monitor_id, str(candidate))
            outcome = "relevant_change" if result.relevant else "no_change"
            monitor = self.monitors.record_activity(
                monitor_id,
                outcome,
                new_items=1 if result.relevant else 0,
                relevant_items=1 if result.relevant else 0,
                observed_at=observed_at,
            )
            return {
                "monitor_id": monitor_id,
                "outcome": outcome,
                "relevance": result.as_dict(),
                "monitor": monitor,
                "paid_used": False,
            }

        # Production path: resolve Monitor and execute bounded acquisition
        conn = storage.connect(self.db_path)
        try:
            monitor_row = conn.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,)).fetchone()
            if monitor_row is None:
                raise DomainNotFound(f"monitor '{monitor_id}' not found")
            policy_row = conn.execute("SELECT * FROM monitoring_policies WHERE id = ?", (monitor_row["policy_id"],)).fetchone()
            if policy_row is None:
                raise DomainNotFound(f"monitoring policy '{monitor_row['policy_id']}' not found")
        finally:
            conn.close()

        if monitor_row["enabled"] == 0:
            return {"monitor_id": monitor_id, "outcome": "disabled", "status": "skipped", "paid_used": False}

        target_type = monitor_row["target_type"]
        target_id = monitor_row["target_id"]

        if target_type != "source":
            # Non-source targets do not have an acquisition mechanism yet.
            # Truthfully record non-success (error / unsupported_target) rather than fake no_change.
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="unsupported_target",
                observed_at=observed_at,
            )
            raise DomainValidation(f"monitor target_type '{target_type}' does not support source acquisition yet")

        # Resolve Source
        conn = storage.connect(self.db_path)
        try:
            source_row = conn.execute("SELECT * FROM sources WHERE id = ? AND deleted_at IS NULL", (target_id,)).fetchone()
        finally:
            conn.close()

        if source_row is None:
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="target_not_found",
                observed_at=observed_at,
            )
            raise DomainNotFound(f"source '{target_id}' not found")

        feed_url = source_row["feed_url"]
        homepage_url = source_row["homepage_url"]
        if not feed_url and not homepage_url:
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="not_configured",
                observed_at=observed_at,
            )
            raise DomainValidation(f"source '{target_id}' has neither feed_url nor homepage_url configured")

        allowed_channels = set(_decode(policy_row["allowed_channels"], []))

        # Select acquisition method based on source configuration and policy allowed_channels
        use_feed = False
        use_doc = False
        doc_channel = "direct_http"

        if feed_url and (not allowed_channels or "rss" in allowed_channels or "atom" in allowed_channels):
            use_feed = True
        elif homepage_url and (not allowed_channels or "direct_http" in allowed_channels or "page" in allowed_channels):
            use_doc = True
            doc_channel = "direct_http" if (not allowed_channels or "direct_http" in allowed_channels) else "page"
        elif feed_url and homepage_url and ("direct_http" in allowed_channels or "page" in allowed_channels):
            use_doc = True
            doc_channel = "direct_http" if "direct_http" in allowed_channels else "page"
        else:
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="channel_not_allowed",
                observed_at=observed_at,
            )
            raise DomainValidation(f"source '{target_id}' acquisition channels are not allowed by policy '{policy_row['id']}'")

        job_id = job.get("id")

        try:
            if use_feed:
                poll_result = self.acquisition.poll_feed(source_id=target_id, feed_url=feed_url)
                new_items = poll_result.new_count
                changed_items = poll_result.changed_count
                is_changed = (new_items > 0 or changed_items > 0)
                # Acquisition can prove content changed but not that the change
                # is relevant: leave the semantic claim unset until the later
                # relevance stage actually runs.
                outcome = "changed" if is_changed else "no_change"

                self.budgets.record_usage(
                    job_id=job_id,
                    monitor_id=monitor_id,
                    capability="acquisition",
                    provider="feed",
                    request_type="rss",
                    acquisition_units=1,
                    outcome=outcome,
                )
                monitor_record = self.monitors.record_activity(
                    monitor_id,
                    outcome,
                    new_items=new_items,
                    changed_items=changed_items,
                    relevant_items=0,
                    observed_at=observed_at,
                )
                return {
                    "monitor_id": monitor_id,
                    "outcome": outcome,
                    "target_type": "source",
                    "target_id": target_id,
                    "new_items": new_items,
                    "changed_items": changed_items,
                    "event_id": poll_result.event_id,
                    "monitor": monitor_record,
                    "paid_used": False,
                }
            else:
                doc_result = self.acquisition.acquire_document(source_id=target_id, url=homepage_url, channel=doc_channel)
                is_retrieved = doc_result.outcome == "retrieved"
                if is_retrieved:
                    conn = storage.connect(self.db_path)
                    try:
                        v_count = conn.execute(
                            "SELECT COUNT(*) FROM document_versions WHERE document_id = ?",
                            (doc_result.document_id,),
                        ).fetchone()[0]
                    finally:
                        conn.close()
                    new_items = 1 if v_count <= 1 else 0
                    changed_items = 1 if v_count > 1 else 0
                    # Acquisition detected new or changed content; relevance is
                    # unknown until the semantic relevance stage runs.
                    outcome = "changed"
                else:
                    new_items = 0
                    changed_items = 0
                    outcome = "no_change"

                self.budgets.record_usage(
                    job_id=job_id,
                    monitor_id=monitor_id,
                    capability="acquisition",
                    provider="http",
                    request_type=doc_channel,
                    acquisition_units=1,
                    outcome=outcome,
                )
                monitor_record = self.monitors.record_activity(
                    monitor_id,
                    outcome,
                    new_items=new_items,
                    changed_items=changed_items,
                    relevant_items=0,
                    observed_at=observed_at,
                )
                return {
                    "monitor_id": monitor_id,
                    "outcome": outcome,
                    "target_type": "source",
                    "target_id": target_id,
                    "document_id": doc_result.document_id,
                    "document_version_id": doc_result.document_version_id,
                    "new_items": new_items,
                    "changed_items": changed_items,
                    "event_id": doc_result.event_id,
                    "monitor": monitor_record,
                    "paid_used": False,
                }
        except AcquisitionTimeout as exc:
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="AcquisitionTimeout",
                observed_at=observed_at,
            )
            self.budgets.record_usage(
                job_id=job_id,
                monitor_id=monitor_id,
                capability="acquisition",
                provider="http" if use_doc else "feed",
                request_type=doc_channel if use_doc else "rss",
                acquisition_units=1,
                outcome="error",
            )
            raise RetryableJobFailure(f"AcquisitionTimeout: {exc}") from exc
        except AcquisitionBlocked as exc:
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="AcquisitionBlocked",
                observed_at=observed_at,
            )
            self.budgets.record_usage(
                job_id=job_id,
                monitor_id=monitor_id,
                capability="acquisition",
                provider="http" if use_doc else "feed",
                request_type=doc_channel if use_doc else "rss",
                acquisition_units=1,
                outcome="blocked",
            )
            raise
        except AcquisitionTooLarge as exc:
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="AcquisitionTooLarge",
                observed_at=observed_at,
            )
            self.budgets.record_usage(
                job_id=job_id,
                monitor_id=monitor_id,
                capability="acquisition",
                provider="http" if use_doc else "feed",
                request_type=doc_channel if use_doc else "rss",
                acquisition_units=1,
                outcome="blocked",
            )
            raise
        except FeedParseError as exc:
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code="FeedParseError",
                observed_at=observed_at,
            )
            self.budgets.record_usage(
                job_id=job_id,
                monitor_id=monitor_id,
                capability="acquisition",
                provider="feed",
                request_type="rss",
                acquisition_units=1,
                outcome="error",
            )
            raise
        except AcquisitionError as exc:
            error_code = type(exc).__name__
            self.monitors.record_activity(
                monitor_id,
                "error",
                error_code=error_code,
                observed_at=observed_at,
            )
            self.budgets.record_usage(
                job_id=job_id,
                monitor_id=monitor_id,
                capability="acquisition",
                provider="http" if use_doc else "feed",
                request_type=doc_channel if use_doc else "rss",
                acquisition_units=1,
                outcome="error",
            )
            err_str = str(exc)
            if "HTTP status 5" in err_str or "HTTP request failed" in err_str:
                raise RetryableJobFailure(f"{error_code}: {exc}") from exc
            raise

    def handlers(self) -> dict[str, Callable[[dict[str, Any]], Any]]:
        return {MONITOR_CHECK_JOB_TYPE: self.handle}


def reconcile_monitor_job_outcome(
    conn: sqlite3.Connection,
    job_row: sqlite3.Row,
    final_status: str,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Reconcile monitor state on claim-time budget exhaustion.

    Runs inside the same write transaction that terminalizes the durable job.
    Only the ``budget`` trigger mutates monitor state: budget exhaustion
    happens before the handler ran, so it records an explicit error activity
    instead of leaving the execution ambiguous. Completion/cancellation of a
    monitor job needs no reconciliation here -- the acquisition handler writes
    the authoritative activity row for real executions, and a cancelled queued
    job never executed, so ``last_result`` is preserved.
    """
    if job_row["job_type"] != MONITOR_CHECK_JOB_TYPE:
        return
    monitor_id = job_row["monitor_id"]
    if not monitor_id:
        return
    details = details or {}
    trigger = details.get("trigger")
    if trigger == "budget":
        now = job_row["updated_at"] or utc_now()
        error_code = str(details.get("error_code") or "budget_exhausted")
        row = conn.execute(
            "SELECT m.*, p.base_cadence_seconds, p.min_cadence_seconds, p.max_cadence_seconds, p.backoff_rules, p.retirement_criteria "
            "FROM monitors m JOIN monitoring_policies p ON p.id = m.policy_id WHERE m.id = ?",
            (monitor_id,),
        ).fetchone()
        if row is None:
            return
        conn.execute(
            "INSERT INTO monitor_activity(id, monitor_id, outcome, new_items, changed_items, relevant_items, error_code, observed_at, created_at) "
            "VALUES (?, ?, 'error', 0, 0, 0, ?, ?, ?)",
            (new_id("activity"), monitor_id, error_code, now, now),
        )
        if row["last_run_at"] and row["next_check_at"]:
            current_interval = _seconds_between(row["next_check_at"], row["last_run_at"])
        else:
            current_interval = int(row["base_cadence_seconds"])
        backoff = _decode(row["backoff_rules"], {})
        multiplier = float(backoff.get("error_multiplier", 2.0))
        if not math.isfinite(multiplier) or multiplier < 1.0 or multiplier > 10.0:
            multiplier = 2.0
        cadence = round(current_interval * multiplier)
        cadence = max(int(row["min_cadence_seconds"]), min(int(row["max_cadence_seconds"]), max(1, cadence)))
        consecutive_errors = 0
        for activity_row in conn.execute(
            "SELECT outcome FROM monitor_activity WHERE monitor_id = ? ORDER BY observed_at DESC, id DESC LIMIT 100",
            (monitor_id,),
        ):
            if activity_row[0] != "error":
                break
            consecutive_errors += 1
        retirement = _decode(row["retirement_criteria"], {})
        max_errors = retirement.get("max_consecutive_errors")
        retired = isinstance(max_errors, int) and max_errors > 0 and consecutive_errors >= max_errors
        next_check = None if retired else _plus_seconds(now, cadence)
        last_result = "retired" if retired else "error"
        conn.execute(
            "UPDATE monitors SET enabled = ?, next_check_at = ?, last_run_at = ?, last_result = ?, updated_at = ? WHERE id = ?",
            (0 if retired else row["enabled"], next_check, now, last_result, now, monitor_id),
        )


def monitor_job_completion_hook(
    conn: sqlite3.Connection,
    job_row: sqlite3.Row,
    job_status: str,
    context: Mapping[str, Any] | None = None,
) -> None:
    """Monitor completion hook invoked by JobService job-lifecycle events.

    Composed independently from Research Question hooks at the central wiring
    point. A no-op for any non-monitor job; only claim-time budget exhaustion
    writes monitor activity (the durable execution path records its own rows).
    """
    reconcile_monitor_job_outcome(conn, job_row, job_status, context)


__all__ = [
    "MonitorService",
    "MonitorExecutionService",
    "MonitoringPolicyService",
    "RelevanceCascade",
    "RelevanceResult",
    "RelevanceScope",
    "ScopeSuggestionService",
    "monitor_job_completion_hook",
    "reconcile_monitor_job_outcome",
]
