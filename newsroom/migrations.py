"""Immutable SQLite migrations for the standalone Newsroom schema."""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from . import storage


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


MIGRATION_0001_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE app_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password_algo TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        disabled_at TEXT
    )
    """,
    """
    CREATE TABLE sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked_at TEXT,
        ip TEXT,
        user_agent TEXT
    )
    """,
    """
    CREATE TABLE categories (
        id TEXT PRIMARY KEY,
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        display_order INTEGER NOT NULL DEFAULT 0,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        priority TEXT NOT NULL DEFAULT 'normal',
        max_stories_per_run INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )
    """,
    """
    CREATE TABLE topics (
        id TEXT PRIMARY KEY,
        category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
        slug TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        priority TEXT NOT NULL DEFAULT 'normal',
        max_queries_per_run INTEGER,
        max_stories_per_run INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT,
        UNIQUE (category_id, slug)
    )
    """,
    """
    CREATE TABLE topic_terms (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        term TEXT NOT NULL,
        term_normalized TEXT NOT NULL,
        term_type TEXT NOT NULL CHECK (term_type IN ('include', 'alias', 'entity', 'exclude')),
        weight REAL NOT NULL DEFAULT 1.0,
        created_at TEXT NOT NULL,
        UNIQUE (topic_id, term_normalized, term_type)
    )
    """,
    """
    CREATE TABLE subjects (
        id TEXT PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        subject_type TEXT NOT NULL CHECK (subject_type IN ('person', 'company', 'product', 'agency', 'law', 'case', 'project', 'technology', 'franchise', 'organization', 'other')),
        description TEXT NOT NULL DEFAULT '',
        canonical_url TEXT,
        canonical_id TEXT,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        priority TEXT NOT NULL DEFAULT 'normal',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )
    """,
    """
    CREATE TABLE subject_aliases (
        id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        alias TEXT NOT NULL,
        alias_normalized TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (subject_id, alias_normalized)
    )
    """,
    """
    CREATE TABLE topic_subjects (
        topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        PRIMARY KEY (topic_id, subject_id)
    )
    """,
    """
    CREATE TABLE sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        domain TEXT,
        homepage_url TEXT,
        feed_url TEXT,
        source_kind TEXT NOT NULL DEFAULT 'web' CHECK (source_kind IN ('web', 'feed', 'api', 'official', 'aggregator', 'unknown')),
        default_quality TEXT NOT NULL DEFAULT 'unknown' CHECK (default_quality IN ('primary', 'high', 'medium', 'low', 'unknown')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )
    """,
    """
    CREATE TABLE documents (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES sources(id),
        canonical_url TEXT NOT NULL,
        canonical_url_hash TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        title_normalized TEXT NOT NULL,
        published_at TEXT,
        first_seen_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE document_versions (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        retrieved_at TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        content_kind TEXT NOT NULL DEFAULT 'metadata' CHECK (content_kind IN ('metadata', 'excerpt', 'full_text')),
        locator_type TEXT,
        locator_value TEXT,
        normalized_json TEXT,
        etag TEXT,
        last_modified TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (document_id, content_hash, retrieved_at)
    )
    """,
    """
    CREATE TABLE stories (
        id TEXT PRIMARY KEY,
        lifecycle TEXT NOT NULL DEFAULT 'developing' CHECK (lifecycle IN ('developing', 'stable', 'resolved', 'archived')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )
    """,
    """
    CREATE TABLE story_revisions (
        id TEXT PRIMARY KEY,
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        revision_number INTEGER NOT NULL,
        headline TEXT NOT NULL,
        headline_normalized TEXT NOT NULL,
        summary TEXT NOT NULL DEFAULT '',
        why_it_matters TEXT NOT NULL DEFAULT '',
        material_change INTEGER NOT NULL DEFAULT 0 CHECK (material_change IN (0, 1)),
        claim_set_hash TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (story_id, revision_number)
    )
    """,
    """
    CREATE TABLE story_topics (
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        match_score INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (story_id, topic_id)
    )
    """,
    """
    CREATE TABLE story_subjects (
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        subject_id TEXT NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        PRIMARY KEY (story_id, subject_id)
    )
    """,
    """
    CREATE TABLE claims (
        id TEXT PRIMARY KEY,
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        proposition TEXT NOT NULL,
        proposition_hash TEXT NOT NULL,
        importance TEXT NOT NULL DEFAULT 'relevant' CHECK (importance IN ('major', 'relevant', 'peripheral')),
        state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'supported', 'partially_supported', 'disputed', 'unsubstantiated', 'superseded')),
        supersedes_claim_id TEXT REFERENCES claims(id),
        created_at TEXT NOT NULL,
        accepted_at TEXT
    )
    """,
    """
    CREATE TABLE claim_state_history (
        id TEXT PRIMARY KEY,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        from_state TEXT,
        to_state TEXT NOT NULL,
        reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE evidence_spans (
        id TEXT PRIMARY KEY,
        document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
        excerpt TEXT NOT NULL,
        locator_type TEXT,
        locator_value TEXT,
        span_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (document_version_id, span_hash)
    )
    """,
    """
    CREATE TABLE claim_evidence (
        id TEXT PRIMARY KEY,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        evidence_span_id TEXT NOT NULL REFERENCES evidence_spans(id) ON DELETE CASCADE,
        relationship TEXT NOT NULL CHECK (relationship IN ('supports', 'contradicts', 'contextualizes')),
        created_at TEXT NOT NULL,
        UNIQUE (claim_id, evidence_span_id, relationship)
    )
    """,
    """
    CREATE TABLE research_questions (
        id TEXT PRIMARY KEY,
        question TEXT NOT NULL,
        origin_type TEXT NOT NULL CHECK (origin_type IN ('story', 'claim', 'subject', 'user', 'monitor')),
        origin_id TEXT,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'abandoned')),
        priority TEXT NOT NULL DEFAULT 'normal',
        search_attempt_budget INTEGER NOT NULL DEFAULT 0,
        last_attempt_at TEXT,
        next_attempt_at TEXT,
        resolution_note TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT
    )
    """,
    """
    CREATE TABLE monitoring_policies (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        allowed_channels TEXT NOT NULL,
        base_cadence_seconds INTEGER NOT NULL,
        min_cadence_seconds INTEGER NOT NULL,
        max_cadence_seconds INTEGER NOT NULL,
        priority TEXT NOT NULL DEFAULT 'normal',
        query_budget INTEGER NOT NULL DEFAULT 0,
        paid_budget_usd REAL NOT NULL DEFAULT 0.0,
        local_model_budget INTEGER NOT NULL DEFAULT 0,
        escalation_rules TEXT,
        backoff_rules TEXT,
        retirement_criteria TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE monitors (
        id TEXT PRIMARY KEY,
        target_type TEXT NOT NULL CHECK (target_type IN ('topic', 'subject', 'story', 'source', 'research_question')),
        target_id TEXT NOT NULL,
        policy_id TEXT NOT NULL REFERENCES monitoring_policies(id),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        next_check_at TEXT,
        last_run_at TEXT,
        last_result TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (target_type, target_id)
    )
    """,
    """
    CREATE TABLE jobs (
        id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled')),
        payload_json TEXT,
        idempotency_key TEXT UNIQUE,
        monitor_id TEXT REFERENCES monitors(id),
        research_question_id TEXT REFERENCES research_questions(id),
        priority INTEGER NOT NULL DEFAULT 0,
        lease_owner TEXT,
        lease_expires_at TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        next_attempt_at TEXT,
        failure_cause TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE job_attempts (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
        attempt_no INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled')),
        error_code TEXT,
        error_detail TEXT,
        UNIQUE (job_id, attempt_no)
    )
    """,
    """
    CREATE TABLE runs (
        id TEXT PRIMARY KEY,
        trigger_type TEXT NOT NULL CHECK (trigger_type IN ('cron', 'manual', 'test')),
        status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'partial', 'failed')),
        started_at TEXT NOT NULL,
        completed_at TEXT,
        summary_json TEXT
    )
    """,
    """
    CREATE TABLE tags (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE story_tags (
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        PRIMARY KEY (story_id, tag_id)
    )
    """,
    """
    CREATE TABLE story_review (
        story_id TEXT PRIMARY KEY REFERENCES stories(id) ON DELETE CASCADE,
        review_status TEXT NOT NULL DEFAULT 'new' CHECK (review_status IN ('new', 'saved', 'dismissed', 'not_useful')),
        not_useful_reason TEXT,
        last_reviewed_revision_id TEXT REFERENCES story_revisions(id),
        saved_at TEXT,
        dismissed_at TEXT,
        not_useful_at TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE feedback_events (
        id TEXT PRIMARY KEY,
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        action TEXT NOT NULL CHECK (action IN ('save', 'dismiss', 'not_useful', 'restore', 'tag_added', 'tag_removed')),
        reason TEXT,
        note TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE provider_usage (
        id TEXT PRIMARY KEY,
        job_id TEXT REFERENCES jobs(id),
        monitor_id TEXT REFERENCES monitors(id),
        research_question_id TEXT REFERENCES research_questions(id),
        capability TEXT NOT NULL,
        provider TEXT,
        request_type TEXT NOT NULL,
        query_units INTEGER,
        token_units INTEGER,
        estimated_cost_usd REAL NOT NULL DEFAULT 0.0,
        latency_ms INTEGER,
        outcome TEXT,
        created_at TEXT NOT NULL
    )
    """,
)

MIGRATION_0001_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0001_STATEMENTS).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class MigrationResult:
    applied_versions: tuple[int, ...]
    current_version: int


def _ensure_ledger(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def migration_status(db_path: Optional[str | Path] = None) -> tuple[int, ...]:
    conn = storage.connect(db_path)
    try:
        _ensure_ledger(conn)
        return tuple(
            row[0]
            for row in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        )
    finally:
        conn.close()


def apply_migrations(db_path: Optional[str | Path] = None) -> MigrationResult:
    conn = storage.connect(db_path)
    applied: list[int] = []
    try:
        with storage.write_tx(conn):
            _ensure_ledger(conn)
            existing = {
                row[0]
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            if 1 not in existing:
                for statement in MIGRATION_0001_STATEMENTS:
                    conn.execute(statement)
                now = utc_now()
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (1, now),
                )
                conn.execute(
                    "INSERT INTO app_meta(key, value) VALUES ('schema_version', '1')"
                )
                conn.execute(
                    "INSERT INTO app_meta(key, value) VALUES ('schema_seeded_at', ?)",
                    (now,),
                )
                applied.append(1)
        current = max((*existing, *applied), default=0)
        return MigrationResult(tuple(applied), current)
    finally:
        conn.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Newsroom database migrations")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("migrate", "status"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--db", required=True, type=Path)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "migrate":
        result = apply_migrations(args.db)
        print(
            f"migrated={','.join(map(str, result.applied_versions)) or 'none'} "
            f"current={result.current_version}"
        )
    else:
        print(",".join(map(str, migration_status(args.db))) or "none")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the CLI
    raise SystemExit(main())
