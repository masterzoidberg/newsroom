"""Phase 24 persistent Watches, vocabulary review, and Source discovery.

A Watch owns the user intent. Approved Sources are connected through ordinary
source Monitors so no discovery path can bypass acquisition, relevance,
ArticleAnalysis, or verified evidence promotion.

Since migration 0024 a Monitor is identified by target *and* approved
information need, so two Watches may share one Source while each keeps its own
approved scope, cadence, and enabled state. Every Monitor row still belongs to
exactly one Watch (`watch_sources.monitor_id` is UNIQUE), which is what makes
per-Watch pause/resume safe.

Vocabulary and Source candidates are retrieval configuration only. Nothing here
creates Evidence, Claims, Stories, Reports, or Alerts; approved Sources simply
enter the existing Phase 18-23 pipeline.
"""
from __future__ import annotations

import ipaddress
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlparse

from . import storage
from .ai import (
    AIError,
    AIRouter,
    CapabilityBundle,
    SQLiteTelemetrySink,
    VocabularyOutput,
    VocabularyRequest,
)
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
from .jobs import (
    BudgetService,
    JobService,
    WATCH_SOURCE_DISCOVERY_JOB_TYPE,
    WATCH_VOCABULARY_SUGGESTION_JOB_TYPE,
)
from .monitoring import (
    MonitorService,
    RelevanceScope,
    TARGET_TABLES,
    _scope_for_target,
)
from .url_norm import normalize_url
from .worker import RetryableJobFailure

WATCH_STATUSES = frozenset({"active", "paused", "disabled"})
WATCH_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
VOCABULARY_KINDS = frozenset(
    {
        "primary",
        "alias",
        "synonym",
        "acronym",
        "acronym_expansion",
        "related",
        "include",
        "exclude",
    }
)
DISCOVERY_METHODS = frozenset(
    {
        "manual",
        "existing_source",
        "document_link",
        "feed_discovery",
        "web_search",
        "ai_suggestion",
    }
)

MAX_TERM_LENGTH = 300
MAX_RATIONALE_LENGTH = 2000
MAX_SUGGESTIONS_PER_RUN = 50
MAX_CANDIDATES_PER_RUN = 25
MAX_QUERY_VARIANTS = 12
MAX_ACTIVE_QUERY_TERMS = 100
MAX_PAGE_SIZE = 100
MAX_SETUP_INTEREST_LENGTH = 2_000

WATCH_SETUP_CATEGORY_SLUG = "watch-setup"
WATCH_SETUP_CATEGORY_NAME = "Watch setup"
WATCH_SETUP_CATEGORY_DESCRIPTION = "Neutral category for Watch setup drafts"
WATCH_SETUP_POLICY_NAME = "Watch setup"
WATCH_SETUP_BASE_CADENCE_SECONDS = 3_600
WATCH_SETUP_MIN_CADENCE_SECONDS = 900
WATCH_SETUP_MAX_CADENCE_SECONDS = 86_400
WATCH_SETUP_QUERY_BUDGET = MAX_QUERY_VARIANTS
WATCH_SETUP_LOCAL_MODEL_BUDGET = 100

# A Watch target of 'source' is pure acquisition: 'source' is not a valid
# monitor information-need type, so such a Watch produces acquisition-only
# monitors exactly as Phase 20 defines them.
_NEEDLESS_TARGET = "source"


def _safe_url(value: Any) -> str:
    """Validate an externally supplied Source URL before it can be persisted.

    Phase 24 accepts URLs from provider suggestions and discovered Documents,
    so a candidate must never be able to point monitoring at loopback, link
    local, or otherwise non-global infrastructure.
    """
    try:
        url = normalize_url(str(value or "").strip())
    except ValueError as exc:
        raise DomainValidation(str(exc)) from exc
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise DomainValidation("source candidate URL must be http or https")
    host = (parsed.hostname or "").casefold()
    if not host:
        raise DomainValidation("source candidate URL requires a hostname")
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise DomainValidation(
            "source candidate URL must not target a private or local address"
        )
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise DomainValidation(
            "source candidate URL must not target a private or local host"
        )
    return url


def _normalized_candidate_url(url: str) -> str:
    """Stable per-Watch candidate identity for repeated discovery runs."""
    return url.rstrip("/").casefold() or url.casefold()


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _initialism(term: str) -> str | None:
    """Derive a deterministic acronym for a multi-word term.

    Only multi-word phrases whose words are all alphabetic produce an
    initialism, so 'unidentified anomalous phenomena' yields 'UAP' while
    'F-16 sighting' yields nothing.
    """
    words = [word for word in term.split() if word]
    if len(words) < 2 or len(words) > 6:
        return None
    if not all(word.isalpha() and len(word) >= 3 for word in words):
        return None
    return "".join(word[0] for word in words).upper()


class WatchService:
    """Higher-level monitoring intent backed by ordinary source Monitors."""

    def __init__(self, db_path: str | Path, *, router: AIRouter | None = None):
        self.db_path = Path(db_path)
        self.router = router

    # ------------------------------------------------------------------
    # Watch lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _require_watch(conn: sqlite3.Connection, watch_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM watches WHERE id = ?", (watch_id,)).fetchone()
        if row is None:
            raise DomainNotFound("watch not found")
        return row

    @staticmethod
    def _need_for(watch: Mapping[str, Any]) -> tuple[str | None, str | None]:
        """The information need a Watch pins onto each of its Monitors."""
        if watch["target_type"] == _NEEDLESS_TARGET:
            return None, None
        return str(watch["target_type"]), str(watch["target_id"])

    def create(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name = str(data.get("name", "")).strip()
        target_type = str(data.get("target_type", "")).strip()
        target_id = str(data.get("target_id", "")).strip()
        policy_id = str(data.get("policy_id", "")).strip()
        if not name or len(name) > 200:
            raise DomainValidation("watch name must be between 1 and 200 characters")
        if target_type not in TARGET_TABLES or not target_id or not policy_id:
            raise DomainValidation(
                "watch target_type, target_id, and policy_id are required"
            )
        status = str(data.get("status", "active"))
        priority = str(data.get("priority", "normal"))
        if status not in WATCH_STATUSES or priority not in WATCH_PRIORITIES:
            raise DomainValidation("invalid watch status or priority")
        identifier = str(data.get("id") or new_id("watch"))
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                target_table = TARGET_TABLES[target_type]
                exists = conn.execute(
                    f"SELECT 1 FROM {target_table} WHERE id = ?", (target_id,)
                ).fetchone()
                if exists is None:
                    raise DomainNotFound("watch target not found")
                policy = conn.execute(
                    "SELECT 1 FROM monitoring_policies WHERE id = ?", (policy_id,)
                ).fetchone()
                if policy is None:
                    raise DomainNotFound("monitoring policy not found")
                conn.execute(
                    """
                    INSERT INTO watches(id, name, target_type, target_id, policy_id,
                                        status, priority, discovery_enabled,
                                        created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        identifier,
                        name,
                        target_type,
                        target_id,
                        policy_id,
                        status,
                        priority,
                        int(bool(data.get("discovery_enabled", True))),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("a watch already exists for this target") from exc
        finally:
            conn.close()
        return self.get(identifier)

    @staticmethod
    def _validated_paused_setup(data: Mapping[str, Any]) -> tuple[str, str, str, list[str]]:
        request_id = data.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            raise DomainValidation("request_id must be a UUID")
        try:
            canonical_request_id = str(uuid.UUID(request_id.strip()))
        except (ValueError, AttributeError) as exc:
            raise DomainValidation("request_id must be a UUID") from exc

        interest = data.get("interest")
        if not isinstance(interest, str):
            raise DomainValidation("interest must be a string")
        interest = interest.strip()
        if not interest or len(interest) > MAX_SETUP_INTEREST_LENGTH:
            raise DomainValidation(
                f"interest must be between 1 and {MAX_SETUP_INTEREST_LENGTH} characters"
            )

        name = data.get("name")
        if not isinstance(name, str):
            raise DomainValidation("watch name must be a string")
        name = name.strip()
        if not name or len(name) > 200:
            raise DomainValidation("watch name must be between 1 and 200 characters")

        raw_terms = data.get("primary_terms")
        if not isinstance(raw_terms, Sequence) or isinstance(raw_terms, (str, bytes)):
            raise DomainValidation("primary_terms must be an array")
        if not raw_terms or len(raw_terms) > MAX_ACTIVE_QUERY_TERMS:
            raise DomainValidation(
                f"primary_terms must contain between 1 and {MAX_ACTIVE_QUERY_TERMS} terms"
            )
        terms: list[str] = []
        seen: set[str] = set()
        for raw_term in raw_terms:
            if not isinstance(raw_term, str):
                raise DomainValidation("primary_terms must contain strings")
            term = raw_term.strip()
            if not term or len(term) > MAX_TERM_LENGTH:
                raise DomainValidation(
                    f"each primary term must be between 1 and {MAX_TERM_LENGTH} characters"
                )
            identity = normalized_text(term)
            if identity in seen:
                continue
            seen.add(identity)
            terms.append(term)
        if not terms:
            raise DomainValidation("at least one primary term is required")
        return canonical_request_id, interest, name, terms

    @staticmethod
    def _setup_topic_slug(request_id: str) -> str:
        return f"watch-{request_id.replace('-', '')}"

    @staticmethod
    def _require_canonical_setup_category(category: sqlite3.Row | None) -> sqlite3.Row:
        expected = {
            "slug": WATCH_SETUP_CATEGORY_SLUG,
            "name": WATCH_SETUP_CATEGORY_NAME,
            "description": WATCH_SETUP_CATEGORY_DESCRIPTION,
            "enabled": 1,
            "priority": "normal",
            "display_order": 0,
            "max_stories_per_run": None,
            "deleted_at": None,
        }
        if category is None or any(category[field] != value for field, value in expected.items()):
            raise DomainConflict(
                "Category slug 'watch-setup' is not the canonical Watch setup Category; "
                "no changes were made. Resolve the conflicting Category before retrying."
            )
        return category

    @staticmethod
    def _decoded_setup_policy(row: sqlite3.Row) -> dict[str, Any]:
        policy = _row(row)
        for field in ("allowed_channels", "escalation_rules", "backoff_rules", "retirement_criteria"):
            default: Any = [] if field == "allowed_channels" else {}
            policy[field] = json.loads(policy[field]) if policy[field] is not None else default
        policy["watch_scope"] = "private"
        return policy

    @classmethod
    def _setup_response(
        cls,
        conn: sqlite3.Connection,
        *,
        request_id: str,
        category: sqlite3.Row,
        topic: sqlite3.Row,
        terms: Sequence[sqlite3.Row],
        policy: sqlite3.Row,
        watch: sqlite3.Row,
        resumed: bool,
    ) -> dict[str, Any]:
        term_payload = [_row(term) for term in terms]
        policy_payload = cls._decoded_setup_policy(policy)
        monitor_count = conn.execute(
            "SELECT COUNT(*) FROM watch_sources WHERE watch_id = ?", (watch["id"],)
        ).fetchone()[0]
        job_count = conn.execute(
            """
            SELECT COUNT(*) FROM jobs
            WHERE monitor_id IN (
                SELECT monitor_id FROM watch_sources WHERE watch_id = ?
            )
            """,
            (watch["id"],),
        ).fetchone()[0]
        watch_payload = _row(watch)
        topic_payload = _row(topic)
        category_payload = _row(category)
        return {
            "draft_type": "paused_watch",
            "version": 1,
            "resumed": resumed,
            "request_id": request_id,
            "category_id": category["id"],
            "topic_id": topic["id"],
            "policy_id": policy["id"],
            "watch_id": watch["id"],
            "name": watch["name"],
            "interest": topic["description"],
            "primary_terms": [term["term"] for term in terms],
            "status": watch["status"],
            "target_type": watch["target_type"],
            "discovery_enabled": bool(watch["discovery_enabled"]),
            "priority": watch["priority"],
            "next_action": "add_sources",
            "paid_budget_usd": float(policy["paid_budget_usd"] or 0.0),
            "paid_escalation_enabled": False,
            "monitor_count": int(monitor_count),
            "job_count": int(job_count),
            "category": category_payload,
            "topic": topic_payload,
            "topic_terms": term_payload,
            "policy": policy_payload,
            "watch": watch_payload,
        }

    @classmethod
    def _existing_paused_setup(
        cls,
        conn: sqlite3.Connection,
        *,
        request_id: str,
        interest: str,
        name: str,
        terms: Sequence[str],
    ) -> dict[str, Any] | None:
        watch = conn.execute("SELECT * FROM watches WHERE id = ?", (request_id,)).fetchone()
        if watch is None:
            return None
        if (
            watch["target_type"] != "topic"
            or watch["status"] != "paused"
            or watch["priority"] != "normal"
            or watch["discovery_enabled"] != 0
            or watch["name"] != name
        ):
            raise DomainConflict("request identity is already used by another Watch")
        topic = conn.execute("SELECT * FROM topics WHERE id = ?", (watch["target_id"],)).fetchone()
        if topic is None or topic["deleted_at"] is not None or topic["category_id"] is None:
            raise DomainConflict("request identity is already used by another Watch")
        category = conn.execute("SELECT * FROM categories WHERE id = ?", (topic["category_id"],)).fetchone()
        category = cls._require_canonical_setup_category(category)
        if (
            topic["name"] != name
            or topic["description"] != interest
            or topic["slug"] != cls._setup_topic_slug(request_id)
        ):
            raise DomainConflict("request identity is already used by another Watch")
        term_rows = conn.execute(
            "SELECT * FROM topic_terms WHERE topic_id = ? ORDER BY rowid", (topic["id"],)
        ).fetchall()
        if len(term_rows) != len(terms) or any(
            row["term_type"] != "include"
            or row["concept_kind"] != "term"
            or row["term_normalized"] != normalized_text(term)
            for row, term in zip(term_rows, terms)
        ):
            raise DomainConflict("request identity is already used by another Watch")
        policy = conn.execute(
            "SELECT * FROM monitoring_policies WHERE id = ?", (watch["policy_id"],)
        ).fetchone()
        if policy is None:
            raise DomainConflict("request identity is already used by another Watch")
        expected_channels = ["rss", "atom", "direct_http", "page"]
        if (
            policy["name"] != WATCH_SETUP_POLICY_NAME
            or json.loads(policy["allowed_channels"] or "[]") != expected_channels
            or policy["base_cadence_seconds"] != WATCH_SETUP_BASE_CADENCE_SECONDS
            or policy["min_cadence_seconds"] != WATCH_SETUP_MIN_CADENCE_SECONDS
            or policy["max_cadence_seconds"] != WATCH_SETUP_MAX_CADENCE_SECONDS
            or policy["priority"] != "normal"
            or policy["query_budget"] != WATCH_SETUP_QUERY_BUDGET
            or float(policy["paid_budget_usd"] or 0.0) != 0.0
            or policy["local_model_budget"] != WATCH_SETUP_LOCAL_MODEL_BUDGET
            or json.loads(policy["escalation_rules"] or "{}") != {}
            or json.loads(policy["backoff_rules"] or "{}") != {}
            or json.loads(policy["retirement_criteria"] or "{}") != {}
        ):
            raise DomainConflict("request identity is already used by another Watch")
        return cls._setup_response(
            conn,
            request_id=request_id,
            category=category,
            topic=topic,
            terms=term_rows,
            policy=policy,
            watch=watch,
            resumed=True,
        )

    def create_paused_setup(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Atomically create or resume the bounded first-run Watch draft."""
        request_id, interest, name, terms = self._validated_paused_setup(data)
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                existing = self._existing_paused_setup(
                    conn,
                    request_id=request_id,
                    interest=interest,
                    name=name,
                    terms=terms,
                )
                if existing is not None:
                    return existing

                category = conn.execute(
                    "SELECT * FROM categories WHERE slug = ?", (WATCH_SETUP_CATEGORY_SLUG,)
                ).fetchone()
                if category is None:
                    category_id = new_id("cat")
                    conn.execute(
                        """
                        INSERT INTO categories(
                            id, slug, name, description, display_order, enabled, priority,
                            max_stories_per_run, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 0, 1, 'normal', NULL, ?, ?)
                        """,
                        (
                            category_id,
                            WATCH_SETUP_CATEGORY_SLUG,
                            WATCH_SETUP_CATEGORY_NAME,
                            WATCH_SETUP_CATEGORY_DESCRIPTION,
                            now,
                            now,
                        ),
                    )
                    category = conn.execute(
                        "SELECT * FROM categories WHERE id = ?", (category_id,)
                    ).fetchone()
                category = self._require_canonical_setup_category(category)

                topic_id = new_id("top")
                conn.execute(
                    """
                    INSERT INTO topics(
                        id, category_id, slug, name, description, enabled, priority,
                        max_queries_per_run, max_stories_per_run, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 1, 'normal', NULL, NULL, ?, ?)
                    """,
                    (
                        topic_id,
                        category["id"],
                        self._setup_topic_slug(request_id),
                        name,
                        interest,
                        now,
                        now,
                    ),
                )
                for term in terms:
                    conn.execute(
                        """
                        INSERT INTO topic_terms(
                            id, topic_id, term, term_normalized, term_type, weight,
                            created_at, concept_kind
                        ) VALUES (?, ?, ?, ?, 'include', 1.0, ?, 'term')
                        """,
                        (new_id("term"), topic_id, term, normalized_text(term), now),
                    )

                policy_id = new_id("pol")
                allowed_channels = ["rss", "atom", "direct_http", "page"]
                conn.execute(
                    """
                    INSERT INTO monitoring_policies(
                        id, name, allowed_channels, base_cadence_seconds,
                        min_cadence_seconds, max_cadence_seconds, priority, query_budget,
                        paid_budget_usd, local_model_budget, escalation_rules, backoff_rules,
                        retirement_criteria, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'normal', ?, 0.0, ?, '{}', '{}', '{}', ?, ?)
                    """,
                    (
                        policy_id,
                        WATCH_SETUP_POLICY_NAME,
                        json.dumps(allowed_channels, separators=(",", ":")),
                        WATCH_SETUP_BASE_CADENCE_SECONDS,
                        WATCH_SETUP_MIN_CADENCE_SECONDS,
                        WATCH_SETUP_MAX_CADENCE_SECONDS,
                        WATCH_SETUP_QUERY_BUDGET,
                        WATCH_SETUP_LOCAL_MODEL_BUDGET,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO watches(
                        id, name, target_type, target_id, policy_id, status, priority,
                        discovery_enabled, created_at, updated_at
                    ) VALUES (?, ?, 'topic', ?, ?, 'paused', 'normal', 0, ?, ?)
                    """,
                    (request_id, name, topic_id, policy_id, now, now),
                )
                watch = conn.execute("SELECT * FROM watches WHERE id = ?", (request_id,)).fetchone()
                topic = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
                category = conn.execute(
                    "SELECT * FROM categories WHERE id = ?", (category["id"],)
                ).fetchone()
                term_rows = conn.execute(
                    "SELECT * FROM topic_terms WHERE topic_id = ? ORDER BY rowid", (topic_id,)
                ).fetchall()
                policy = conn.execute(
                    "SELECT * FROM monitoring_policies WHERE id = ?", (policy_id,)
                ).fetchone()
                return self._setup_response(
                    conn,
                    request_id=request_id,
                    category=category,
                    topic=topic,
                    terms=term_rows,
                    policy=policy,
                    watch=watch,
                    resumed=False,
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("paused Watch setup already exists") from exc
        finally:
            conn.close()

    def get(self, watch_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            watch = _row(self._require_watch(conn, watch_id))
            watch["vocabulary"] = [
                _row(row)
                for row in conn.execute(
                    """
                    SELECT * FROM watch_vocabulary
                    WHERE watch_id = ?
                    ORDER BY created_at, id
                    """,
                    (watch_id,),
                )
            ]
            watch["source_candidates"] = [
                self._candidate_payload(row)
                for row in conn.execute(
                    """
                    SELECT * FROM source_candidates
                    WHERE watch_id = ?
                    ORDER BY created_at, id
                    """,
                    (watch_id,),
                )
            ]
            watch["sources"] = [
                {
                    "source": {
                        "id": row["source_id"],
                        "name": row["name"],
                        "slug": row["slug"],
                        "domain": row["domain"],
                        "homepage_url": row["homepage_url"],
                        "feed_url": row["feed_url"],
                        "source_kind": row["source_kind"],
                    },
                    "monitor": {
                        "id": row["monitor_id"],
                        "enabled": row["enabled"],
                        "next_check_at": row["next_check_at"],
                        "last_run_at": row["last_run_at"],
                        "last_result": row["last_result"],
                        "need_type": row["need_type"],
                        "need_id": row["need_id"],
                    },
                    "linked_at": row["linked_at"],
                }
                for row in conn.execute(
                    """
                    SELECT ws.created_at AS linked_at, ws.source_id, ws.monitor_id,
                           s.name, s.slug, s.domain, s.homepage_url, s.feed_url,
                           s.source_kind,
                           m.enabled, m.next_check_at, m.last_run_at, m.last_result,
                           m.need_type, m.need_id
                    FROM watch_sources AS ws
                    JOIN sources AS s ON s.id = ws.source_id
                    JOIN monitors AS m ON m.id = ws.monitor_id
                    WHERE ws.watch_id = ?
                    ORDER BY s.name, s.id
                    """,
                    (watch_id,),
                )
            ]
            return watch
        finally:
            conn.close()

    def list(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        if status is not None and status not in WATCH_STATUSES:
            raise DomainValidation("invalid watch status")
        if page < 1 or not 1 <= page_size <= 100:
            raise DomainValidation("invalid pagination")
        conn = storage.connect(self.db_path)
        try:
            where, params = ("status = ?", [status]) if status else ("1 = 1", [])
            total = conn.execute(
                f"SELECT COUNT(*) FROM watches WHERE {where}", params
            ).fetchone()[0]
            identifiers = [
                row[0]
                for row in conn.execute(
                    f"""
                    SELECT id FROM watches WHERE {where}
                    ORDER BY updated_at DESC, id
                    LIMIT ? OFFSET ?
                    """,
                    [*params, page_size, (page - 1) * page_size],
                )
            ]
        finally:
            conn.close()
        return {
            "items": [self.get(identifier) for identifier in identifiers],
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    @staticmethod
    def _page_bounds(page: int, page_size: int) -> None:
        if (
            isinstance(page, bool)
            or isinstance(page_size, bool)
            or page < 1
            or not 1 <= page_size <= MAX_PAGE_SIZE
        ):
            raise DomainValidation(
                f"page must be >= 1 and page_size must be between 1 and {MAX_PAGE_SIZE}"
            )

    def list_vocabulary(
        self,
        watch_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        if status is not None and status not in {"suggested", "approved", "rejected"}:
            raise DomainValidation("invalid vocabulary status")
        self._page_bounds(page, page_size)
        conn = storage.connect(self.db_path)
        try:
            self._require_watch(conn, watch_id)
            where = "watch_id = ?"
            params: list[Any] = [watch_id]
            if status is not None:
                where += " AND status = ?"
                params.append(status)
            total = conn.execute(
                f"SELECT COUNT(*) FROM watch_vocabulary WHERE {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT * FROM watch_vocabulary
                WHERE {where}
                ORDER BY created_at, id
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [_row(row) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    def list_source_candidates(
        self,
        watch_id: str,
        *,
        status: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        if status is not None and status not in {"suggested", "approved", "rejected"}:
            raise DomainValidation("invalid source candidate status")
        self._page_bounds(page, page_size)
        conn = storage.connect(self.db_path)
        try:
            self._require_watch(conn, watch_id)
            where = "watch_id = ?"
            params: list[Any] = [watch_id]
            if status is not None:
                where += " AND status = ?"
                params.append(status)
            total = conn.execute(
                f"SELECT COUNT(*) FROM source_candidates WHERE {where}", params
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT * FROM source_candidates
                WHERE {where}
                ORDER BY created_at, id
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "items": [self._candidate_payload(row) for row in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        finally:
            conn.close()

    def list_sources(
        self, watch_id: str, *, page: int = 1, page_size: int = 25
    ) -> dict[str, Any]:
        self._page_bounds(page, page_size)
        conn = storage.connect(self.db_path)
        try:
            self._require_watch(conn, watch_id)
            total = conn.execute(
                "SELECT COUNT(*) FROM watch_sources WHERE watch_id = ?", (watch_id,)
            ).fetchone()[0]
            rows = conn.execute(
                """
                SELECT ws.created_at AS linked_at, ws.source_id, ws.monitor_id,
                       s.name, s.slug, s.domain, s.homepage_url, s.feed_url,
                       s.source_kind, m.enabled, m.next_check_at, m.last_run_at,
                       m.last_result, m.need_type, m.need_id
                FROM watch_sources AS ws
                JOIN sources AS s ON s.id = ws.source_id
                JOIN monitors AS m ON m.id = ws.monitor_id
                WHERE ws.watch_id = ?
                ORDER BY s.name, s.id
                LIMIT ? OFFSET ?
                """,
                (watch_id, page_size, (page - 1) * page_size),
            ).fetchall()
            items = [
                {
                    "source": {
                        "id": row["source_id"],
                        "name": row["name"],
                        "slug": row["slug"],
                        "domain": row["domain"],
                        "homepage_url": row["homepage_url"],
                        "feed_url": row["feed_url"],
                        "source_kind": row["source_kind"],
                    },
                    "monitor": {
                        "id": row["monitor_id"],
                        "enabled": row["enabled"],
                        "next_check_at": row["next_check_at"],
                        "last_run_at": row["last_run_at"],
                        "last_result": row["last_result"],
                        "need_type": row["need_type"],
                        "need_id": row["need_id"],
                    },
                    "linked_at": row["linked_at"],
                }
                for row in rows
            ]
            return {"items": items, "page": page, "page_size": page_size, "total": total}
        finally:
            conn.close()

    def health(self, watch_id: str) -> dict[str, Any]:
        """Return a bounded coverage and operational summary derived from state."""
        conn = storage.connect(self.db_path)
        try:
            watch = self._require_watch(conn, watch_id)
            monitor_summary = conn.execute(
                """
                SELECT COUNT(*) AS attached_source_count,
                       SUM(CASE WHEN m.enabled = 1 THEN 1 ELSE 0 END) AS active_source_count,
                       MAX(m.last_run_at) AS last_attempt,
                       MAX(CASE WHEN m.last_result <> 'error' THEN m.last_run_at END) AS last_success,
                       MIN(CASE WHEN m.enabled = 1 THEN m.next_check_at END) AS next_scheduled_run,
                       MAX(CASE WHEN m.last_result = 'error' THEN m.last_run_at END) AS last_monitor_error
                FROM watch_sources AS ws
                JOIN monitors AS m ON m.id = ws.monitor_id
                WHERE ws.watch_id = ?
                """,
                (watch_id,),
            ).fetchone()
            pending_vocabulary = conn.execute(
                """
                SELECT COUNT(*) FROM watch_vocabulary
                WHERE watch_id = ? AND status = 'suggested'
                """,
                (watch_id,),
            ).fetchone()[0]
            pending_candidates = conn.execute(
                """
                SELECT COUNT(*) FROM source_candidates
                WHERE watch_id = ? AND status = 'suggested'
                """,
                (watch_id,),
            ).fetchone()[0]
            jobs = conn.execute(
                """
                SELECT job_type, status, payload_json, created_at, updated_at,
                       failure_cause
                FROM jobs
                WHERE job_type IN ('monitor_check', 'watch_source_discovery',
                                   'watch_vocabulary_suggestion')
                ORDER BY updated_at DESC, id DESC
                LIMIT 100
                """
            ).fetchall()
        finally:
            conn.close()

        discovery_job: sqlite3.Row | None = None
        recent_error = None
        for job in jobs:
            try:
                payload = json.loads(job["payload_json"] or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
            if not isinstance(payload, Mapping) or payload.get("watch_id") != watch_id:
                continue
            if job["job_type"] == WATCH_SOURCE_DISCOVERY_JOB_TYPE and discovery_job is None:
                discovery_job = job
            if job["status"] in {"failed", "cancelled"} and recent_error is None:
                recent_error = job["failure_cause"] or job["status"]

        if watch["discovery_error"]:
            recent_error = watch["discovery_error"]
        elif monitor_summary["last_monitor_error"] and recent_error is None:
            recent_error = "monitor_error"
        return {
            "watch_id": watch_id,
            "status": watch["status"],
            "discovery_enabled": bool(watch["discovery_enabled"]),
            "attached_source_count": int(monitor_summary["attached_source_count"] or 0),
            "active_source_count": int(monitor_summary["active_source_count"] or 0),
            "pending_source_candidate_count": int(pending_candidates),
            "pending_vocabulary_suggestion_count": int(pending_vocabulary),
            "last_attempt": monitor_summary["last_attempt"],
            "last_success": monitor_summary["last_success"],
            "next_scheduled_run": monitor_summary["next_scheduled_run"],
            "last_discovery_run": watch["last_discovery_at"],
            "last_discovery_status": discovery_job["status"] if discovery_job else None,
            "last_error": recent_error,
        }

    def update(self, watch_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        """Update mutable Watch intent without changing its target identity."""
        allowed = {"name", "policy_id", "priority", "discovery_enabled"}
        unknown = set(data) - allowed
        if unknown:
            raise DomainValidation(f"unsupported watch fields: {sorted(unknown)}")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                current = self._require_watch(conn, watch_id)
                values: dict[str, Any] = {}
                if "name" in data:
                    name = str(data["name"]).strip()
                    if not name or len(name) > 200:
                        raise DomainValidation("watch name must be between 1 and 200 characters")
                    values["name"] = name
                if "priority" in data:
                    priority = str(data["priority"]).strip()
                    if priority not in WATCH_PRIORITIES:
                        raise DomainValidation("invalid watch priority")
                    values["priority"] = priority
                if "discovery_enabled" in data:
                    if not isinstance(data["discovery_enabled"], bool):
                        raise DomainValidation("discovery_enabled must be a boolean")
                    values["discovery_enabled"] = int(data["discovery_enabled"])
                policy_id = str(data.get("policy_id", current["policy_id"])).strip()
                if not policy_id:
                    raise DomainValidation("watch policy_id must not be empty")
                if conn.execute(
                    "SELECT 1 FROM monitoring_policies WHERE id = ?", (policy_id,)
                ).fetchone() is None:
                    raise DomainNotFound("monitoring policy not found")
                values["policy_id"] = policy_id
                values["updated_at"] = utc_now()
                assignments = ", ".join(f"{field} = ?" for field in values)
                conn.execute(
                    f"UPDATE watches SET {assignments} WHERE id = ?",
                    [*values.values(), watch_id],
                )
                if policy_id != current["policy_id"]:
                    conn.execute(
                        """
                        UPDATE monitors SET policy_id = ?, updated_at = ?
                        WHERE id IN (SELECT monitor_id FROM watch_sources WHERE watch_id = ?)
                        """,
                        (policy_id, values["updated_at"], watch_id),
                    )
        finally:
            conn.close()
        return self.get(watch_id)

    def _set_status(self, watch_id: str, status: str) -> dict[str, Any]:
        """Pause/resume only the Monitors this Watch owns.

        `watch_sources.monitor_id` is UNIQUE, so a Monitor reached from here can
        never be another Watch's Monitor even when the Source itself is shared.
        """
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_watch(conn, watch_id)
                conn.execute(
                    "UPDATE watches SET status = ?, updated_at = ? WHERE id = ?",
                    (status, now, watch_id),
                )
                conn.execute(
                    """
                    UPDATE monitors
                       SET enabled = ?, updated_at = ?
                     WHERE id IN (SELECT monitor_id FROM watch_sources WHERE watch_id = ?)
                    """,
                    (int(status == "active"), now, watch_id),
                )
        finally:
            conn.close()
        return self.get(watch_id)

    def pause(self, watch_id: str) -> dict[str, Any]:
        return self._set_status(watch_id, "paused")

    def resume(self, watch_id: str) -> dict[str, Any]:
        return self._set_status(watch_id, "active")

    def disable(self, watch_id: str) -> dict[str, Any]:
        return self._set_status(watch_id, "disabled")

    # ------------------------------------------------------------------
    # Vocabulary
    # ------------------------------------------------------------------

    def _deterministic_terms(
        self, conn: sqlite3.Connection, watch: sqlite3.Row
    ) -> list[tuple[str, str, str | None, str, str]]:
        """Derive suggestions from persisted domain state, never a hardcoded list.

        The approved scope of the Watch target already carries the reviewed
        Topic terms, Subject aliases, entities, and concepts, so those are the
        honest deterministic seed. Initialisms are derived structurally.
        """
        name = str(watch["name"]).strip()
        candidates: list[tuple[str, str, str | None, str, str]] = [
            (name, "primary", None, "user", "Watch title")
        ]
        scope = _scope_for_target(conn, watch["target_type"], watch["target_id"])
        origin = "topic" if watch["target_type"] == "topic" else "subject"
        for term in scope.exact_terms:
            candidates.append((term, "primary", None, origin, "Approved target term"))
        for term in scope.vocabulary:
            candidates.append((term, "alias", None, origin, "Approved target vocabulary"))
        for term in scope.entities:
            candidates.append((term, "related", None, origin, "Approved target entity"))
        for term in scope.concepts:
            candidates.append((term, "related", None, origin, "Approved target concept"))
        for term in scope.exclusions:
            candidates.append((term, "exclude", None, origin, "Approved target exclusion"))

        # Structural acronym derivation over the positive terms gathered above.
        phrases = [term for term, kind, _, _, _ in list(candidates) if kind != "exclude"]
        for phrase in phrases:
            acronym = _initialism(phrase)
            if acronym is None:
                continue
            candidates.append(
                (acronym, "acronym", phrase, "deterministic", f"Initialism of {phrase!r}")
            )
            candidates.append(
                (
                    phrase,
                    "acronym_expansion",
                    acronym,
                    "deterministic",
                    f"Expansion of {acronym!r}",
                )
            )
        return candidates

    @staticmethod
    def _validated_provider_terms(
        payload: Any, limit: int
    ) -> list[tuple[str, str, str | None, str, str]]:
        """Bound and validate provider output before it can reach persistence.

        Invalid provider output must never mutate Watch state, so anything that
        is not a well-formed suggestion is dropped rather than persisted.
        """
        if isinstance(payload, VocabularyOutput):
            payload = [item.model_dump() for item in payload.suggestions]
        elif isinstance(payload, Mapping) and "suggestions" in payload:
            payload = payload["suggestions"]
        if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)):
            raise DomainValidation("vocabulary provider must return a sequence")
        validated: list[tuple[str, str, str | None, str, str]] = []
        for item in list(payload)[:limit]:
            if not isinstance(item, Mapping):
                continue
            term = str(item.get("term", "")).strip()
            kind = str(item.get("kind", "related"))
            if not term or len(term) > MAX_TERM_LENGTH or kind not in VOCABULARY_KINDS:
                continue
            expansion_of = item.get("expansion_of")
            expansion_of = (
                str(expansion_of)[:MAX_TERM_LENGTH] if expansion_of is not None else None
            )
            rationale = str(item.get("rationale", "Provider suggestion"))
            validated.append(
                (term, kind, expansion_of, "ai", rationale[:MAX_RATIONALE_LENGTH])
            )
        return validated

    def suggest_vocabulary(
        self,
        watch_id: str,
        *,
        limit: int = 20,
        provider: Callable[[Mapping[str, Any]], Any] | None = None,
        work_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Propose terminology for review.

        Suggestions are persisted as `status='suggested'` and `enabled=0`, so
        they cannot influence monitoring until a human approves them. A
        previously rejected term is preserved by the UNIQUE constraint and is
        therefore never resurrected by a later run.
        """
        if not 1 <= limit <= MAX_SUGGESTIONS_PER_RUN:
            raise DomainValidation(
                f"vocabulary suggestion limit must be 1-{MAX_SUGGESTIONS_PER_RUN}"
            )
        conn = storage.connect(self.db_path)
        try:
            watch = self._require_watch(conn, watch_id)
            candidates = self._deterministic_terms(conn, watch)
            if self.router is not None and provider is None:
                policy = conn.execute(
                    "SELECT paid_budget_usd FROM monitoring_policies WHERE id = ?",
                    (watch["policy_id"],),
                ).fetchone()
                paid_route_allowed = not self.router.policy.paid_enabled
                if self.router.policy.paid_enabled:
                    paid_route_allowed = bool(
                        policy is not None
                        and float(policy["paid_budget_usd"] or 0.0) >= self.router.policy.paid_request_cost_usd
                        and BudgetService(self.db_path).paid_enabled()
                    )
                if paid_route_allowed:
                    scope = _scope_for_target(
                        conn, watch["target_type"], watch["target_id"]
                    )
                    request = VocabularyRequest(
                        watch_name=str(watch["name"]),
                        target_type=str(watch["target_type"]),
                        approved_terms=tuple(dict.fromkeys(scope.all_terms()))[:200],
                        max_suggestions=limit,
                    )
                    try:
                        payload = self.router.vocabulary(
                            request, work_id=work_id or f"watch:{watch_id}"
                        )
                    except AIError:
                        payload = None
                    if payload is not None:
                        try:
                            candidates.extend(
                                self._validated_provider_terms(payload, limit)
                            )
                        except DomainValidation:
                            pass
            elif provider is not None:
                # Provider failure is isolated: the deterministic suggestions
                # and the existing Watch configuration must survive it.
                try:
                    payload = provider(
                        {
                            "name": str(watch["name"]),
                            "target_type": watch["target_type"],
                        }
                    )
                except Exception:  # noqa: BLE001 - optional enhancement only
                    payload = []
                try:
                    candidates.extend(self._validated_provider_terms(payload, limit))
                except DomainValidation:
                    pass

            now = utc_now()
            seen: set[tuple[str, str]] = set()
            with storage.write_tx(conn):
                for term, kind, expansion_of, origin, rationale in candidates:
                    term = term.strip()
                    if not term or len(term) > MAX_TERM_LENGTH:
                        continue
                    if kind not in VOCABULARY_KINDS:
                        continue
                    if any(ord(character) < 32 for character in term):
                        continue
                    identity = (normalized_text(term), kind)
                    if identity in seen:
                        continue
                    seen.add(identity)
                    if len(seen) > limit:
                        break
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO watch_vocabulary(
                            id, watch_id, term, term_normalized, kind, origin,
                            status, enabled, expansion_of, rationale, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, 'suggested', 0, ?, ?, ?)
                        """,
                        (
                            new_id("wv"),
                            watch_id,
                            term,
                            normalized_text(term),
                            kind,
                            origin,
                            expansion_of,
                            rationale[:MAX_RATIONALE_LENGTH],
                            now,
                        ),
                    )
            return [
                _row(row)
                for row in conn.execute(
                    """
                    SELECT * FROM watch_vocabulary
                    WHERE watch_id = ?
                    ORDER BY created_at, id
                    """,
                    (watch_id,),
                )
            ]
        finally:
            conn.close()

    def add_vocabulary(self, watch_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        """Record an explicit user term, already approved and active."""
        term = str(data.get("term", "")).strip()
        kind = str(data.get("kind", "alias"))
        if not term or len(term) > MAX_TERM_LENGTH:
            raise DomainValidation(
                f"vocabulary term must be between 1 and {MAX_TERM_LENGTH} characters"
            )
        if any(ord(character) < 32 for character in term):
            raise DomainValidation("vocabulary term must not contain control characters")
        if kind not in VOCABULARY_KINDS:
            raise DomainValidation("unsupported vocabulary kind")
        expansion_of = data.get("expansion_of")
        identifier = new_id("wv")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_watch(conn, watch_id)
                conn.execute(
                    """
                    INSERT INTO watch_vocabulary(
                        id, watch_id, term, term_normalized, kind, origin,
                        status, enabled, expansion_of, rationale, created_at,
                        reviewed_at, reviewed_by)
                    VALUES (?, ?, ?, ?, ?, 'user', 'approved', 1, ?, ?, ?, ?, ?)
                    """,
                    (
                        identifier,
                        watch_id,
                        term,
                        normalized_text(term),
                        kind,
                        str(expansion_of)[:MAX_TERM_LENGTH] if expansion_of else None,
                        str(data.get("rationale", "Added by user"))[:MAX_RATIONALE_LENGTH],
                        now,
                        now,
                        str(data.get("created_by", "user"))[:200],
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict("vocabulary term already exists for this watch") from exc
        finally:
            conn.close()
        self._refresh_scopes(watch_id, changed_by=str(data.get("created_by", "user")))
        return self.get_vocabulary(watch_id, identifier)

    def get_vocabulary(self, watch_id: str, vocabulary_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM watch_vocabulary WHERE id = ? AND watch_id = ?",
                (vocabulary_id, watch_id),
            ).fetchone()
            if row is None:
                raise DomainNotFound("watch vocabulary not found")
            return _row(row)
        finally:
            conn.close()

    def review_vocabulary(
        self, watch_id: str, vocabulary_id: str, status: str, reviewed_by: str
    ) -> dict[str, Any]:
        if status not in {"approved", "rejected"}:
            raise DomainValidation("vocabulary may only be approved or rejected")
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                row = conn.execute(
                    "SELECT * FROM watch_vocabulary WHERE id = ? AND watch_id = ?",
                    (vocabulary_id, watch_id),
                ).fetchone()
                if row is None:
                    raise DomainNotFound("watch vocabulary not found")
                if row["status"] not in {"suggested", status}:
                    raise DomainConflict("vocabulary has already been reviewed")
                conn.execute(
                    """
                    UPDATE watch_vocabulary
                       SET status = ?, enabled = ?, reviewed_at = ?, reviewed_by = ?
                     WHERE id = ?
                    """,
                    (
                        status,
                        int(status == "approved"),
                        utc_now(),
                        str(reviewed_by)[:200],
                        vocabulary_id,
                    ),
                )
        finally:
            conn.close()
        self._refresh_scopes(watch_id, changed_by=reviewed_by)
        return self.get_vocabulary(watch_id, vocabulary_id)

    def _refresh_scopes(self, watch_id: str, *, changed_by: str) -> None:
        """Append a new approved scope snapshot to this Watch's Monitors.

        Existing snapshots stay immutable, so already-pinned processing jobs
        keep evaluating the scope that existed at acquisition time.
        """
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                watch = self._require_watch(conn, watch_id)
                base = _scope_for_target(
                    conn, watch["target_type"], watch["target_id"]
                )
                terms = conn.execute(
                    """
                    SELECT term, kind FROM watch_vocabulary
                    WHERE watch_id = ? AND status = 'approved' AND enabled = 1
                    """,
                    (watch_id,),
                ).fetchall()
                positive = tuple(row[0] for row in terms if row[1] != "exclude")
                exclusions = tuple(row[0] for row in terms if row[1] == "exclude")
                scope = RelevanceScope(
                    exact_terms=base.exact_terms,
                    vocabulary=tuple(dict.fromkeys((*base.vocabulary, *positive))),
                    entities=base.entities,
                    concepts=base.concepts,
                    semantic_terms=tuple(
                        dict.fromkeys((*base.semantic_terms, *positive))
                    ),
                    exclusions=tuple(dict.fromkeys((*base.exclusions, *exclusions))),
                    semantic_threshold=base.semantic_threshold,
                )
                for row in conn.execute(
                    "SELECT monitor_id FROM watch_sources WHERE watch_id = ?",
                    (watch_id,),
                ):
                    MonitorService._write_scope_history(
                        conn,
                        row[0],
                        scope,
                        change_type="approved",
                        changed_by=changed_by,
                        created_at=now,
                    )
        finally:
            conn.close()

    def query_plan(self, watch_id: str, *, limit: int = MAX_QUERY_VARIANTS) -> dict[str, Any]:
        """Build a bounded deterministic plan from approved Watch vocabulary.

        Each variant contains one selected term. This intentionally avoids a
        Cartesian product of primary, alias, and contextual terms. The
        existing policy query budget is the first cap; the hard Phase 24 cap
        remains in force even when a policy is configured more generously.
        """
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise DomainValidation("query plan limit must be between 1 and 100")
        conn = storage.connect(self.db_path)
        try:
            watch = self._require_watch(conn, watch_id)
            policy = conn.execute(
                "SELECT query_budget FROM monitoring_policies WHERE id = ?",
                (watch["policy_id"],),
            ).fetchone()
            policy_budget = int(policy["query_budget"] or 0) if policy else 0
            variant_limit = min(MAX_QUERY_VARIANTS, limit, policy_budget)
            scope = _scope_for_target(conn, watch["target_type"], watch["target_id"])
            rows = conn.execute(
                """
                SELECT term, kind
                FROM watch_vocabulary
                WHERE watch_id = ? AND status = 'approved' AND enabled = 1
                ORDER BY created_at, id
                LIMIT ?
                """,
                (watch_id, MAX_ACTIVE_QUERY_TERMS),
            ).fetchall()
        finally:
            conn.close()

        primary = list(scope.exact_terms)
        supporting = [
            *scope.vocabulary,
            *scope.entities,
            *scope.concepts,
            *scope.semantic_terms,
        ]
        exclusions = list(scope.exclusions)
        for row in rows:
            if row["kind"] in {"primary", "acronym", "acronym_expansion", "include"}:
                primary.append(row["term"])
            elif row["kind"] in {"alias", "synonym", "related"}:
                supporting.append(row["term"])
            elif row["kind"] == "exclude":
                exclusions.append(row["term"])

        def unique(values: Sequence[str], cap: int) -> list[str]:
            result: list[str] = []
            seen: set[str] = set()
            for value in values:
                term = str(value).strip()
                identity = normalized_text(term)
                if not identity or identity in seen:
                    continue
                seen.add(identity)
                result.append(term)
                if len(result) >= cap:
                    break
            return result

        primary_terms = unique(primary, MAX_ACTIVE_QUERY_TERMS)
        supporting_terms = unique(supporting, MAX_ACTIVE_QUERY_TERMS)
        excluded_terms = unique(exclusions, MAX_ACTIVE_QUERY_TERMS)
        variants: list[dict[str, Any]] = []
        for category, terms in (("primary", primary_terms), ("supporting", supporting_terms)):
            for term in terms:
                if len(variants) >= variant_limit:
                    break
                variants.append({"query": term, "category": category, "terms": [term]})
            if len(variants) >= variant_limit:
                break
        return {
            "watch_id": watch_id,
            "query_budget": policy_budget,
            "requested_limit": limit,
            "variant_count": len(variants),
            "variants": variants,
            "active_terms": unique([*primary_terms, *supporting_terms], MAX_ACTIVE_QUERY_TERMS),
            "excluded_terms": excluded_terms,
        }

    # ------------------------------------------------------------------
    # Source candidates
    # ------------------------------------------------------------------

    @staticmethod
    def _candidate_payload(row: sqlite3.Row) -> dict[str, Any]:
        payload = _row(row)
        payload["provenance"] = json.loads(payload.pop("provenance_json"))
        return payload

    def add_source_candidate(
        self, watch_id: str, data: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Record a candidate Source for human review.

        A candidate is never monitored. It only becomes an active Watch Source
        through `review_source_candidate`, which goes through the normal
        Source and Monitor services.
        """
        name = str(data.get("name", "")).strip()
        rationale = str(data.get("rationale", "")).strip()
        method = str(data.get("discovery_method", "manual"))
        if not name or not rationale or method not in DISCOVERY_METHODS:
            raise DomainValidation(
                "source candidate requires name, rationale, and a supported discovery method"
            )
        requested_source_id = str(data.get("source_id") or "").strip() or None
        identifier = new_id("cand")
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_watch(conn, watch_id)
                selected_source = None
                if requested_source_id:
                    selected_source = conn.execute(
                        """
                        SELECT id, homepage_url, feed_url
                        FROM sources
                        WHERE id = ? AND deleted_at IS NULL
                        """,
                        (requested_source_id,),
                    ).fetchone()
                    if selected_source is None:
                        raise DomainNotFound("source not found")
                homepage_value = data.get("homepage_url") or (
                    selected_source["homepage_url"] or selected_source["feed_url"]
                    if selected_source is not None
                    else None
                )
                if not homepage_value:
                    raise DomainValidation(
                        "source candidate requires a usable homepage or feed URL"
                    )
                url = _safe_url(homepage_value)
                feed_value = data.get("feed_url") or (
                    selected_source["feed_url"] if selected_source is not None else None
                )
                feed = _safe_url(feed_value) if feed_value else None
                normalized = _normalized_candidate_url(url)
                existing = conn.execute(
                    "SELECT id FROM source_candidates WHERE watch_id = ? AND normalized_url = ?",
                    (watch_id, normalized),
                ).fetchone()
                if existing is not None:
                    identifier = existing[0]
                else:
                    source = selected_source or conn.execute(
                            """
                            SELECT id FROM sources
                            WHERE deleted_at IS NULL
                              AND (homepage_url = ? OR (feed_url IS NOT NULL AND feed_url = ?))
                            ORDER BY id
                            LIMIT 1
                            """,
                            (url, feed or url),
                        ).fetchone()
                    conn.execute(
                        """
                        INSERT INTO source_candidates(
                            id, watch_id, source_id, name, homepage_url, normalized_url,
                            feed_url, discovery_method, rationale, authority_context,
                            limitations, provenance_json, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            identifier,
                            watch_id,
                            source[0] if source else None,
                            name[:200],
                            url,
                            normalized,
                            feed,
                            method,
                            rationale[:MAX_RATIONALE_LENGTH],
                            str(data.get("authority_context", ""))[:MAX_RATIONALE_LENGTH],
                            str(data.get("limitations", ""))[:MAX_RATIONALE_LENGTH],
                            json.dumps(
                                dict(data.get("provenance") or {}),
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                            now,
                        ),
                    )
        finally:
            conn.close()
        return self.get_source_candidate(identifier)

    def get_source_candidate(self, candidate_id: str) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM source_candidates WHERE id = ?", (candidate_id,)
            ).fetchone()
            if row is None:
                raise DomainNotFound("source candidate not found")
            return self._candidate_payload(row)
        finally:
            conn.close()

    def _resolve_source(self, candidate: Mapping[str, Any]) -> str:
        """Reuse a known Source, or create one through the normal Source service."""
        if candidate["source_id"]:
            return str(candidate["source_id"])
        slug = normalized_slug(str(candidate["name"]))
        try:
            source = CoreService(self.db_path).create_source(
                {
                    "name": candidate["name"],
                    "slug": slug,
                    "homepage_url": candidate["homepage_url"],
                    "feed_url": candidate["feed_url"],
                    "source_kind": "feed" if candidate["feed_url"] else "web",
                }
            )
            return str(source["id"])
        except (sqlite3.IntegrityError, DomainConflict):
            conn = storage.connect(self.db_path)
            try:
                row = conn.execute(
                    "SELECT id FROM sources WHERE slug = ?", (slug,)
                ).fetchone()
            finally:
                conn.close()
            if row is None:
                raise
            return str(row[0])

    def _resolve_monitor(self, watch: Mapping[str, Any], source_id: str) -> str:
        """Find or create this Watch's Monitor for a Source.

        Monitor identity is (target, information need) since migration 0024, so
        a Source shared by several Watches yields one Monitor per Watch and each
        keeps its own scope and enabled state.
        """
        need_type, need_id = self._need_for(watch)
        monitors = MonitorService(self.db_path)
        try:
            monitor = monitors.create(
                {
                    "target_type": "source",
                    "target_id": source_id,
                    "policy_id": watch["policy_id"],
                    "need_type": need_type,
                    "need_id": need_id,
                    "enabled": watch["status"] == "active",
                }
            )
            return str(monitor["id"])
        except DomainConflict:
            pass
        conn = storage.connect(self.db_path)
        try:
            if need_type is None:
                row = conn.execute(
                    """
                    SELECT id FROM monitors
                    WHERE target_type = 'source' AND target_id = ? AND need_type IS NULL
                    """,
                    (source_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id FROM monitors
                    WHERE target_type = 'source' AND target_id = ?
                      AND need_type = ? AND need_id = ?
                    """,
                    (source_id, need_type, need_id),
                ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise DomainConflict("could not resolve a monitor for this watch source")
        return str(row[0])

    def review_source_candidate(
        self, watch_id: str, candidate_id: str, status: str, reviewed_by: str
    ) -> dict[str, Any]:
        if status not in {"approved", "rejected"}:
            raise DomainValidation(
                "source candidate may only be approved or rejected"
            )
        candidate = self.get_source_candidate(candidate_id)
        if candidate["watch_id"] != watch_id:
            raise DomainNotFound("source candidate not found")
        if candidate["status"] not in {"suggested", status}:
            raise DomainConflict("source candidate has already been reviewed")

        if status == "rejected":
            conn = storage.connect(self.db_path)
            try:
                with storage.write_tx(conn):
                    conn.execute(
                        """
                        UPDATE source_candidates
                           SET status = 'rejected', reviewed_at = ?, reviewed_by = ?
                         WHERE id = ?
                        """,
                        (utc_now(), str(reviewed_by)[:200], candidate_id),
                    )
            finally:
                conn.close()
            return self.get_source_candidate(candidate_id)

        watch = self.get(watch_id)
        source_id = self._resolve_source(candidate)
        monitor_id = self._resolve_monitor(watch, source_id)
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                # A concurrent approval may already have linked this Source.
                # Converge on the existing relationship instead of silently
                # dropping the insert and reporting success.
                linked = conn.execute(
                    "SELECT monitor_id FROM watch_sources WHERE watch_id = ? AND source_id = ?",
                    (watch_id, source_id),
                ).fetchone()
                if linked is None:
                    conn.execute(
                        """
                        INSERT INTO watch_sources(watch_id, source_id, monitor_id, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (watch_id, source_id, monitor_id, utc_now()),
                    )
                conn.execute(
                    """
                    UPDATE source_candidates
                       SET source_id = ?, status = 'approved',
                           reviewed_at = ?, reviewed_by = ?
                     WHERE id = ?
                    """,
                    (source_id, utc_now(), str(reviewed_by)[:200], candidate_id),
                )
        except sqlite3.IntegrityError as exc:
            raise DomainConflict(
                "source is already linked to this watch by another monitor"
            ) from exc
        finally:
            conn.close()
        self._refresh_scopes(watch_id, changed_by=reviewed_by)
        return self.get_source_candidate(candidate_id)

    # ------------------------------------------------------------------
    # Deterministic Source discovery
    # ------------------------------------------------------------------

    def discover_sources(
        self, watch_id: str, *, limit: int = MAX_CANDIDATES_PER_RUN
    ) -> dict[str, Any]:
        """Propose candidate Sources from persisted corpus state only.

        Phase 24 deliberately builds no crawler and issues no network request
        here (§36/§37). `SafeHTMLExtractor` keeps visible text and discards
        anchors, so outbound hyperlinks simply are not part of the corpus. The
        three signals below are the reference information Newsroom genuinely
        does persist:

        * ``existing_source``  a known Source already produced relevant
          material for this Watch's need but is not attached to it;
        * ``document_link``    a Phase 09 lineage parent (cites, syndicated
          from, wire propagation, rewritten from) of a relevant Document;
        * ``feed_discovery``   a relevant Document whose canonical URL lives on
          a different domain than the Source that delivered it, i.e. the
          syndicated original publisher, which has no Source record yet.

        A run that finds nothing is a successful run, not a failure.
        """
        if not 1 <= limit <= MAX_CANDIDATES_PER_RUN:
            raise DomainValidation(
                f"source discovery limit must be 1-{MAX_CANDIDATES_PER_RUN}"
            )
        conn = storage.connect(self.db_path)
        try:
            self._require_watch(conn, watch_id)
            attached = {
                row[0]
                for row in conn.execute(
                    "SELECT source_id FROM watch_sources WHERE watch_id = ?",
                    (watch_id,),
                )
            }
            proposals = self._discovery_proposals(conn, watch_id, attached, limit)
        finally:
            conn.close()

        created: list[dict[str, Any]] = []
        for proposal in proposals:
            try:
                created.append(self.add_source_candidate(watch_id, proposal))
            except DomainValidation:
                # An unusable persisted URL must not fail the whole run.
                continue

        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                conn.execute(
                    """
                    UPDATE watches
                       SET last_discovery_at = ?, discovery_error = NULL, updated_at = ?
                     WHERE id = ?
                    """,
                    (now, now, watch_id),
                )
        finally:
            conn.close()
        return {
            "watch_id": watch_id,
            "ran_at": now,
            "methods": ["existing_source", "document_link", "feed_discovery"],
            "candidates": created,
            "candidate_count": len(created),
            "external_requests": 0,
        }

    def record_discovery_error(self, watch_id: str, message: str) -> None:
        """Persist a bounded discovery failure without disturbing monitoring."""
        now = utc_now()
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_watch(conn, watch_id)
                conn.execute(
                    """
                    UPDATE watches
                       SET last_discovery_at = ?, discovery_error = ?, updated_at = ?
                     WHERE id = ?
                    """,
                    (now, str(message)[:MAX_RATIONALE_LENGTH], now, watch_id),
                )
        finally:
            conn.close()

    def _discovery_proposals(
        self,
        conn: sqlite3.Connection,
        watch_id: str,
        attached: set[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        proposals: list[dict[str, Any]] = []
        seen_sources: set[str] = set()
        seen_domains: set[str] = set()

        # Relevant material acquired for this Watch's own Monitors. Only a
        # confirmed relevant=1 decision qualifies, so discovery inherits the
        # Phase 20 relevance boundary instead of inventing its own.
        relevant = conn.execute(
            """
            SELECT DISTINCT d.id AS document_id, d.source_id, d.canonical_url,
                   s.domain AS source_domain, s.name AS source_name,
                   s.source_kind
            FROM document_version_relevance AS r
            JOIN watch_sources AS ws ON ws.monitor_id = r.monitor_id
            JOIN document_versions AS dv ON dv.id = r.document_version_id
            JOIN documents AS d ON d.id = dv.document_id
            JOIN sources AS s ON s.id = d.source_id
            WHERE ws.watch_id = ? AND r.relevant = 1
            ORDER BY d.id
            LIMIT ?
            """,
            (watch_id, limit * 10),
        ).fetchall()

        # (1) document_link — Sources referenced through persisted lineage.
        for row in conn.execute(
            """
            SELECT DISTINCT s.id, s.name, s.homepage_url, s.feed_url,
                   l.relationship
            FROM document_version_relevance AS r
            JOIN watch_sources AS ws ON ws.monitor_id = r.monitor_id
            JOIN document_versions AS dv ON dv.id = r.document_version_id
            JOIN document_lineage AS l ON l.document_id = dv.document_id
            JOIN documents AS parent ON parent.id = l.parent_document_id
            JOIN sources AS s ON s.id = parent.source_id
            WHERE ws.watch_id = ? AND r.relevant = 1
              AND s.deleted_at IS NULL
            ORDER BY s.id
            LIMIT ?
            """,
            (watch_id, limit),
        ):
            source_id, name, homepage, feed, relationship = row
            if source_id in attached or source_id in seen_sources:
                continue
            if not homepage and not feed:
                continue
            seen_sources.add(source_id)
            proposals.append(
                {
                    "name": name,
                    "homepage_url": homepage or feed,
                    "feed_url": feed,
                    "discovery_method": "document_link",
                    "rationale": (
                        f"Referenced by relevant Documents for this Watch "
                        f"({relationship})."
                    ),
                    "provenance": {"relationship": relationship, "source_id": source_id},
                }
            )

        # (2) existing_source — known Sources already producing relevant
        # material for this Watch that the user has not attached.
        for row in relevant:
            source_id = row["source_id"]
            if source_id in attached or source_id in seen_sources:
                continue
            homepage = conn.execute(
                "SELECT homepage_url, feed_url FROM sources WHERE id = ?",
                (source_id,),
            ).fetchone()
            if homepage is None or not (homepage[0] or homepage[1]):
                continue
            seen_sources.add(source_id)
            proposals.append(
                {
                    "name": row["source_name"],
                    "homepage_url": homepage[0] or homepage[1],
                    "feed_url": homepage[1],
                    "discovery_method": "existing_source",
                    "rationale": (
                        "Already known to Newsroom and produced relevant "
                        "material for this Watch."
                    ),
                    "provenance": {"source_id": source_id},
                }
            )

        # (3) feed_discovery — the syndicated original publisher of relevant
        # material, identified by a canonical URL on a domain Newsroom does not
        # yet have a Source for.
        for row in relevant:
            canonical = str(row["canonical_url"] or "")
            host = (urlparse(canonical).hostname or "").casefold()
            if not host:
                continue
            source_domain = str(row["source_domain"] or "").casefold()
            if not source_domain or host == source_domain or host.endswith(
                f".{source_domain}"
            ):
                continue
            if host in seen_domains:
                continue
            known = conn.execute(
                "SELECT 1 FROM sources WHERE deleted_at IS NULL AND domain = ?",
                (host,),
            ).fetchone()
            if known is not None:
                continue
            seen_domains.add(host)
            proposals.append(
                {
                    "name": host,
                    "homepage_url": f"https://{host}/",
                    "discovery_method": "feed_discovery",
                    "rationale": (
                        f"Original publisher of relevant material delivered by "
                        f"{row['source_name']}."
                    ),
                    "provenance": {
                        "observed_url": canonical,
                        "delivered_by_source_id": row["source_id"],
                    },
                }
            )

        return proposals[:limit]

    def remove_source(self, watch_id: str, source_id: str) -> None:
        """Detach a Source from a Watch.

        The Source itself, its Documents, and any other Watch's Monitor for the
        same Source are untouched; only this Watch's own Monitor is disabled.
        """
        conn = storage.connect(self.db_path)
        try:
            with storage.write_tx(conn):
                self._require_watch(conn, watch_id)
                row = conn.execute(
                    "SELECT monitor_id FROM watch_sources WHERE watch_id = ? AND source_id = ?",
                    (watch_id, source_id),
                ).fetchone()
                if row is None:
                    raise DomainNotFound("watch source not found")
                conn.execute(
                    "UPDATE monitors SET enabled = 0, updated_at = ? WHERE id = ?",
                    (utc_now(), row[0]),
                )
                conn.execute(
                    "DELETE FROM watch_sources WHERE watch_id = ? AND source_id = ?",
                    (watch_id, source_id),
                )
        finally:
            conn.close()


class WatchMaintenanceService:
    """Durable, retryable Watch discovery and vocabulary suggestion runs.

    These are asynchronous and externally influenced, so they use the existing
    JobService rather than a second orchestration framework. Neither run touches
    the Phase 18-23 evidence chain: the worst case is that a Watch gains
    candidate rows a human has not approved.
    """

    def __init__(self, db_path: str | Path, *, watches: WatchService | None = None):
        self.db_path = Path(db_path)
        self.watches = watches or WatchService(
            db_path,
            router=AIRouter(
                local=CapabilityBundle.local_defaults(),
                telemetry=SQLiteTelemetrySink(db_path),
            ),
        )

    def handlers(self) -> dict[str, Any]:
        return {
            WATCH_SOURCE_DISCOVERY_JOB_TYPE: self.handle_discovery,
            WATCH_VOCABULARY_SUGGESTION_JOB_TYPE: self.handle_suggestion,
        }

    @staticmethod
    def _requested_key(job_type: str, watch_id: str, requested_at: str) -> str:
        """Coalesce duplicate dispatch of one requested run, not future runs.

        A permanent per-Watch key would make a Watch undiscoverable forever
        after its first run, so the caller's request instant participates in the
        key (§50).
        """
        return f"{job_type}:{watch_id}:{requested_at}"

    def _enqueue(
        self,
        job_type: str,
        watch_id: str,
        *,
        queue: JobService | None = None,
        requested_at: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        conn = storage.connect(self.db_path)
        try:
            WatchService._require_watch(conn, watch_id)
        finally:
            conn.close()
        requested_at = requested_at or utc_now()
        payload: dict[str, Any] = {
            "watch_id": watch_id,
            "requested_at": requested_at,
        }
        if limit is not None:
            payload["limit"] = int(limit)
        return (queue or JobService(self.db_path)).enqueue(
            job_type,
            payload,
            idempotency_key=self._requested_key(job_type, watch_id, requested_at),
        )

    def enqueue_discovery(self, watch_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._enqueue(WATCH_SOURCE_DISCOVERY_JOB_TYPE, watch_id, **kwargs)

    def enqueue_suggestion(self, watch_id: str, **kwargs: Any) -> dict[str, Any]:
        return self._enqueue(WATCH_VOCABULARY_SUGGESTION_JOB_TYPE, watch_id, **kwargs)

    @staticmethod
    def _watch_id(job: Mapping[str, Any]) -> str:
        payload = job.get("payload")
        if not isinstance(payload, Mapping):
            raise DomainValidation("watch job payload must be an object")
        watch_id = str(payload.get("watch_id") or "").strip()
        if not watch_id:
            raise DomainValidation("watch job payload is missing watch_id")
        return watch_id

    def handle_discovery(self, job: Mapping[str, Any]) -> dict[str, Any]:
        watch_id = self._watch_id(job)
        payload = job["payload"]
        limit = int(payload.get("limit") or MAX_CANDIDATES_PER_RUN)
        try:
            result = self.watches.discover_sources(watch_id, limit=limit)
        except DomainNotFound:
            # The Watch was removed between enqueue and execution; a stale
            # obligation must not retry forever.
            raise
        except DomainValidation:
            raise
        except Exception as exc:  # noqa: BLE001 - recorded, then retried
            self.watches.record_discovery_error(watch_id, str(exc))
            raise RetryableJobFailure(f"source discovery failed: {exc}") from exc
        # Finding nothing is a successful run, not a failure (§86).
        return {
            "watch_id": watch_id,
            "outcome": "completed",
            "candidate_count": result["candidate_count"],
            "methods": result["methods"],
            "external_requests": result["external_requests"],
        }

    def handle_suggestion(self, job: Mapping[str, Any]) -> dict[str, Any]:
        watch_id = self._watch_id(job)
        payload = job["payload"]
        limit = int(payload.get("limit") or 20)
        terms = self.watches.suggest_vocabulary(
            watch_id, limit=limit, work_id=str(job.get("id") or "") or None
        )
        pending = [item for item in terms if item["status"] == "suggested"]
        return {
            "watch_id": watch_id,
            "outcome": "completed",
            "term_count": len(terms),
            "pending_review": len(pending),
        }


__all__ = [
    "DISCOVERY_METHODS",
    "VOCABULARY_KINDS",
    "WATCH_STATUSES",
    "WatchMaintenanceService",
    "WatchService",
]
