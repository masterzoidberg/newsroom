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

MIGRATION_0002_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE sessions ADD COLUMN csrf_token_hash TEXT",
    "ALTER TABLE topic_terms ADD COLUMN concept_kind TEXT NOT NULL DEFAULT 'term'",
    """
    CREATE TABLE auth_login_attempts (
        username TEXT PRIMARY KEY,
        failed_count INTEGER NOT NULL DEFAULT 0,
        first_failed_at TEXT NOT NULL,
        locked_until TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE topic_scope_suggestions (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        suggestion_type TEXT NOT NULL CHECK (suggestion_type IN ('term', 'alias', 'acronym', 'related_concept', 'exclude')),
        value TEXT NOT NULL,
        value_normalized TEXT NOT NULL,
        rationale TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL CHECK (source IN ('ai', 'user')),
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT,
        UNIQUE (topic_id, suggestion_type, value_normalized)
    )
    """,
)

MIGRATION_0002_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0002_STATEMENTS).encode("utf-8")
).hexdigest()

MIGRATION_0003_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE story_revision_claims (
        revision_id TEXT NOT NULL REFERENCES story_revisions(id) ON DELETE CASCADE,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
        position INTEGER NOT NULL CHECK (position >= 0),
        PRIMARY KEY (revision_id, claim_id),
        UNIQUE (revision_id, position)
    )
    """,
    "CREATE INDEX story_revision_claims_claim_idx ON story_revision_claims(claim_id)",
    """
    CREATE TRIGGER document_versions_immutable_update
    BEFORE UPDATE ON document_versions
    BEGIN
        SELECT RAISE(ABORT, 'document versions are immutable');
    END
    """,
    """
    CREATE TRIGGER document_versions_immutable_delete
    BEFORE DELETE ON document_versions
    BEGIN
        SELECT RAISE(ABORT, 'document versions are immutable');
    END
    """,
    """
    CREATE TRIGGER evidence_spans_immutable_update
    BEFORE UPDATE ON evidence_spans
    BEGIN
        SELECT RAISE(ABORT, 'evidence spans are immutable');
    END
    """,
    """
    CREATE TRIGGER evidence_spans_immutable_delete
    BEFORE DELETE ON evidence_spans
    BEGIN
        SELECT RAISE(ABORT, 'evidence spans are immutable');
    END
    """,
    """
    CREATE TRIGGER claims_accepted_text_immutable
    BEFORE UPDATE OF proposition, proposition_hash ON claims
    WHEN OLD.accepted_at IS NOT NULL
         AND (NEW.proposition IS NOT OLD.proposition OR NEW.proposition_hash IS NOT OLD.proposition_hash)
    BEGIN
        SELECT RAISE(ABORT, 'accepted claim text is immutable');
    END
    """,
    """
    CREATE TRIGGER claims_immutable_delete
    BEFORE DELETE ON claims
    BEGIN
        SELECT RAISE(ABORT, 'claims are append-only');
    END
    """,
    """
    CREATE TRIGGER claim_state_history_immutable_update
    BEFORE UPDATE ON claim_state_history
    BEGIN
        SELECT RAISE(ABORT, 'claim state history is append-only');
    END
    """,
    """
    CREATE TRIGGER claim_state_history_immutable_delete
    BEFORE DELETE ON claim_state_history
    BEGIN
        SELECT RAISE(ABORT, 'claim state history is append-only');
    END
    """,
    """
    CREATE TRIGGER claim_evidence_immutable_update
    BEFORE UPDATE ON claim_evidence
    BEGIN
        SELECT RAISE(ABORT, 'claim evidence links are append-only');
    END
    """,
    """
    CREATE TRIGGER claim_evidence_immutable_delete
    BEFORE DELETE ON claim_evidence
    BEGIN
        SELECT RAISE(ABORT, 'claim evidence links are append-only');
    END
    """,
    """
    CREATE TRIGGER story_revisions_immutable_update
    BEFORE UPDATE ON story_revisions
    BEGIN
        SELECT RAISE(ABORT, 'story revisions are immutable');
    END
    """,
    """
    CREATE TRIGGER story_revisions_immutable_delete
    BEFORE DELETE ON story_revisions
    BEGIN
        SELECT RAISE(ABORT, 'story revisions are immutable');
    END
    """,
    """
    CREATE TRIGGER story_revision_claims_immutable_update
    BEFORE UPDATE ON story_revision_claims
    BEGIN
        SELECT RAISE(ABORT, 'story revision claim sets are immutable');
    END
    """,
    """
    CREATE TRIGGER story_revision_claims_immutable_delete
    BEFORE DELETE ON story_revision_claims
    BEGIN
        SELECT RAISE(ABORT, 'story revision claim sets are immutable');
    END
    """,
)

MIGRATION_0003_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0003_STATEMENTS).encode("utf-8")
).hexdigest()

MIGRATION_0004_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TRIGGER claims_acceptance_immutable
    BEFORE UPDATE OF accepted_at ON claims
    WHEN OLD.accepted_at IS NOT NULL
         AND NEW.accepted_at IS NOT OLD.accepted_at
    BEGIN
        SELECT RAISE(ABORT, 'claim acceptance is immutable');
    END
    """,
)

MIGRATION_0004_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0004_STATEMENTS).encode("utf-8")
).hexdigest()

MIGRATION_0005_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE acquisition_events (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
        document_version_id TEXT REFERENCES document_versions(id) ON DELETE SET NULL,
        channel TEXT NOT NULL CHECK (channel IN ('rss', 'atom', 'direct_http', 'page')),
        request_url TEXT NOT NULL,
        final_url TEXT,
        outcome TEXT NOT NULL CHECK (outcome IN ('retrieved', 'not_modified', 'unchanged', 'failed', 'blocked')),
        status_code INTEGER,
        content_type TEXT,
        etag TEXT,
        last_modified TEXT,
        raw_content_hash TEXT,
        normalized_content_hash TEXT,
        response_bytes INTEGER,
        error_code TEXT,
        error_message TEXT,
        observed_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX acquisition_events_source_idx ON acquisition_events(source_id, created_at DESC)",
    "CREATE INDEX acquisition_events_document_idx ON acquisition_events(document_id, created_at DESC)",
    """
    CREATE TABLE source_profiles (
        source_id TEXT PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
        source_type TEXT NOT NULL DEFAULT 'unknown',
        coverage_json TEXT NOT NULL DEFAULT '{}',
        acquisition_methods_json TEXT NOT NULL DEFAULT '[]',
        activity_json TEXT NOT NULL DEFAULT '{}',
        failure_json TEXT NOT NULL DEFAULT '{}',
        duplication_json TEXT NOT NULL DEFAULT '{}',
        usefulness_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE source_suggestions (
        id TEXT PRIMARY KEY,
        source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        domain TEXT,
        homepage_url TEXT,
        feed_url TEXT,
        rationale TEXT NOT NULL,
        likely_contribution TEXT NOT NULL,
        limitations TEXT NOT NULL DEFAULT '',
        supported_methods_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT
    )
    """,
    "CREATE INDEX source_suggestions_status_idx ON source_suggestions(status, created_at DESC)",
    """
    CREATE TRIGGER acquisition_events_immutable_update
    BEFORE UPDATE ON acquisition_events
    BEGIN
        SELECT RAISE(ABORT, 'acquisition events are immutable');
    END
    """,
    """
    CREATE TRIGGER acquisition_events_immutable_delete
    BEFORE DELETE ON acquisition_events
    BEGIN
        SELECT RAISE(ABORT, 'acquisition events are immutable');
    END
    """,
)

MIGRATION_0005_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0005_STATEMENTS).encode("utf-8")
).hexdigest()

MIGRATION_0006_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE jobs ADD COLUMN run_id TEXT REFERENCES runs(id)",
    "ALTER TABLE jobs ADD COLUMN cancel_requested_at TEXT",
    "CREATE INDEX jobs_run_idx ON jobs(run_id, created_at DESC)",
    """
    CREATE TABLE budget_limits (
        id TEXT PRIMARY KEY,
        scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'policy', 'job', 'research_question')),
        scope_id TEXT NOT NULL DEFAULT '',
        period TEXT NOT NULL CHECK (period IN ('daily', 'monthly', 'lifetime')),
        cap_type TEXT NOT NULL CHECK (cap_type IN ('acquisition_units', 'local_model_units', 'paid_requests', 'usd')),
        cap_value REAL NOT NULL CHECK (cap_value >= 0),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (scope_type, scope_id, period, cap_type)
    )
    """,
    """
    CREATE TABLE budget_reservations (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
        acquisition_units INTEGER NOT NULL DEFAULT 0 CHECK (acquisition_units >= 0),
        local_model_units INTEGER NOT NULL DEFAULT 0 CHECK (local_model_units >= 0),
        paid_requests INTEGER NOT NULL DEFAULT 0 CHECK (paid_requests >= 0),
        estimated_cost_usd REAL NOT NULL DEFAULT 0.0 CHECK (estimated_cost_usd >= 0),
        status TEXT NOT NULL CHECK (status IN ('reserved', 'released')),
        reserved_at TEXT NOT NULL,
        released_at TEXT
    )
    """,
    "CREATE INDEX budget_reservations_status_idx ON budget_reservations(status, reserved_at)",
    """
    CREATE TABLE scheduler_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_tick_at TEXT,
        updated_at TEXT NOT NULL
    )
    """,
)

MIGRATION_0006_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0006_STATEMENTS).encode("utf-8")
).hexdigest()

MIGRATION_0007_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE monitor_scope_history (
        id TEXT PRIMARY KEY,
        monitor_id TEXT NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
        version INTEGER NOT NULL,
        scope_json TEXT NOT NULL,
        change_type TEXT NOT NULL CHECK (change_type IN ('initial', 'approved', 'manual')),
        changed_by TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (monitor_id, version)
    )
    """,
    "CREATE INDEX monitor_scope_history_monitor_idx ON monitor_scope_history(monitor_id, version DESC)",
    """
    CREATE TABLE monitor_activity (
        id TEXT PRIMARY KEY,
        monitor_id TEXT NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
        outcome TEXT NOT NULL CHECK (outcome IN ('no_change', 'relevant_change', 'partial', 'error')),
        new_items INTEGER NOT NULL DEFAULT 0 CHECK (new_items >= 0),
        changed_items INTEGER NOT NULL DEFAULT 0 CHECK (changed_items >= 0),
        relevant_items INTEGER NOT NULL DEFAULT 0 CHECK (relevant_items >= 0),
        error_code TEXT,
        observed_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX monitor_activity_monitor_idx ON monitor_activity(monitor_id, observed_at DESC, id DESC)",
    """
    CREATE TABLE vocabulary_suggestions (
        id TEXT PRIMARY KEY,
        topic_id TEXT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        suggestion_type TEXT NOT NULL CHECK (suggestion_type IN ('term', 'synonym', 'acronym', 'alias', 'broader', 'narrower', 'related_concept', 'ambiguity', 'exclude')),
        value TEXT NOT NULL,
        value_normalized TEXT NOT NULL,
        rationale TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL CHECK (source IN ('ai', 'user')),
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT,
        UNIQUE (topic_id, suggestion_type, value_normalized)
    )
    """,
    "CREATE INDEX vocabulary_suggestions_topic_idx ON vocabulary_suggestions(topic_id, status, created_at DESC)",
    """
    CREATE TRIGGER monitor_activity_immutable_update
    BEFORE UPDATE ON monitor_activity
    BEGIN
        SELECT RAISE(ABORT, 'monitor activity is immutable');
    END
    """,
    """
    CREATE TRIGGER monitor_activity_immutable_delete
    BEFORE DELETE ON monitor_activity
    BEGIN
        SELECT RAISE(ABORT, 'monitor activity is immutable');
    END
    """,
    """
    CREATE TRIGGER monitor_scope_history_immutable_update
    BEFORE UPDATE ON monitor_scope_history
    BEGIN
        SELECT RAISE(ABORT, 'monitor scope history is immutable');
    END
    """,
    """
    CREATE TRIGGER monitor_scope_history_immutable_delete
    BEFORE DELETE ON monitor_scope_history
    BEGIN
        SELECT RAISE(ABORT, 'monitor scope history is immutable');
    END
    """,
)

MIGRATION_0007_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0007_STATEMENTS).encode("utf-8")
).hexdigest()


MIGRATION_0008_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE story_documents (
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
        event_key TEXT,
        entities_json TEXT NOT NULL DEFAULT '[]',
        locations_json TEXT NOT NULL DEFAULT '[]',
        linked_at TEXT NOT NULL,
        PRIMARY KEY (story_id, document_id)
    )
    """,
    "CREATE INDEX story_documents_document_idx ON story_documents(document_id)",
    """
    CREATE TABLE document_lineage (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        parent_document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
        relationship TEXT NOT NULL CHECK (relationship IN (
            'cites', 'syndicated_from', 'wire_propagation',
            'rewritten_from', 'common_primary_document'
        )),
        confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
        rationale TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE (document_id, parent_document_id, relationship),
        CHECK (document_id <> parent_document_id)
    )
    """,
    "CREATE INDEX document_lineage_document_idx ON document_lineage(document_id, relationship)",
    "CREATE INDEX document_lineage_parent_idx ON document_lineage(parent_document_id, relationship)",
    """
    CREATE TABLE story_evolution_events (
        id TEXT PRIMARY KEY,
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
        update_class TEXT NOT NULL CHECK (update_class IN (
            'new_story', 'duplicate', 'corroboration', 'contradiction',
            'qualification', 'correction', 'material_update'
        )),
        material_change INTEGER NOT NULL DEFAULT 0 CHECK (material_change IN (0, 1)),
        decision_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX story_evolution_events_story_idx ON story_evolution_events(story_id, created_at, id)",
    "CREATE INDEX story_evolution_events_document_idx ON story_evolution_events(document_id, created_at, id)",
    """
    CREATE TABLE story_revision_documents (
        revision_id TEXT NOT NULL REFERENCES story_revisions(id) ON DELETE CASCADE,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
        role TEXT NOT NULL DEFAULT 'trigger' CHECK (role IN ('trigger', 'provenance')),
        created_at TEXT NOT NULL,
        PRIMARY KEY (revision_id, document_id)
    )
    """,
    "CREATE INDEX story_revision_documents_document_idx ON story_revision_documents(document_id)",
    """
    CREATE TRIGGER story_documents_immutable_update
    BEFORE UPDATE ON story_documents
    BEGIN
        SELECT RAISE(ABORT, 'story document links are append-only');
    END
    """,
    """
    CREATE TRIGGER story_documents_immutable_delete
    BEFORE DELETE ON story_documents
    BEGIN
        SELECT RAISE(ABORT, 'story document links are append-only');
    END
    """,
    """
    CREATE TRIGGER document_lineage_immutable_update
    BEFORE UPDATE ON document_lineage
    BEGIN
        SELECT RAISE(ABORT, 'document lineage is append-only');
    END
    """,
    """
    CREATE TRIGGER document_lineage_immutable_delete
    BEFORE DELETE ON document_lineage
    BEGIN
        SELECT RAISE(ABORT, 'document lineage is append-only');
    END
    """,
    """
    CREATE TRIGGER story_evolution_events_immutable_update
    BEFORE UPDATE ON story_evolution_events
    BEGIN
        SELECT RAISE(ABORT, 'story evolution events are append-only');
    END
    """,
    """
    CREATE TRIGGER story_evolution_events_immutable_delete
    BEFORE DELETE ON story_evolution_events
    BEGIN
        SELECT RAISE(ABORT, 'story evolution events are append-only');
    END
    """,
    """
    CREATE TRIGGER story_revision_documents_immutable_update
    BEFORE UPDATE ON story_revision_documents
    BEGIN
        SELECT RAISE(ABORT, 'story revision document links are append-only');
    END
    """,
    """
    CREATE TRIGGER story_revision_documents_immutable_delete
    BEFORE DELETE ON story_revision_documents
    BEGIN
        SELECT RAISE(ABORT, 'story revision document links are append-only');
    END
    """,
)

MIGRATION_0008_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0008_STATEMENTS).encode("utf-8")
).hexdigest()


MIGRATION_0009_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE research_questions ADD COLUMN query_budget INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE research_questions ADD COLUMN local_model_budget INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE research_questions ADD COLUMN paid_budget_usd REAL NOT NULL DEFAULT 0.0",
    """
    CREATE TABLE research_question_history (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        from_status TEXT CHECK (from_status IS NULL OR from_status IN ('open', 'resolved', 'abandoned')),
        to_status TEXT NOT NULL CHECK (to_status IN ('open', 'resolved', 'abandoned')),
        reason TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT 'system',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX research_question_history_question_idx ON research_question_history(question_id, created_at, id)",
    """
    CREATE TABLE research_question_claims (
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
        relationship TEXT NOT NULL CHECK (relationship IN ('supports', 'contradicts', 'contextualizes', 'resolves')),
        created_at TEXT NOT NULL,
        PRIMARY KEY (question_id, claim_id, relationship)
    )
    """,
    "CREATE INDEX research_question_claims_claim_idx ON research_question_claims(claim_id, created_at)",
    """
    CREATE TABLE research_question_evidence (
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        evidence_span_id TEXT NOT NULL REFERENCES evidence_spans(id) ON DELETE RESTRICT,
        relationship TEXT NOT NULL CHECK (relationship IN ('supports', 'contradicts', 'contextualizes', 'resolves')),
        created_at TEXT NOT NULL,
        PRIMARY KEY (question_id, evidence_span_id, relationship)
    )
    """,
    "CREATE INDEX research_question_evidence_span_idx ON research_question_evidence(evidence_span_id, created_at)",
    """
    CREATE TABLE research_question_attempts (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
        attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
        mode TEXT NOT NULL CHECK (mode IN ('manual', 'policy')),
        status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned', 'running', 'succeeded', 'partial', 'failed', 'cancelled')),
        query_units INTEGER NOT NULL DEFAULT 0 CHECK (query_units >= 0),
        local_model_units INTEGER NOT NULL DEFAULT 0 CHECK (local_model_units >= 0),
        estimated_cost_usd REAL NOT NULL DEFAULT 0.0 CHECK (estimated_cost_usd >= 0.0),
        query TEXT,
        outcome_note TEXT,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (question_id, attempt_no)
    )
    """,
    "CREATE INDEX research_question_attempts_question_idx ON research_question_attempts(question_id, attempt_no)",
    """
    CREATE TABLE research_question_notes (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        note_type TEXT NOT NULL CHECK (note_type IN ('note', 'hypothesis')),
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX research_question_notes_question_idx ON research_question_notes(question_id, created_at, id)",
    """
    CREATE TABLE research_gap_suggestions (
        id TEXT PRIMARY KEY,
        question_id TEXT REFERENCES research_questions(id) ON DELETE SET NULL,
        origin_type TEXT NOT NULL CHECK (origin_type IN ('story', 'claim')),
        origin_id TEXT NOT NULL,
        gap_type TEXT NOT NULL CHECK (gap_type IN (
            'missing_claims', 'pending_claim', 'unsubstantiated_claim',
            'missing_support', 'contradiction', 'weak_independence',
            'missing_primary_source'
        )),
        suggestion_type TEXT NOT NULL CHECK (suggestion_type IN ('question', 'search', 'source')),
        suggestion TEXT NOT NULL,
        rationale TEXT NOT NULL,
        expected_information_value REAL NOT NULL CHECK (expected_information_value >= 0.0 AND expected_information_value <= 1.0),
        payload_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'converted')),
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT
    )
    """,
    "CREATE INDEX research_gap_suggestions_origin_idx ON research_gap_suggestions(origin_type, origin_id, status, created_at)",
    "CREATE INDEX research_gap_suggestions_question_idx ON research_gap_suggestions(question_id, status, created_at)",
    """
    CREATE TRIGGER research_question_history_immutable_update
    BEFORE UPDATE ON research_question_history
    BEGIN
        SELECT RAISE(ABORT, 'research question history is append-only');
    END
    """,
    """
    CREATE TRIGGER research_question_history_immutable_delete
    BEFORE DELETE ON research_question_history
    BEGIN
        SELECT RAISE(ABORT, 'research question history is append-only');
    END
    """,
    """
    CREATE TRIGGER research_question_claims_immutable_update
    BEFORE UPDATE ON research_question_claims
    BEGIN
        SELECT RAISE(ABORT, 'research question claim links are append-only');
    END
    """,
    """
    CREATE TRIGGER research_question_claims_immutable_delete
    BEFORE DELETE ON research_question_claims
    BEGIN
        SELECT RAISE(ABORT, 'research question claim links are append-only');
    END
    """,
    """
    CREATE TRIGGER research_question_evidence_immutable_update
    BEFORE UPDATE ON research_question_evidence
    BEGIN
        SELECT RAISE(ABORT, 'research question evidence links are append-only');
    END
    """,
    """
    CREATE TRIGGER research_question_evidence_immutable_delete
    BEFORE DELETE ON research_question_evidence
    BEGIN
        SELECT RAISE(ABORT, 'research question evidence links are append-only');
    END
    """,
    """
    CREATE TRIGGER research_question_notes_immutable_update
    BEFORE UPDATE ON research_question_notes
    BEGIN
        SELECT RAISE(ABORT, 'research question notes are append-only');
    END
    """,
    """
    CREATE TRIGGER research_question_notes_immutable_delete
    BEFORE DELETE ON research_question_notes
    BEGIN
        SELECT RAISE(ABORT, 'research question notes are append-only');
    END
    """,
)

MIGRATION_0009_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0009_STATEMENTS).encode("utf-8")
).hexdigest()


MIGRATION_0010_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE living_reports (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        target_type TEXT NOT NULL CHECK (target_type IN ('monitor', 'story', 'topic', 'subject', 'source', 'research_question')),
        target_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
        timezone_name TEXT NOT NULL DEFAULT 'UTC',
        current_revision_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (target_type, target_id)
    )
    """,
    "CREATE INDEX living_reports_target_idx ON living_reports(target_type, target_id, status)",
    """
    CREATE TABLE report_revisions (
        id TEXT PRIMARY KEY,
        report_id TEXT NOT NULL REFERENCES living_reports(id) ON DELETE CASCADE,
        revision_number INTEGER NOT NULL CHECK (revision_number > 0),
        claim_set_hash TEXT NOT NULL,
        material_change INTEGER NOT NULL DEFAULT 0 CHECK (material_change IN (0, 1)),
        current_status TEXT NOT NULL,
        what_changed TEXT NOT NULL DEFAULT '',
        sections_json TEXT NOT NULL DEFAULT '{}',
        propositions_json TEXT NOT NULL DEFAULT '[]',
        audit_json TEXT NOT NULL DEFAULT '{}',
        generated_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE (report_id, revision_number)
    )
    """,
    "CREATE INDEX report_revisions_report_idx ON report_revisions(report_id, revision_number DESC)",
    """
    CREATE TABLE report_revision_claims (
        revision_id TEXT NOT NULL REFERENCES report_revisions(id) ON DELETE CASCADE,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
        position INTEGER NOT NULL CHECK (position >= 0),
        created_at TEXT NOT NULL,
        PRIMARY KEY (revision_id, claim_id),
        UNIQUE (revision_id, position)
    )
    """,
    "CREATE INDEX report_revision_claims_claim_idx ON report_revision_claims(claim_id)",
    """
    CREATE TABLE report_revision_causes (
        id TEXT PRIMARY KEY,
        revision_id TEXT NOT NULL REFERENCES report_revisions(id) ON DELETE CASCADE,
        cause_type TEXT NOT NULL CHECK (cause_type IN ('new_primary_evidence', 'contradiction', 'correction', 'corroboration', 'material_update')),
        cause_id TEXT NOT NULL,
        story_id TEXT REFERENCES stories(id) ON DELETE SET NULL,
        claim_id TEXT REFERENCES claims(id) ON DELETE SET NULL,
        evidence_span_id TEXT REFERENCES evidence_spans(id) ON DELETE SET NULL,
        document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
        rationale TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX report_revision_causes_revision_idx ON report_revision_causes(revision_id, cause_type, created_at)",
    "CREATE INDEX report_revision_causes_evidence_idx ON report_revision_causes(evidence_span_id)",
    """
    CREATE TABLE briefings (
        id TEXT PRIMARY KEY,
        period TEXT NOT NULL CHECK (period IN ('daily', 'weekly')),
        timezone_name TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('draft', 'published')),
        created_at TEXT NOT NULL,
        UNIQUE (period, timezone_name, period_start, period_end)
    )
    """,
    """
    CREATE TABLE briefing_monitors (
        briefing_id TEXT NOT NULL REFERENCES briefings(id) ON DELETE CASCADE,
        monitor_id TEXT NOT NULL REFERENCES monitors(id) ON DELETE RESTRICT,
        created_at TEXT NOT NULL,
        PRIMARY KEY (briefing_id, monitor_id)
    )
    """,
    """
    CREATE TABLE briefing_items (
        id TEXT PRIMARY KEY,
        briefing_id TEXT NOT NULL REFERENCES briefings(id) ON DELETE CASCADE,
        report_id TEXT NOT NULL REFERENCES living_reports(id) ON DELETE RESTRICT,
        report_revision_id TEXT NOT NULL REFERENCES report_revisions(id) ON DELETE RESTRICT,
        story_id TEXT REFERENCES stories(id) ON DELETE SET NULL,
        rank INTEGER NOT NULL CHECK (rank > 0),
        importance_score REAL NOT NULL CHECK (importance_score >= 0.0 AND importance_score <= 1.0),
        reason TEXT NOT NULL DEFAULT '',
        claim_ids_json TEXT NOT NULL DEFAULT '[]',
        evidence_span_ids_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        UNIQUE (briefing_id, report_revision_id, story_id)
    )
    """,
    "CREATE INDEX briefing_items_briefing_idx ON briefing_items(briefing_id, rank, id)",
    """
    CREATE TABLE alert_rules (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        target_type TEXT NOT NULL CHECK (target_type IN ('all', 'report', 'monitor', 'story')),
        target_id TEXT,
        event_types_json TEXT NOT NULL DEFAULT '[]',
        min_importance REAL NOT NULL DEFAULT 0.0 CHECK (min_importance >= 0.0 AND min_importance <= 1.0),
        browser_enabled INTEGER NOT NULL DEFAULT 0 CHECK (browser_enabled IN (0, 1)),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        dedupe_window_seconds INTEGER NOT NULL DEFAULT 86400 CHECK (dedupe_window_seconds >= 0),
        timezone_name TEXT NOT NULL DEFAULT 'UTC',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX alert_rules_target_idx ON alert_rules(target_type, target_id, enabled)",
    """
    CREATE TABLE alerts (
        id TEXT PRIMARY KEY,
        rule_id TEXT NOT NULL REFERENCES alert_rules(id) ON DELETE RESTRICT,
        report_id TEXT REFERENCES living_reports(id) ON DELETE SET NULL,
        report_revision_id TEXT REFERENCES report_revisions(id) ON DELETE SET NULL,
        story_id TEXT REFERENCES stories(id) ON DELETE SET NULL,
        event_type TEXT NOT NULL CHECK (event_type IN ('new_primary_evidence', 'contradiction', 'correction', 'corroboration', 'material_update')),
        title TEXT NOT NULL,
        body TEXT NOT NULL,
        importance_score REAL NOT NULL CHECK (importance_score >= 0.0 AND importance_score <= 1.0),
        dedupe_key TEXT NOT NULL UNIQUE,
        cause_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'unread' CHECK (status IN ('unread', 'acknowledged')),
        created_at TEXT NOT NULL,
        acknowledged_at TEXT,
        acknowledged_by TEXT
    )
    """,
    "CREATE INDEX alerts_status_idx ON alerts(status, created_at DESC, id)",
    "CREATE INDEX alerts_report_idx ON alerts(report_id, created_at DESC, id)",
    """
    CREATE TABLE alert_deliveries (
        id TEXT PRIMARY KEY,
        alert_id TEXT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
        channel TEXT NOT NULL CHECK (channel IN ('in_app', 'browser')),
        status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed', 'denied', 'offline', 'skipped')),
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
        error_detail TEXT,
        delivered_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (alert_id, channel)
    )
    """,
    "CREATE INDEX alert_deliveries_status_idx ON alert_deliveries(status, updated_at, id)",
    """
    CREATE TABLE notification_preferences (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        browser_enabled INTEGER NOT NULL DEFAULT 0 CHECK (browser_enabled IN (0, 1)),
        permission_state TEXT NOT NULL DEFAULT 'default' CHECK (permission_state IN ('default', 'granted', 'denied')),
        online INTEGER NOT NULL DEFAULT 1 CHECK (online IN (0, 1)),
        updated_at TEXT NOT NULL
    )
    """,
    "INSERT INTO notification_preferences(id, updated_at) VALUES (1, '1970-01-01T00:00:00Z')",
    """
    CREATE TRIGGER report_revisions_immutable_update
    BEFORE UPDATE ON report_revisions
    BEGIN
        SELECT RAISE(ABORT, 'report revisions are immutable');
    END
    """,
    """
    CREATE TRIGGER report_revisions_immutable_delete
    BEFORE DELETE ON report_revisions
    BEGIN
        SELECT RAISE(ABORT, 'report revisions are immutable');
    END
    """,
    """
    CREATE TRIGGER report_revision_claims_immutable_update
    BEFORE UPDATE ON report_revision_claims
    BEGIN
        SELECT RAISE(ABORT, 'report revision claim links are immutable');
    END
    """,
    """
    CREATE TRIGGER report_revision_claims_immutable_delete
    BEFORE DELETE ON report_revision_claims
    BEGIN
        SELECT RAISE(ABORT, 'report revision claim links are immutable');
    END
    """,
    """
    CREATE TRIGGER report_revision_causes_immutable_update
    BEFORE UPDATE ON report_revision_causes
    BEGIN
        SELECT RAISE(ABORT, 'report revision causes are immutable');
    END
    """,
    """
    CREATE TRIGGER report_revision_causes_immutable_delete
    BEFORE DELETE ON report_revision_causes
    BEGIN
        SELECT RAISE(ABORT, 'report revision causes are immutable');
    END
    """,
)

MIGRATION_0010_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0010_STATEMENTS).encode("utf-8")
).hexdigest()


MIGRATION_0011_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE tags ADD COLUMN namespace TEXT NOT NULL DEFAULT 'user'",
    "ALTER TABLE tags ADD COLUMN tag_type TEXT NOT NULL DEFAULT 'user' CHECK (tag_type IN ('user', 'smart'))",
    "CREATE INDEX tags_namespace_idx ON tags(namespace, tag_type, normalized_name, id)",
    """
    CREATE TABLE notes (
        id TEXT PRIMARY KEY,
        object_type TEXT NOT NULL CHECK (object_type IN ('story', 'subject', 'document', 'claim', 'monitor', 'research_question')),
        object_id TEXT NOT NULL,
        note_type TEXT NOT NULL CHECK (note_type IN ('note', 'hypothesis', 'context')),
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX notes_object_idx ON notes(object_type, object_id, created_at DESC, id DESC)",
    """
    CREATE TABLE search_records (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL CHECK (entity_type IN ('monitor', 'source', 'document', 'story', 'subject', 'claim', 'evidence', 'tag', 'question', 'note')),
        entity_id TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        source_id TEXT,
        story_id TEXT,
        subject_id TEXT,
        monitor_id TEXT,
        question_id TEXT,
        tag_id TEXT,
        document_id TEXT,
        state TEXT,
        lifecycle TEXT,
        created_at TEXT NOT NULL,
        UNIQUE (entity_type, entity_id)
    )
    """,
    "CREATE INDEX search_records_type_idx ON search_records(entity_type, entity_id)",
    "CREATE INDEX search_records_filter_idx ON search_records(source_id, story_id, subject_id, monitor_id, question_id, tag_id, document_id)",
    """
    CREATE VIRTUAL TABLE search_fts USING fts5(
        entity_type UNINDEXED,
        entity_id UNINDEXED,
        title,
        body,
        tokenize = 'unicode61'
    )
    """,
)

MIGRATION_0011_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0011_STATEMENTS).encode("utf-8")
).hexdigest()


_SEARCH_DIRTY_TABLES = (
    "monitors", "monitoring_policies", "sources", "documents", "document_versions",
    "evidence_spans", "stories", "story_revisions", "story_subjects", "story_tags",
    "story_documents", "story_evolution_events", "subjects", "subject_aliases", "claims",
    "claim_evidence", "claim_state_history", "research_questions", "research_question_notes",
    "notes", "tags", "topics", "topic_terms", "topic_subjects",
)
MIGRATION_0012_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE search_index_meta (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        dirty INTEGER NOT NULL DEFAULT 1 CHECK (dirty IN (0, 1)),
        updated_at TEXT NOT NULL
    )
    """,
    "INSERT INTO search_index_meta(id, updated_at) VALUES (1, '1970-01-01T00:00:00Z')",
    *tuple(
        f"""
        CREATE TRIGGER search_dirty_{table}_{operation}
        AFTER {operation.upper()} ON {table}
        BEGIN
            UPDATE search_index_meta SET dirty = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1;
        END
        """
        for table in _SEARCH_DIRTY_TABLES
        for operation in ("insert", "update", "delete")
    ),
)

MIGRATION_0012_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0012_STATEMENTS).encode("utf-8")
).hexdigest()


MIGRATION_0013_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE ask_conversations (
        id TEXT PRIMARY KEY,
        scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'story', 'claim', 'evidence', 'document', 'report', 'question', 'research_question', 'subject', 'monitor', 'note')),
        scope_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK ((scope_type = 'global' AND scope_id IS NULL) OR (scope_type <> 'global' AND scope_id IS NOT NULL))
    )
    """,
    "CREATE INDEX ask_conversations_scope_idx ON ask_conversations(scope_type, scope_id, updated_at DESC, id DESC)",
    """
    CREATE TABLE ask_runs (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES ask_conversations(id) ON DELETE CASCADE,
        turn_number INTEGER NOT NULL,
        prompt_hash TEXT NOT NULL,
        prompt_length INTEGER NOT NULL CHECK (prompt_length > 0),
        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'answered', 'qualified', 'refused', 'cancelled', 'failed')),
        answer_json TEXT,
        retrieval_json TEXT,
        citations_json TEXT,
        refusal_code TEXT,
        context_units INTEGER NOT NULL DEFAULT 0 CHECK (context_units >= 0),
        provider_route TEXT NOT NULL DEFAULT 'local_deterministic',
        estimated_cost_usd REAL NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
        created_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE (conversation_id, turn_number)
    )
    """,
    "CREATE INDEX ask_runs_conversation_idx ON ask_runs(conversation_id, turn_number DESC, id DESC)",
    "CREATE INDEX ask_runs_status_idx ON ask_runs(status, created_at DESC, id DESC)",
)

MIGRATION_0013_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0013_STATEMENTS).encode("utf-8")
).hexdigest()


# 0014: widen monitor_activity.outcome with a neutral acquisition-level
# 'changed' outcome. 'changed' means content changed but semantic relevance is
# not yet evaluated; it is distinct from 'relevant_change' (confirmed relevance)
# and 'no_change' (truthful unchanged acquisition). SQLite cannot ALTER a CHECK
# constraint, so the table is rebuilt inside one transaction: immutability
# triggers are dropped, the table is renamed, recreated with the widened CHECK,
# copied verbatim, and the triggers plus index recreated. Existing rows and the
# FK on monitors(id) survive because the column layout is unchanged.
MIGRATION_0014_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER monitor_activity_immutable_update",
    "DROP TRIGGER monitor_activity_immutable_delete",
    "ALTER TABLE monitor_activity RENAME TO monitor_activity_old",
    """
    CREATE TABLE monitor_activity (
        id TEXT PRIMARY KEY,
        monitor_id TEXT NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
        outcome TEXT NOT NULL CHECK (outcome IN ('no_change', 'changed', 'relevant_change', 'partial', 'error')),
        new_items INTEGER NOT NULL DEFAULT 0 CHECK (new_items >= 0),
        changed_items INTEGER NOT NULL DEFAULT 0 CHECK (changed_items >= 0),
        relevant_items INTEGER NOT NULL DEFAULT 0 CHECK (relevant_items >= 0),
        error_code TEXT,
        observed_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    INSERT INTO monitor_activity
        (id, monitor_id, outcome, new_items, changed_items, relevant_items,
         error_code, observed_at, created_at)
    SELECT id, monitor_id, outcome, new_items, changed_items, relevant_items,
           error_code, observed_at, created_at
    FROM monitor_activity_old
    """,
    "DROP TABLE monitor_activity_old",
    "CREATE INDEX monitor_activity_monitor_idx ON monitor_activity(monitor_id, observed_at DESC, id DESC)",
    """
    CREATE TRIGGER monitor_activity_immutable_update
    BEFORE UPDATE ON monitor_activity
    BEGIN
        SELECT RAISE(ABORT, 'monitor activity is immutable');
    END
    """,
    """
    CREATE TRIGGER monitor_activity_immutable_delete
    BEFORE DELETE ON monitor_activity
    BEGIN
        SELECT RAISE(ABORT, 'monitor activity is immutable');
    END
    """,
)

MIGRATION_0014_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0014_STATEMENTS).encode("utf-8")
).hexdigest()

# Phase 18 — durable normalized content artifact. Acquired normalized content
# (visible text for HTML/text pages, normalized feed-entry metadata, or the
# bounded fallback text of non-extractable responses) is persisted once in a
# content-addressed, immutable artifact table. document_versions gains a
# nullable artifact_id reference: pre-Phase-18 historical versions legitimately
# have no artifact (NULL), and no content is manufactured for them. FK
# enforcement protects against dangling references; a BEFORE UPDATE trigger
# makes stored content immutable while leaving metadata columns (e.g. future
# retention eligibility) open; referenced artifacts cannot be deleted because
# the document_versions FK has RESTRICT semantics.
MIGRATION_0015_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE content_artifacts (
        id TEXT PRIMARY KEY,
        normalized_content_hash TEXT NOT NULL UNIQUE,
        content_kind TEXT NOT NULL CHECK (content_kind IN ('visible_text', 'feed_metadata', 'fallback_text')),
        norm_version TEXT NOT NULL,
        normalized_text TEXT NOT NULL,
        text_length INTEGER NOT NULL CHECK (text_length >= 0),
        retention_eligible INTEGER NOT NULL DEFAULT 1 CHECK (retention_eligible IN (0, 1)),
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER content_artifacts_immutable_content
    BEFORE UPDATE OF normalized_content_hash, content_kind, norm_version, normalized_text, text_length ON content_artifacts
    BEGIN
        SELECT RAISE(ABORT, 'content artifact content is immutable');
    END
    """,
    "ALTER TABLE document_versions ADD COLUMN artifact_id TEXT REFERENCES content_artifacts(id)",
    "CREATE INDEX document_versions_artifact_idx ON document_versions(artifact_id)",
)

MIGRATION_0015_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0015_STATEMENTS).encode("utf-8")
).hexdigest()

# Phase 19 — durable changed-DocumentVersion processing obligations. The jobs
# table gains the canonical ownership column for `document_version_process`
# jobs (document_version_id, FK-guarded so a processing obligation can never
# point at a missing version) plus an index over (document_version_id, status)
# so active-work coalescing and obligation queries stay cheap. A nullable
# result_json column durably persists the deterministic processing result
# produced by the worker handler (job outcomes previously only reached
# in-memory completion-hook context). All three additions are additive and
# schema-15 data is preserved unchanged; the columns are NULL for every
# historical job row.
MIGRATION_0016_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE jobs ADD COLUMN document_version_id TEXT REFERENCES document_versions(id)",
    "ALTER TABLE jobs ADD COLUMN result_json TEXT",
    "CREATE INDEX jobs_document_version_idx ON jobs(document_version_id, status)",
)

MIGRATION_0016_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0016_STATEMENTS).encode("utf-8")
).hexdigest()

# Phase 20 — semantic scope and automatic relevance. Two additions:
#
# 1. monitors gains the explicit, OPTIONAL approved information-need
#    association (need_type/need_id referencing a Topic, Subject, Story, or
#    Research Question). A Source Monitor with a need is a semantic monitor
#    whose approved scope comes from that need; a Source Monitor without one
#    is explicitly classified acquisition-only. History rows are untouched: the
#    columns are NULL for every pre-Phase-20 monitor, which remains a truthful
#    acquisition-only classification.
#
# 2. document_version_relevance durably records each deterministic relevance
#    decision for a DocumentVersion against one approved scope snapshot. The
#    row pins the originating monitor and the monitor_scope_history version
#    used, copies the full approved snapshot (scope_json) so the decision is
#    reproducible even if the monitor's mutable scope later changes, and
#    keeps the matched terms/stage/score/reason/provenance of the decision.
#    UNIQUE(document_version_id, monitor_id, scope_version) is the canonical
#    relevance identity: retries, lease recovery, and explicit reruns all
#    reference one decision rather than duplicating or overwriting history.
#    Article text is never stored here.
MIGRATION_0017_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE monitors ADD COLUMN need_type TEXT CHECK (need_type IS NULL OR need_type IN ('topic', 'subject', 'story', 'research_question'))",
    "ALTER TABLE monitors ADD COLUMN need_id TEXT",
    """
    CREATE TABLE document_version_relevance (
        id TEXT PRIMARY KEY,
        document_version_id TEXT NOT NULL REFERENCES document_versions(id),
        monitor_id TEXT NOT NULL REFERENCES monitors(id),
        job_id TEXT REFERENCES jobs(id),
        scope_version INTEGER NOT NULL CHECK (scope_version > 0),
        scope_json TEXT NOT NULL,
        relevant INTEGER NOT NULL CHECK (relevant IN (0, 1)),
        stage TEXT NOT NULL,
        score REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
        matched_terms_json TEXT NOT NULL DEFAULT '[]',
        reason TEXT NOT NULL DEFAULT '',
        algorithm TEXT NOT NULL DEFAULT 'deterministic_relevance_cascade_v1',
        paid_used INTEGER NOT NULL DEFAULT 0 CHECK (paid_used IN (0, 1)),
        created_at TEXT NOT NULL,
        UNIQUE (document_version_id, monitor_id, scope_version)
    )
    """,
    "CREATE INDEX document_version_relevance_version_idx ON document_version_relevance(document_version_id, monitor_id)",
    "CREATE INDEX document_version_relevance_monitor_idx ON document_version_relevance(monitor_id, scope_version)",
)

MIGRATION_0017_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0017_STATEMENTS).encode("utf-8")
).hexdigest()


# Phase 21 — durable structured article analysis. Relevant DocumentVersions
# (Phase 20 durable relevance=true decisions) get a validated structured
# ArticleAnalysis persisted here. The row carries full provenance to
# reproduce/audit the analysis without duplicating the article body:
# document_version reference, the relevance decision and its pinned approved
# scope version, the immutable Phase 18 content artifact reference and its
# normalized hash, and the exact schema/prompt/provider/model identity. The
# result is a validated structured JSON payload (schema version stored;
# validation always occurs before persistence; fields are bounded). Stored
# content is immutable via triggers, matching the durable-record discipline.
# UNIQUE(identity_hash) is the canonical analysis identity: retries, lease
# recovery, and explicit reruns reuse one analysis, and a provider/model/
# prompt/schema change produces a new version instead of overwriting history.
# Candidate Claims and candidate Evidence excerpts live only inside
# result_json; article_analyses never holds canonical EvidenceSpans or Claims.
# The migration is additive: schema-17 data is preserved unchanged and no
# historical analysis is fabricated.
MIGRATION_0018_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE article_analyses (
        id TEXT PRIMARY KEY,
        document_version_id TEXT NOT NULL REFERENCES document_versions(id),
        relevance_id TEXT NOT NULL REFERENCES document_version_relevance(id),
        monitor_id TEXT NOT NULL REFERENCES monitors(id),
        job_id TEXT REFERENCES jobs(id),
        scope_version INTEGER NOT NULL CHECK (scope_version > 0),
        artifact_id TEXT NOT NULL REFERENCES content_artifacts(id),
        normalized_content_hash TEXT NOT NULL,
        identity_hash TEXT NOT NULL UNIQUE,
        schema_version TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        provider TEXT NOT NULL,
        model TEXT NOT NULL,
        paid INTEGER NOT NULL DEFAULT 0 CHECK (paid IN (0, 1)),
        confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
        input_char_count INTEGER NOT NULL CHECK (input_char_count >= 0),
        analyzed_char_count INTEGER NOT NULL CHECK (analyzed_char_count >= 0),
        truncated INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0, 1)),
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX article_analyses_version_idx ON article_analyses(document_version_id, created_at, id)",
    "CREATE INDEX article_analyses_relevance_idx ON article_analyses(relevance_id)",
    "CREATE INDEX article_analyses_monitor_idx ON article_analyses(monitor_id, scope_version)",
    """
    CREATE TRIGGER article_analyses_immutable_update
    BEFORE UPDATE ON article_analyses
    BEGIN
        SELECT RAISE(ABORT, 'article analyses are immutable');
    END
    """,
    """
    CREATE TRIGGER article_analyses_immutable_delete
    BEFORE DELETE ON article_analyses
    BEGIN
        SELECT RAISE(ABORT, 'article analyses are append-only');
    END
    """,
)

MIGRATION_0018_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0018_STATEMENTS).encode("utf-8")
).hexdigest()


# Phase 21H — durable paid analysis invocations. The invocation row is the
# serialized authorization boundary for an automatic paid ArticleAnalysis:
# its unique identity prevents two workers from entering the remote provider,
# while its reserved request/cost remains durable before the call begins. A
# remote provider without a documented idempotency contract cannot be retried
# automatically after an uncertain call, so failed/uncertain rows remain
# budget-consuming until an explicit operator reconciliation releases only a
# definitely-not-started invocation.
MIGRATION_0019_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE analysis_invocations (
        id TEXT PRIMARY KEY,
        identity_hash TEXT NOT NULL UNIQUE,
        document_version_id TEXT NOT NULL REFERENCES document_versions(id),
        relevance_id TEXT NOT NULL REFERENCES document_version_relevance(id),
        monitor_id TEXT NOT NULL REFERENCES monitors(id),
        job_id TEXT REFERENCES jobs(id),
        state TEXT NOT NULL CHECK (state IN ('reserved', 'running', 'succeeded', 'failed_terminal', 'retryable', 'uncertain')),
        paid INTEGER NOT NULL DEFAULT 1 CHECK (paid IN (0, 1)),
        reserved_requests INTEGER NOT NULL DEFAULT 0 CHECK (reserved_requests >= 0),
        reserved_cost_usd REAL NOT NULL DEFAULT 0.0 CHECK (reserved_cost_usd >= 0),
        owner_token TEXT,
        lease_expires_at TEXT,
        started_at TEXT,
        completed_at TEXT,
        failure_code TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX analysis_invocations_state_idx ON analysis_invocations(state, updated_at)",
    "CREATE INDEX analysis_invocations_document_idx ON analysis_invocations(document_version_id, created_at, id)",
    "ALTER TABLE provider_usage ADD COLUMN invocation_id TEXT REFERENCES analysis_invocations(id)",
    "CREATE INDEX provider_usage_invocation_idx ON provider_usage(invocation_id)",
)

MIGRATION_0019_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0019_STATEMENTS).encode("utf-8")
).hexdigest()

# Phase 21H.2 — exact analysis-input provenance and immutable relevance.
# Existing ArticleAnalysis rows remain readable with NULL v2 provenance, but
# only newly-created rows carrying the complete contract can be eligible for
# automatic evidence promotion.
MIGRATION_0020_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE article_analyses ADD COLUMN input_view_version TEXT",
    "ALTER TABLE article_analyses ADD COLUMN input_content_hash TEXT",
    "ALTER TABLE article_analyses ADD COLUMN analyzed_content_hash TEXT",
    "ALTER TABLE article_analyses ADD COLUMN invocation_id TEXT REFERENCES analysis_invocations(id)",
    "CREATE INDEX article_analyses_invocation_idx ON article_analyses(invocation_id)",
    """
    CREATE TRIGGER article_analyses_input_contract_insert
    BEFORE INSERT ON article_analyses
    WHEN NEW.input_view_version IS NOT NULL
         OR NEW.input_content_hash IS NOT NULL
         OR NEW.analyzed_content_hash IS NOT NULL
    BEGIN
        SELECT CASE WHEN NEW.input_view_version IS NULL
                          OR NEW.input_content_hash IS NULL
                          OR NEW.analyzed_content_hash IS NULL
                          OR NEW.input_char_count < 1
                          OR NEW.analyzed_char_count < 1
                          OR NEW.analyzed_char_count > NEW.input_char_count
                          OR NEW.truncated != (NEW.analyzed_char_count < NEW.input_char_count)
                          OR (NEW.paid = 1 AND NEW.invocation_id IS NULL)
                          OR (NEW.paid = 0 AND NEW.invocation_id IS NOT NULL)
                    THEN RAISE(ABORT, 'invalid article analysis input contract') END;
    END
    """,
    """
    CREATE TRIGGER document_version_relevance_immutable_update
    BEFORE UPDATE ON document_version_relevance
    BEGIN
        SELECT RAISE(ABORT, 'document version relevance is immutable');
    END
    """,
    """
    CREATE TRIGGER document_version_relevance_immutable_delete
    BEFORE DELETE ON document_version_relevance
    BEGIN
        SELECT RAISE(ABORT, 'document version relevance is immutable');
    END
    """,
)

MIGRATION_0020_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0020_STATEMENTS).encode("utf-8")
).hexdigest()

# Phase 22 — locally verified evidence and canonical unassigned Claims.
# SQLite cannot remove the historical claims.story_id NOT NULL constraint in
# place. legacy_alter_table keeps existing child FKs pointed at the canonical
# table name while the rows are copied losslessly into the widened table.
MIGRATION_0021_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE evidence_spans ADD COLUMN article_analysis_id TEXT REFERENCES article_analyses(id)",
    "ALTER TABLE evidence_spans ADD COLUMN artifact_id TEXT REFERENCES content_artifacts(id)",
    "ALTER TABLE evidence_spans ADD COLUMN artifact_content_hash TEXT",
    "ALTER TABLE evidence_spans ADD COLUMN view_content_hash TEXT",
    "ALTER TABLE evidence_spans ADD COLUMN view_kind TEXT CHECK (view_kind IN ('artifact', 'feed'))",
    "ALTER TABLE evidence_spans ADD COLUMN view_version TEXT",
    "ALTER TABLE evidence_spans ADD COLUMN field_path TEXT",
    "ALTER TABLE evidence_spans ADD COLUMN start_offset INTEGER",
    "ALTER TABLE evidence_spans ADD COLUMN end_offset INTEGER",
    "ALTER TABLE evidence_spans ADD COLUMN verification_method TEXT",
    "ALTER TABLE evidence_spans ADD COLUMN provenance_json TEXT",
    "CREATE INDEX evidence_spans_analysis_idx ON evidence_spans(article_analysis_id)",
    "DROP TRIGGER claims_accepted_text_immutable",
    "DROP TRIGGER claims_acceptance_immutable",
    "DROP TRIGGER claims_immutable_delete",
    "PRAGMA legacy_alter_table = ON",
    "ALTER TABLE claims RENAME TO claims_legacy_0021",
    """
    CREATE TABLE claims (
        id TEXT PRIMARY KEY,
        story_id TEXT REFERENCES stories(id) ON DELETE CASCADE,
        proposition TEXT NOT NULL,
        proposition_hash TEXT NOT NULL,
        importance TEXT NOT NULL DEFAULT 'relevant' CHECK (importance IN ('major', 'relevant', 'peripheral')),
        state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'supported', 'partially_supported', 'disputed', 'unsubstantiated', 'superseded')),
        supersedes_claim_id TEXT REFERENCES claims(id),
        article_analysis_id TEXT REFERENCES article_analyses(id),
        candidate_claim_index INTEGER,
        created_at TEXT NOT NULL,
        accepted_at TEXT,
        CHECK ((article_analysis_id IS NULL AND candidate_claim_index IS NULL AND story_id IS NOT NULL)
            OR (article_analysis_id IS NOT NULL AND candidate_claim_index IS NOT NULL AND candidate_claim_index >= 0)),
        UNIQUE (article_analysis_id, candidate_claim_index)
    )
    """,
    """
    INSERT INTO claims
        (id, story_id, proposition, proposition_hash, importance, state,
         supersedes_claim_id, created_at, accepted_at)
    SELECT id, story_id, proposition, proposition_hash, importance, state,
           supersedes_claim_id, created_at, accepted_at
    FROM claims_legacy_0021
    """,
    "DROP TABLE claims_legacy_0021",
    "PRAGMA legacy_alter_table = OFF",
    """
    CREATE TRIGGER claims_accepted_text_immutable
    BEFORE UPDATE OF proposition, proposition_hash ON claims
    WHEN OLD.accepted_at IS NOT NULL
         AND (NEW.proposition IS NOT OLD.proposition OR NEW.proposition_hash IS NOT OLD.proposition_hash)
    BEGIN
        SELECT RAISE(ABORT, 'accepted claim text is immutable');
    END
    """,
    """
    CREATE TRIGGER claims_automatic_provenance_immutable
    BEFORE UPDATE OF story_id, proposition, proposition_hash, article_analysis_id, candidate_claim_index ON claims
    WHEN OLD.article_analysis_id IS NOT NULL
    BEGIN
        SELECT RAISE(ABORT, 'automatic claim provenance is immutable');
    END
    """,
    """
    CREATE TRIGGER claims_acceptance_immutable
    BEFORE UPDATE OF accepted_at ON claims
    WHEN OLD.accepted_at IS NOT NULL
         AND NEW.accepted_at IS NOT OLD.accepted_at
    BEGIN
        SELECT RAISE(ABORT, 'claim acceptance is immutable');
    END
    """,
    """
    CREATE TRIGGER claims_immutable_delete
    BEFORE DELETE ON claims
    BEGIN
        SELECT RAISE(ABORT, 'claims are append-only');
    END
    """,
    """
    CREATE TABLE article_analysis_promotions (
        id TEXT PRIMARY KEY,
        promotion_identity TEXT NOT NULL UNIQUE,
        article_analysis_id TEXT NOT NULL REFERENCES article_analyses(id),
        candidate_claim_index INTEGER NOT NULL CHECK (candidate_claim_index >= 0),
        outcome_code TEXT NOT NULL,
        claim_id TEXT REFERENCES claims(id),
        evidence_span_ids_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL,
        UNIQUE (article_analysis_id, candidate_claim_index)
    )
    """,
    "CREATE INDEX article_analysis_promotions_analysis_idx ON article_analysis_promotions(article_analysis_id)",
    """
    CREATE TRIGGER evidence_spans_verified_contract_insert
    BEFORE INSERT ON evidence_spans
    WHEN NEW.verification_method IS NOT NULL
    BEGIN
        SELECT CASE WHEN NEW.article_analysis_id IS NULL OR NEW.artifact_id IS NULL
                          OR NEW.artifact_content_hash IS NULL OR NEW.view_content_hash IS NULL
                          OR NEW.view_kind IS NULL OR NEW.view_version IS NULL
                          OR NEW.start_offset IS NULL OR NEW.end_offset IS NULL
                          OR NEW.start_offset < 0 OR NEW.end_offset <= NEW.start_offset
                          OR NEW.provenance_json IS NULL
                    THEN RAISE(ABORT, 'invalid verified evidence contract') END;
    END
    """,
    """
    CREATE TRIGGER article_analysis_promotions_immutable_update
    BEFORE UPDATE ON article_analysis_promotions
    BEGIN SELECT RAISE(ABORT, 'analysis promotions are immutable'); END
    """,
    """
    CREATE TRIGGER article_analysis_promotions_immutable_delete
    BEFORE DELETE ON article_analysis_promotions
    BEGIN SELECT RAISE(ABORT, 'analysis promotions are immutable'); END
    """,
)

MIGRATION_0021_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0021_STATEMENTS).encode("utf-8")
).hexdigest()

# Phase 22.1 — keep manual evidence distinct from automatically verified
# evidence, separate the Claim Story lifecycle from immutable automatic
# provenance, and make promotion outcomes describe a coherent trusted graph.
# SQLite cannot drop the historical EvidenceSpan table-level uniqueness in
# place, so the table is rebuilt while preserving every row ID and child FK.
MIGRATION_0022_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER evidence_spans_immutable_update",
    "DROP TRIGGER evidence_spans_immutable_delete",
    "DROP TRIGGER evidence_spans_verified_contract_insert",
    "PRAGMA legacy_alter_table = ON",
    "ALTER TABLE evidence_spans RENAME TO evidence_spans_legacy_0022",
    """
    CREATE TABLE evidence_spans (
        id TEXT PRIMARY KEY,
        document_version_id TEXT NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
        excerpt TEXT NOT NULL,
        locator_type TEXT,
        locator_value TEXT,
        span_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        article_analysis_id TEXT REFERENCES article_analyses(id),
        artifact_id TEXT REFERENCES content_artifacts(id),
        artifact_content_hash TEXT,
        view_content_hash TEXT,
        view_kind TEXT CHECK (view_kind IN ('artifact', 'feed')),
        view_version TEXT,
        field_path TEXT,
        start_offset INTEGER,
        end_offset INTEGER,
        verification_method TEXT,
        provenance_json TEXT
    )
    """,
    """
    INSERT INTO evidence_spans
        (id, document_version_id, excerpt, locator_type, locator_value, span_hash, created_at,
         article_analysis_id, artifact_id, artifact_content_hash, view_content_hash,
         view_kind, view_version, field_path, start_offset, end_offset,
         verification_method, provenance_json)
    SELECT id, document_version_id, excerpt, locator_type, locator_value, span_hash, created_at,
           article_analysis_id, artifact_id, artifact_content_hash, view_content_hash,
           view_kind, view_version, field_path, start_offset, end_offset,
           verification_method, provenance_json
    FROM evidence_spans_legacy_0022
    """,
    "DROP TABLE evidence_spans_legacy_0022",
    "PRAGMA legacy_alter_table = OFF",
    "CREATE INDEX evidence_spans_analysis_idx ON evidence_spans(article_analysis_id)",
    "CREATE UNIQUE INDEX evidence_spans_manual_identity_idx ON evidence_spans(document_version_id, span_hash) WHERE verification_method IS NULL",
    """
    CREATE UNIQUE INDEX evidence_spans_verified_identity_idx
    ON evidence_spans(
        document_version_id, span_hash, verification_method, article_analysis_id,
        artifact_id, artifact_content_hash, view_content_hash, view_kind,
        view_version, COALESCE(field_path, ''), start_offset, end_offset,
        provenance_json
    ) WHERE verification_method IS NOT NULL
    """,
    """
    CREATE TRIGGER evidence_spans_immutable_update
    BEFORE UPDATE ON evidence_spans
    BEGIN
        SELECT RAISE(ABORT, 'evidence spans are immutable');
    END
    """,
    """
    CREATE TRIGGER evidence_spans_immutable_delete
    BEFORE DELETE ON evidence_spans
    BEGIN
        SELECT RAISE(ABORT, 'evidence spans are immutable');
    END
    """,
    """
    CREATE TRIGGER evidence_spans_verified_contract_insert
    BEFORE INSERT ON evidence_spans
    WHEN NEW.verification_method IS NOT NULL
         OR NEW.article_analysis_id IS NOT NULL
         OR NEW.artifact_id IS NOT NULL
         OR NEW.artifact_content_hash IS NOT NULL
         OR NEW.view_content_hash IS NOT NULL
         OR NEW.view_kind IS NOT NULL
         OR NEW.view_version IS NOT NULL
         OR NEW.field_path IS NOT NULL
         OR NEW.start_offset IS NOT NULL
         OR NEW.end_offset IS NOT NULL
         OR NEW.provenance_json IS NOT NULL
    BEGIN
        SELECT CASE WHEN NEW.verification_method IS NULL
                          OR NEW.verification_method != 'exact_analyzed_slice_v1'
                          OR NEW.article_analysis_id IS NULL
                          OR NEW.artifact_id IS NULL
                          OR NEW.artifact_content_hash IS NULL
                          OR NEW.view_content_hash IS NULL
                          OR NEW.view_kind IS NULL
                          OR NEW.view_version IS NULL
                          OR NEW.start_offset IS NULL
                          OR NEW.end_offset IS NULL
                          OR NEW.start_offset < 0
                          OR NEW.end_offset <= NEW.start_offset
                          OR NEW.provenance_json IS NULL
                          OR json_valid(NEW.provenance_json) != 1
                          OR json_extract(NEW.provenance_json, '$.analysis_id') IS NOT NEW.article_analysis_id
                          OR json_type(NEW.provenance_json, '$.candidate_claim_index') != 'integer'
                          OR json_type(NEW.provenance_json, '$.candidate_excerpt_index') != 'integer'
                    THEN RAISE(ABORT, 'invalid verified evidence contract') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM article_analyses a
            JOIN content_artifacts ca ON ca.id = a.artifact_id
            WHERE a.id = NEW.article_analysis_id
              AND a.document_version_id = NEW.document_version_id
              AND a.artifact_id = NEW.artifact_id
              AND a.normalized_content_hash = NEW.artifact_content_hash
              AND ca.normalized_content_hash = NEW.artifact_content_hash
              AND NEW.end_offset <= a.analyzed_char_count
        ) THEN RAISE(ABORT, 'verified evidence provenance does not match analysis') END;
    END
    """,
    "DROP TRIGGER claims_automatic_provenance_immutable",
    """
    CREATE TRIGGER claims_automatic_provenance_immutable
    BEFORE UPDATE OF proposition, proposition_hash, article_analysis_id, candidate_claim_index ON claims
    WHEN OLD.article_analysis_id IS NOT NULL
    BEGIN
        SELECT RAISE(ABORT, 'automatic claim provenance is immutable');
    END
    """,
    """
    CREATE TRIGGER claims_story_association_immutable
    BEFORE UPDATE OF story_id ON claims
    WHEN OLD.story_id IS NOT NULL
         AND NEW.story_id IS NOT OLD.story_id
    BEGIN
        SELECT RAISE(ABORT, 'claim Story association is immutable');
    END
    """,
    """
    CREATE TABLE claim_story_assignment_history (
        id TEXT PRIMARY KEY,
        claim_id TEXT NOT NULL UNIQUE REFERENCES claims(id) ON DELETE CASCADE,
        from_story_id TEXT REFERENCES stories(id) ON DELETE SET NULL,
        to_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        reason TEXT NOT NULL DEFAULT 'controlled Story assignment',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX claim_story_assignment_history_story_idx ON claim_story_assignment_history(to_story_id, created_at, id)",
    """
    CREATE TRIGGER claim_story_assignment_history_insert
    AFTER UPDATE OF story_id ON claims
    WHEN OLD.story_id IS NULL AND NEW.story_id IS NOT NULL
    BEGIN
        INSERT INTO claim_story_assignment_history
            (id, claim_id, from_story_id, to_story_id, reason, created_at)
        VALUES
            ('csa_' || lower(hex(randomblob(16))), NEW.id, OLD.story_id, NEW.story_id,
             'controlled Story assignment', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
    END
    """,
    """
    CREATE TRIGGER claim_story_assignment_history_immutable_update
    BEFORE UPDATE ON claim_story_assignment_history
    BEGIN
        SELECT RAISE(ABORT, 'Claim Story assignment history is append-only');
    END
    """,
    """
    CREATE TRIGGER claim_story_assignment_history_immutable_delete
    BEFORE DELETE ON claim_story_assignment_history
    BEGIN
        SELECT RAISE(ABORT, 'Claim Story assignment history is append-only');
    END
    """,
    """
    CREATE TRIGGER claims_automatic_insert_pending
    BEFORE INSERT ON claims
    WHEN NEW.article_analysis_id IS NOT NULL AND NEW.story_id IS NOT NULL
    BEGIN
        SELECT RAISE(ABORT, 'automatic Claims must begin without a Story');
    END
    """,
    """
    CREATE TRIGGER article_analysis_promotions_verified_contract_insert
    BEFORE INSERT ON article_analysis_promotions
    WHEN NEW.outcome_code = 'verified'
    BEGIN
        SELECT CASE WHEN NEW.claim_id IS NULL
                          OR json_valid(NEW.evidence_span_ids_json) != 1
                          OR json_type(NEW.evidence_span_ids_json) != 'array'
                          OR json_array_length(NEW.evidence_span_ids_json) < 1
                    THEN RAISE(ABORT, 'invalid verified promotion outcome') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM claims c
            WHERE c.id = NEW.claim_id
              AND c.article_analysis_id = NEW.article_analysis_id
              AND c.candidate_claim_index = NEW.candidate_claim_index
              AND c.story_id IS NULL
        ) THEN RAISE(ABORT, 'verified promotion Claim does not match analysis') END;
        SELECT CASE WHEN EXISTS (
            SELECT 1
            FROM json_each(NEW.evidence_span_ids_json) ids
            LEFT JOIN evidence_spans es ON es.id = ids.value
            WHERE es.id IS NULL
               OR es.article_analysis_id IS NOT NEW.article_analysis_id
               OR es.verification_method IS NOT 'exact_analyzed_slice_v1'
        ) THEN RAISE(ABORT, 'verified promotion evidence does not match analysis') END;
    END
    """,
    """
    CREATE TRIGGER article_analysis_promotions_failed_contract_insert
    BEFORE INSERT ON article_analysis_promotions
    WHEN NEW.outcome_code != 'verified'
    BEGIN
        SELECT CASE WHEN NEW.claim_id IS NOT NULL
                          OR json_valid(NEW.evidence_span_ids_json) != 1
                          OR json_type(NEW.evidence_span_ids_json) != 'array'
                          OR json_array_length(NEW.evidence_span_ids_json) != 0
                    THEN RAISE(ABORT, 'invalid failed promotion outcome') END;
    END
    """,
)

MIGRATION_0022_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0022_STATEMENTS).encode("utf-8")
).hexdigest()

# Phase 22.1 follow-up — harden the insert contracts introduced by migration
# 0022 for databases that have already reached schema 22. This is additive:
# no canonical rows or historical provenance are rewritten.
MIGRATION_0023_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER evidence_spans_verified_contract_insert",
    """
    CREATE TRIGGER evidence_spans_verified_contract_insert
    BEFORE INSERT ON evidence_spans
    WHEN NEW.verification_method IS NOT NULL
         OR NEW.article_analysis_id IS NOT NULL
         OR NEW.artifact_id IS NOT NULL
         OR NEW.artifact_content_hash IS NOT NULL
         OR NEW.view_content_hash IS NOT NULL
         OR NEW.view_kind IS NOT NULL
         OR NEW.view_version IS NOT NULL
         OR NEW.field_path IS NOT NULL
         OR NEW.start_offset IS NOT NULL
         OR NEW.end_offset IS NOT NULL
         OR NEW.provenance_json IS NOT NULL
    BEGIN
        SELECT CASE WHEN NEW.verification_method IS NULL
                          OR NEW.verification_method != 'exact_analyzed_slice_v1'
                          OR NEW.article_analysis_id IS NULL
                          OR NEW.artifact_id IS NULL
                          OR NEW.artifact_content_hash IS NULL
                          OR NEW.view_content_hash IS NULL
                          OR NEW.view_kind IS NULL
                          OR NEW.view_version IS NULL
                          OR NEW.start_offset IS NULL
                          OR NEW.end_offset IS NULL
                          OR NEW.start_offset < 0
                          OR NEW.end_offset <= NEW.start_offset
                          OR NEW.provenance_json IS NULL
                          OR json_valid(NEW.provenance_json) != 1
                          OR json_extract(NEW.provenance_json, '$.analysis_id') IS NOT NEW.article_analysis_id
                          OR json_type(NEW.provenance_json, '$.candidate_claim_index') != 'integer'
                          OR json_type(NEW.provenance_json, '$.candidate_excerpt_index') != 'integer'
                    THEN RAISE(ABORT, 'invalid verified evidence contract') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM article_analyses a
            JOIN content_artifacts ca ON ca.id = a.artifact_id
            WHERE a.id = NEW.article_analysis_id
              AND a.document_version_id = NEW.document_version_id
              AND a.artifact_id = NEW.artifact_id
              AND a.normalized_content_hash = NEW.artifact_content_hash
              AND ca.normalized_content_hash = NEW.artifact_content_hash
              AND a.input_view_version IS NEW.view_version
              AND a.input_content_hash IS NEW.view_content_hash
              AND ((NEW.view_kind = 'artifact' AND NEW.field_path IS NULL)
                   OR (NEW.view_kind = 'feed' AND NEW.field_path IS 'title;summary'))
              AND NEW.end_offset <= a.analyzed_char_count
        ) THEN RAISE(ABORT, 'verified evidence provenance does not match analysis') END;
    END
    """,
    "DROP TRIGGER claims_automatic_insert_pending",
    """
    CREATE TRIGGER claims_automatic_insert_pending
    BEFORE INSERT ON claims
    WHEN NEW.article_analysis_id IS NOT NULL
         AND (NEW.story_id IS NOT NULL OR NEW.state IS NOT 'pending' OR NEW.accepted_at IS NOT NULL)
    BEGIN
        SELECT RAISE(ABORT, 'automatic Claims must begin pending and without a Story');
    END
    """,
    """
    CREATE TRIGGER claim_evidence_automatic_contract_insert
    BEFORE INSERT ON claim_evidence
    WHEN EXISTS (
        SELECT 1 FROM claims c
        WHERE c.id = NEW.claim_id AND c.article_analysis_id IS NOT NULL
    )
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1
            FROM claims c
            JOIN evidence_spans es ON es.id = NEW.evidence_span_id
            JOIN article_analyses a ON a.id = c.article_analysis_id
            WHERE c.id = NEW.claim_id
              AND es.article_analysis_id IS c.article_analysis_id
              AND es.verification_method IS 'exact_analyzed_slice_v1'
              AND json_extract(es.provenance_json, '$.candidate_claim_index') IS c.candidate_claim_index
              AND es.artifact_id IS NOT NULL
              AND es.artifact_content_hash IS NOT NULL
              AND es.view_content_hash IS NOT NULL
              AND es.view_kind IS NOT NULL
              AND es.view_version IS NOT NULL
              AND es.start_offset IS NOT NULL
              AND es.end_offset IS NOT NULL
              AND a.input_view_version IS es.view_version
              AND a.input_content_hash IS es.view_content_hash
        ) THEN RAISE(ABORT, 'automatic Claims require verified evidence') END;
    END
    """,
    "DROP TRIGGER article_analysis_promotions_verified_contract_insert",
    """
    CREATE TRIGGER article_analysis_promotions_verified_contract_insert
    BEFORE INSERT ON article_analysis_promotions
    WHEN NEW.outcome_code = 'verified'
    BEGIN
        SELECT CASE WHEN NEW.claim_id IS NULL
                          OR json_valid(NEW.evidence_span_ids_json) != 1
                          OR json_type(NEW.evidence_span_ids_json) != 'array'
                          OR json_array_length(NEW.evidence_span_ids_json) < 1
                    THEN RAISE(ABORT, 'invalid verified promotion outcome') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM claims c
            WHERE c.id = NEW.claim_id
              AND c.article_analysis_id = NEW.article_analysis_id
              AND c.candidate_claim_index = NEW.candidate_claim_index
              AND c.story_id IS NULL
        ) THEN RAISE(ABORT, 'verified promotion Claim does not match analysis') END;
        SELECT CASE WHEN EXISTS (
            SELECT 1
            FROM json_each(NEW.evidence_span_ids_json) ids
            LEFT JOIN evidence_spans es ON es.id = ids.value
            LEFT JOIN claim_evidence ce
              ON ce.claim_id = NEW.claim_id AND ce.evidence_span_id = ids.value
            WHERE es.id IS NULL
               OR es.article_analysis_id IS NOT NEW.article_analysis_id
               OR es.verification_method IS NOT 'exact_analyzed_slice_v1'
               OR json_extract(es.provenance_json, '$.candidate_claim_index') IS NOT NEW.candidate_claim_index
               OR ce.id IS NULL
        ) THEN RAISE(ABORT, 'verified promotion evidence does not match analysis') END;
    END
    """,
)

MIGRATION_0023_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0023_STATEMENTS).encode("utf-8")
).hexdigest()


# Phase 24 — a Watch is the user-facing monitoring instruction. Approved
# Sources are implemented by ordinary source Monitors, preserving the existing
# scheduler/acquisition/relevance pipeline and its compatibility contracts.
#
# The monitors rebuild replaces UNIQUE(target_type, target_id) with per-need
# identity. A Source may now be monitored once per approved information need,
# so two Watches can share one Source while each keeps its own approved scope,
# cadence, and enabled state. Acquisition-only monitors (need_type IS NULL)
# remain limited to one per target, which the old constraint also guaranteed.
# Partial indexes are used deliberately: a table-level UNIQUE over nullable
# need columns would treat every NULL as distinct and silently permit
# duplicate acquisition-only monitors.
MIGRATION_0024_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER search_dirty_monitors_insert",
    "DROP TRIGGER search_dirty_monitors_update",
    "DROP TRIGGER search_dirty_monitors_delete",
    "PRAGMA legacy_alter_table = ON",
    "ALTER TABLE monitors RENAME TO monitors_legacy_0024",
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
        need_type TEXT CHECK (need_type IS NULL OR need_type IN ('topic', 'subject', 'story', 'research_question')),
        need_id TEXT
    )
    """,
    """
    INSERT INTO monitors
        (id, target_type, target_id, policy_id, enabled, next_check_at,
         last_run_at, last_result, created_at, updated_at, need_type, need_id)
    SELECT id, target_type, target_id, policy_id, enabled, next_check_at,
           last_run_at, last_result, created_at, updated_at, need_type, need_id
    FROM monitors_legacy_0024
    """,
    "DROP TABLE monitors_legacy_0024",
    "PRAGMA legacy_alter_table = OFF",
    "CREATE UNIQUE INDEX monitors_acquisition_identity_idx ON monitors(target_type, target_id) WHERE need_type IS NULL",
    "CREATE UNIQUE INDEX monitors_need_identity_idx ON monitors(target_type, target_id, need_type, need_id) WHERE need_type IS NOT NULL",
    "CREATE INDEX monitors_due_idx ON monitors(enabled, next_check_at)",
    """
    CREATE TRIGGER search_dirty_monitors_insert
        AFTER INSERT ON monitors
        BEGIN
            UPDATE search_index_meta SET dirty = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1;
        END
    """,
    """
    CREATE TRIGGER search_dirty_monitors_update
        AFTER UPDATE ON monitors
        BEGIN
            UPDATE search_index_meta SET dirty = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1;
        END
    """,
    """
    CREATE TRIGGER search_dirty_monitors_delete
        AFTER DELETE ON monitors
        BEGIN
            UPDATE search_index_meta SET dirty = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1;
        END
    """,
    """
    CREATE TABLE watches (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        target_type TEXT NOT NULL CHECK (target_type IN ('topic','subject','story','source','research_question')),
        target_id TEXT NOT NULL,
        policy_id TEXT NOT NULL REFERENCES monitoring_policies(id),
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','disabled')),
        priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','urgent')),
        discovery_enabled INTEGER NOT NULL DEFAULT 1 CHECK (discovery_enabled IN (0,1)),
        last_discovery_at TEXT,
        discovery_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(target_type, target_id)
    )
    """,
    "CREATE INDEX watches_status_idx ON watches(status, priority, updated_at DESC)",
    """
    CREATE TABLE watch_vocabulary (
        id TEXT PRIMARY KEY,
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        term TEXT NOT NULL,
        term_normalized TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('primary','alias','synonym','acronym','acronym_expansion','related','include','exclude')),
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','ai','topic','subject','import')),
        status TEXT NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested','approved','rejected')),
        enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0,1)),
        expansion_of TEXT,
        rationale TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT,
        UNIQUE(watch_id, term_normalized, kind)
    )
    """,
    "CREATE INDEX watch_vocabulary_watch_idx ON watch_vocabulary(watch_id, status, created_at, id)",
    """
    CREATE TABLE source_candidates (
        id TEXT PRIMARY KEY,
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
        name TEXT NOT NULL,
        homepage_url TEXT NOT NULL,
        normalized_url TEXT NOT NULL,
        feed_url TEXT,
        discovery_method TEXT NOT NULL CHECK (discovery_method IN ('manual','existing_source','document_link','feed_discovery','web_search','ai_suggestion')),
        rationale TEXT NOT NULL,
        authority_context TEXT NOT NULL DEFAULT '',
        limitations TEXT NOT NULL DEFAULT '',
        provenance_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'suggested' CHECK (status IN ('suggested','approved','rejected')),
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT,
        UNIQUE(watch_id, normalized_url)
    )
    """,
    "CREATE INDEX source_candidates_watch_idx ON source_candidates(watch_id, status, created_at, id)",
    """
    CREATE TABLE watch_sources (
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
        monitor_id TEXT NOT NULL UNIQUE REFERENCES monitors(id) ON DELETE RESTRICT,
        created_at TEXT NOT NULL,
        PRIMARY KEY(watch_id, source_id)
    )
    """,
)

MIGRATION_0024_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0024_STATEMENTS).encode("utf-8")
).hexdigest()


# Phase 25 — extend the Phase 10 Research Question records with a derived,
# evidence-grounded assessment and durable bounded pursuit records.  The
# original ``status`` column remains the explicit human lifecycle authority;
# ``assessment_state`` is the deterministic state computed from canonical
# Claim/Evidence relationships.  The new tables deliberately keep planning,
# candidate discovery, and task history separate from trusted evidence.
MIGRATION_0025_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE research_questions ADD COLUMN assessment_state TEXT NOT NULL DEFAULT 'open' CHECK (assessment_state IN ('open','partially_answered','supported','contradicted','resolved','stale'))",
    "ALTER TABLE research_questions ADD COLUMN assessment_hash TEXT",
    "ALTER TABLE research_questions ADD COLUMN assessment_explanation TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE research_questions ADD COLUMN assessment_at TEXT",
    "ALTER TABLE research_questions ADD COLUMN criteria_json TEXT NOT NULL DEFAULT '{}'",
    "ALTER TABLE research_questions ADD COLUMN pursuit_policy TEXT NOT NULL DEFAULT 'manual' CHECK (pursuit_policy IN ('disabled','manual','automatic'))",
    "ALTER TABLE research_questions ADD COLUMN pursuit_cooldown_seconds INTEGER NOT NULL DEFAULT 3600 CHECK (pursuit_cooldown_seconds >= 0)",
    "ALTER TABLE research_question_claims ADD COLUMN origin TEXT NOT NULL DEFAULT 'manual' CHECK (origin IN ('manual','automatic','task'))",
    "ALTER TABLE research_question_claims ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0)",
    "ALTER TABLE research_question_claims ADD COLUMN rationale TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE research_question_claims ADD COLUMN actor TEXT NOT NULL DEFAULT 'system'",
    "ALTER TABLE research_question_attempts ADD COLUMN task_id TEXT",
    "ALTER TABLE research_question_attempts ADD COLUMN gap_id TEXT",
    """
    CREATE TABLE research_question_assessments (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        snapshot_hash TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('open','partially_answered','supported','contradicted','resolved','stale')),
        explanation TEXT NOT NULL DEFAULT '',
        supporting_claim_count INTEGER NOT NULL DEFAULT 0 CHECK (supporting_claim_count >= 0),
        contradicting_claim_count INTEGER NOT NULL DEFAULT 0 CHECK (contradicting_claim_count >= 0),
        contextual_claim_count INTEGER NOT NULL DEFAULT 0 CHECK (contextual_claim_count >= 0),
        qualifying_evidence_count INTEGER NOT NULL DEFAULT 0 CHECK (qualifying_evidence_count >= 0),
        open_gap_count INTEGER NOT NULL DEFAULT 0 CHECK (open_gap_count >= 0),
        origin TEXT NOT NULL CHECK (origin IN ('automatic','manual')),
        created_at TEXT NOT NULL,
        UNIQUE(question_id, snapshot_hash)
    )
    """,
    "CREATE INDEX research_question_assessments_question_idx ON research_question_assessments(question_id, created_at, id)",
    """
    CREATE TABLE research_question_assessment_history (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        assessment_id TEXT NOT NULL REFERENCES research_question_assessments(id) ON DELETE CASCADE,
        from_state TEXT CHECK (from_state IS NULL OR from_state IN ('open','partially_answered','supported','contradicted','resolved','stale')),
        to_state TEXT NOT NULL CHECK (to_state IN ('open','partially_answered','supported','contradicted','resolved','stale')),
        reason_code TEXT NOT NULL,
        claim_ids_json TEXT NOT NULL DEFAULT '[]',
        origin TEXT NOT NULL CHECK (origin IN ('automatic','manual')),
        created_at TEXT NOT NULL,
        UNIQUE(question_id, assessment_id, to_state)
    )
    """,
    "CREATE INDEX research_question_assessment_history_idx ON research_question_assessment_history(question_id, created_at, id)",
    """
    CREATE TABLE research_question_claim_overrides (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
        relationship TEXT NOT NULL CHECK (relationship IN ('supports','contradicts','contextualizes','resolves')),
        action TEXT NOT NULL CHECK (action IN ('exclude','restore')),
        reason TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL,
        UNIQUE(question_id, claim_id, relationship, action)
    )
    """,
    "CREATE INDEX research_question_claim_overrides_idx ON research_question_claim_overrides(question_id, claim_id, relationship, action)",
    """
    CREATE TABLE research_question_gaps (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        gap_key TEXT NOT NULL,
        gap_type TEXT NOT NULL CHECK (gap_type IN ('supporting_evidence','contradiction_review','independent_support','primary_source')),
        description TEXT NOT NULL,
        rationale TEXT NOT NULL DEFAULT '',
        condition_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','pursuing','satisfied','dismissed','blocked')),
        origin TEXT NOT NULL CHECK (origin IN ('automatic','manual')),
        assessment_hash TEXT,
        first_seen_at TEXT NOT NULL,
        last_evaluated_at TEXT NOT NULL,
        satisfied_at TEXT,
        dismissed_at TEXT,
        dismissed_by TEXT,
        dismissal_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(question_id, gap_key)
    )
    """,
    "CREATE INDEX research_question_gaps_question_idx ON research_question_gaps(question_id, status, updated_at, id)",
    """
    CREATE TABLE research_question_gap_history (
        id TEXT PRIMARY KEY,
        gap_id TEXT NOT NULL REFERENCES research_question_gaps(id) ON DELETE CASCADE,
        from_status TEXT,
        to_status TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        assessment_hash TEXT,
        task_id TEXT,
        actor TEXT NOT NULL DEFAULT 'system',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX research_question_gap_history_idx ON research_question_gap_history(gap_id, created_at, id)",
    """
    CREATE TABLE research_tasks (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        gap_id TEXT NOT NULL REFERENCES research_question_gaps(id) ON DELETE RESTRICT,
        task_no INTEGER NOT NULL CHECK (task_no > 0),
        mode TEXT NOT NULL CHECK (mode IN ('manual','automatic')),
        status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','running','completed_with_evidence','completed_with_candidates','completed_no_findings','deferred','failed','cancelled')),
        job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
        attempt_id TEXT REFERENCES research_question_attempts(id) ON DELETE SET NULL,
        snapshot_hash TEXT,
        plan_json TEXT NOT NULL DEFAULT '{}',
        limits_json TEXT NOT NULL DEFAULT '{}',
        outcome_json TEXT NOT NULL DEFAULT '{}',
        error_code TEXT,
        error_detail TEXT,
        next_attempt_at TEXT,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(question_id, gap_id, task_no)
    )
    """,
    "CREATE INDEX research_tasks_question_idx ON research_tasks(question_id, created_at, id)",
    "CREATE INDEX research_tasks_gap_idx ON research_tasks(gap_id, status, created_at, id)",
    "CREATE UNIQUE INDEX research_tasks_one_active_gap_idx ON research_tasks(gap_id) WHERE status IN ('planned','running')",
    """
    CREATE TABLE research_task_queries (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
        query TEXT NOT NULL,
        query_hash TEXT NOT NULL,
        strategy TEXT NOT NULL,
        ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
        created_at TEXT NOT NULL,
        UNIQUE(task_id, query_hash)
    )
    """,
    "CREATE INDEX research_task_queries_task_idx ON research_task_queries(task_id, ordinal, id)",
    """
    CREATE TABLE research_task_findings (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
        finding_type TEXT NOT NULL CHECK (finding_type IN ('corpus','source_candidate','document','document_version','claim','evidence')),
        identity_key TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate','acquired','processed','relevant','produced_claim','irrelevant')),
        source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
        document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
        document_version_id TEXT REFERENCES document_versions(id) ON DELETE SET NULL,
        claim_id TEXT REFERENCES claims(id) ON DELETE SET NULL,
        evidence_span_id TEXT REFERENCES evidence_spans(id) ON DELETE SET NULL,
        rank INTEGER NOT NULL DEFAULT 0 CHECK (rank >= 0),
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(task_id, finding_type, identity_key)
    )
    """,
    "CREATE INDEX research_task_findings_task_idx ON research_task_findings(task_id, status, created_at, id)",
    """
    CREATE TRIGGER research_question_assessment_history_immutable_update
    BEFORE UPDATE ON research_question_assessment_history
    BEGIN SELECT RAISE(ABORT, 'research question assessment history is append-only'); END
    """,
    """
    CREATE TRIGGER research_question_assessment_history_immutable_delete
    BEFORE DELETE ON research_question_assessment_history
    BEGIN SELECT RAISE(ABORT, 'research question assessment history is append-only'); END
    """,
    """
    CREATE TRIGGER research_question_gap_history_immutable_update
    BEFORE UPDATE ON research_question_gap_history
    BEGIN SELECT RAISE(ABORT, 'research question gap history is append-only'); END
    """,
    """
    CREATE TRIGGER research_question_gap_history_immutable_delete
    BEFORE DELETE ON research_question_gap_history
    BEGIN SELECT RAISE(ABORT, 'research question gap history is append-only'); END
    """,
)

MIGRATION_0025_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0025_STATEMENTS).encode("utf-8")
).hexdigest()


# Phase 26 — canonical knowledge metadata.  These tables are deliberately
# additive: Entity/Tag metadata can organize existing intelligence, but it is
# never an alternative Evidence or Claim path.
MIGRATION_0026_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE entities (
        id TEXT PRIMARY KEY,
        canonical_name TEXT NOT NULL,
        normalized_name TEXT NOT NULL UNIQUE,
        entity_type TEXT NOT NULL CHECK (entity_type IN ('person','organization','agency','company','program','location','event','legislation','technology','publication','other','unknown')),
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','candidate','merged')),
        merged_into_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX entities_type_status_idx ON entities(entity_type, status, normalized_name, id)",
    """
    CREATE TABLE entity_aliases (
        id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
        alias TEXT NOT NULL,
        normalized_alias TEXT NOT NULL,
        alias_type TEXT NOT NULL CHECK (alias_type IN ('alternate_name','acronym','expanded_name','abbreviation','former_name','deterministic')),
        origin TEXT NOT NULL CHECK (origin IN ('user','subject','watch','article_analysis','deterministic','provider','import')),
        status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired')),
        created_at TEXT NOT NULL,
        UNIQUE(entity_id, normalized_alias)
    )
    """,
    "CREATE INDEX entity_aliases_lookup_idx ON entity_aliases(normalized_alias, status, entity_id)",
    """
    CREATE TABLE entity_mentions (
        id TEXT PRIMARY KEY,
        entity_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
        mention_text TEXT NOT NULL,
        normalized_mention TEXT NOT NULL,
        source_type TEXT NOT NULL CHECK (source_type IN ('article_analysis','document_version','claim','manual','unknown')),
        source_id TEXT,
        article_analysis_id TEXT REFERENCES article_analyses(id) ON DELETE SET NULL,
        document_version_id TEXT REFERENCES document_versions(id) ON DELETE SET NULL,
        resolution_status TEXT NOT NULL CHECK (resolution_status IN ('resolved','unresolved','ambiguous')),
        resolution_method TEXT NOT NULL CHECK (resolution_method IN ('user','deterministic','provider','unresolved')),
        confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
        context_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        UNIQUE(source_type, source_id, normalized_mention)
    )
    """,
    "CREATE INDEX entity_mentions_entity_idx ON entity_mentions(entity_id, created_at, id)",
    "CREATE INDEX entity_mentions_analysis_idx ON entity_mentions(article_analysis_id, normalized_mention, id)",
    """
    CREATE TABLE claim_entities (
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        role TEXT NOT NULL CHECK (role IN ('subject','object','mentioned','context')),
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        mention_id TEXT REFERENCES entity_mentions(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY(claim_id, entity_id, role)
    )
    """,
    "CREATE INDEX claim_entities_entity_idx ON claim_entities(entity_id, claim_id, role)",
    """
    CREATE TABLE story_entities (
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        created_at TEXT NOT NULL,
        PRIMARY KEY(story_id, entity_id)
    )
    """,
    "CREATE INDEX story_entities_entity_idx ON story_entities(entity_id, story_id)",
    """
    CREATE TABLE research_question_entities (
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        created_at TEXT NOT NULL,
        PRIMARY KEY(question_id, entity_id)
    )
    """,
    "CREATE INDEX research_question_entities_entity_idx ON research_question_entities(entity_id, question_id)",
    """
    CREATE TABLE research_gap_entities (
        gap_id TEXT NOT NULL REFERENCES research_question_gaps(id) ON DELETE CASCADE,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        created_at TEXT NOT NULL,
        PRIMARY KEY(gap_id, entity_id)
    )
    """,
    """
    CREATE TABLE research_task_entities (
        task_id TEXT NOT NULL REFERENCES research_tasks(id) ON DELETE CASCADE,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        created_at TEXT NOT NULL,
        PRIMARY KEY(task_id, entity_id)
    )
    """,
    "CREATE INDEX research_task_entities_entity_idx ON research_task_entities(entity_id, task_id)",
    """
    CREATE TABLE watch_entities (
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        created_at TEXT NOT NULL,
        PRIMARY KEY(watch_id, entity_id)
    )
    """,
    """
    CREATE TABLE tag_assignments (
        id TEXT PRIMARY KEY,
        tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        object_type TEXT NOT NULL CHECK (object_type IN ('entity','claim','evidence','document','story','research_question','research_gap','research_task','source','watch','article_analysis')),
        object_id TEXT NOT NULL,
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
        reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE(tag_id, object_type, object_id)
    )
    """,
    "CREATE INDEX tag_assignments_object_idx ON tag_assignments(object_type, object_id, tag_id)",
    "CREATE INDEX tag_assignments_tag_idx ON tag_assignments(tag_id, object_type, object_id)",
    "CREATE UNIQUE INDEX tags_namespace_normalized_unique_idx ON tags(namespace, normalized_name)",
    """
    CREATE TABLE entity_merges (
        id TEXT PRIMARY KEY,
        from_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        into_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        reason TEXT NOT NULL DEFAULT '',
        actor TEXT NOT NULL DEFAULT 'user',
        created_at TEXT NOT NULL,
        UNIQUE(from_entity_id, into_entity_id)
    )
    """,
    """
    CREATE TABLE knowledge_backfills (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL CHECK (kind IN ('article_analysis_entities','smart_tags')),
        status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled')),
        cursor TEXT,
        processed INTEGER NOT NULL DEFAULT 0 CHECK (processed >= 0),
        row_limit INTEGER NOT NULL CHECK (row_limit > 0),
        batch_size INTEGER NOT NULL CHECK (batch_size > 0),
        error_code TEXT,
        error_detail TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    "CREATE INDEX knowledge_backfills_status_idx ON knowledge_backfills(kind, status, updated_at, id)",
    "ALTER TABLE search_records RENAME TO search_records_legacy_0026",
    """
    CREATE TABLE search_records (
        id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL CHECK (entity_type IN ('monitor','source','document','story','subject','claim','evidence','tag','question','note','entity','research_task','report','watch')),
        entity_id TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        source_id TEXT,
        story_id TEXT,
        subject_id TEXT,
        monitor_id TEXT,
        question_id TEXT,
        tag_id TEXT,
        document_id TEXT,
        state TEXT,
        lifecycle TEXT,
        assessment_state TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(entity_type, entity_id)
    )
    """,
    """
    INSERT INTO search_records
        (id, entity_type, entity_id, title, body, source_id, story_id,
         subject_id, monitor_id, question_id, tag_id, document_id, state,
         lifecycle, assessment_state, created_at)
    SELECT id, entity_type, entity_id, title, body, source_id, story_id,
           subject_id, monitor_id, question_id, tag_id, document_id, state,
           lifecycle, NULL, created_at
    FROM search_records_legacy_0026
    """,
    "DROP TABLE search_records_legacy_0026",
    "CREATE INDEX search_records_type_idx ON search_records(entity_type, entity_id)",
    "CREATE INDEX search_records_filter_idx ON search_records(source_id, story_id, subject_id, monitor_id, question_id, tag_id, document_id)",
    "UPDATE search_index_meta SET dirty = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
    """
    CREATE TRIGGER entity_merges_immutable_update
    BEFORE UPDATE ON entity_merges
    BEGIN SELECT RAISE(ABORT, 'entity merge lineage is append-only'); END
    """,
    """
    CREATE TRIGGER entity_merges_immutable_delete
    BEFORE DELETE ON entity_merges
    BEGIN SELECT RAISE(ABORT, 'entity merge lineage is append-only'); END
    """,
    *tuple(
        f"""
        CREATE TRIGGER search_dirty_{table}_{operation}
        AFTER {operation.upper()} ON {table}
        BEGIN
            UPDATE search_index_meta SET dirty = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1;
        END
        """
        for table in (
            "entities", "entity_aliases", "entity_mentions", "claim_entities",
            "story_entities", "research_question_entities", "research_gap_entities",
            "research_task_entities", "watch_entities", "tag_assignments",
            "entity_merges", "knowledge_backfills",
        )
        for operation in ("insert", "update", "delete")
    ),
)

MIGRATION_0026_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0026_STATEMENTS).encode("utf-8")
).hexdigest()


# 0027: extend persisted Ask scopes to canonical Phase 26 knowledge objects.
# The table rebuild keeps existing sessions/runs intact while widening the
# closed scope vocabulary; Ask history remains audit metadata, not evidence.
MIGRATION_0027_STATEMENTS: tuple[str, ...] = (
    "DROP INDEX ask_runs_status_idx",
    "DROP INDEX ask_runs_conversation_idx",
    "DROP INDEX ask_conversations_scope_idx",
    "ALTER TABLE ask_runs RENAME TO ask_runs_legacy_0027",
    "ALTER TABLE ask_conversations RENAME TO ask_conversations_legacy_0027",
    """
    CREATE TABLE ask_conversations (
        id TEXT PRIMARY KEY,
        scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'story', 'claim', 'evidence', 'document', 'report', 'question', 'research_question', 'subject', 'monitor', 'note', 'entity', 'research_task')),
        scope_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK ((scope_type = 'global' AND scope_id IS NULL) OR (scope_type <> 'global' AND scope_id IS NOT NULL))
    )
    """,
    """
    CREATE TABLE ask_runs (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES ask_conversations(id) ON DELETE CASCADE,
        turn_number INTEGER NOT NULL,
        prompt_hash TEXT NOT NULL,
        prompt_length INTEGER NOT NULL CHECK (prompt_length > 0),
        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'answered', 'qualified', 'refused', 'cancelled', 'failed')),
        answer_json TEXT,
        retrieval_json TEXT,
        citations_json TEXT,
        refusal_code TEXT,
        context_units INTEGER NOT NULL DEFAULT 0 CHECK (context_units >= 0),
        provider_route TEXT NOT NULL DEFAULT 'local_deterministic',
        estimated_cost_usd REAL NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
        created_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE (conversation_id, turn_number)
    )
    """,
    """
    INSERT INTO ask_conversations(id, scope_type, scope_id, created_at, updated_at)
    SELECT id, scope_type, scope_id, created_at, updated_at FROM ask_conversations_legacy_0027
    """,
    """
    INSERT INTO ask_runs(id, conversation_id, turn_number, prompt_hash, prompt_length, status,
                         answer_json, retrieval_json, citations_json, refusal_code,
                         context_units, provider_route, estimated_cost_usd, created_at, completed_at)
    SELECT id, conversation_id, turn_number, prompt_hash, prompt_length, status,
           answer_json, retrieval_json, citations_json, refusal_code,
           context_units, provider_route, estimated_cost_usd, created_at, completed_at
    FROM ask_runs_legacy_0027
    """,
    "DROP TABLE ask_runs_legacy_0027",
    "DROP TABLE ask_conversations_legacy_0027",
    "CREATE INDEX ask_conversations_scope_idx ON ask_conversations(scope_type, scope_id, updated_at DESC, id DESC)",
    "CREATE INDEX ask_runs_conversation_idx ON ask_runs(conversation_id, turn_number DESC, id DESC)",
    "CREATE INDEX ask_runs_status_idx ON ask_runs(status, created_at DESC, id DESC)",
)

MIGRATION_0027_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0027_STATEMENTS).encode("utf-8")
).hexdigest()


# 0028: complete the bounded Ask scope vocabulary with Source records.
MIGRATION_0028_STATEMENTS: tuple[str, ...] = (
    "DROP INDEX ask_runs_status_idx",
    "DROP INDEX ask_runs_conversation_idx",
    "DROP INDEX ask_conversations_scope_idx",
    "ALTER TABLE ask_runs RENAME TO ask_runs_legacy_0028",
    "ALTER TABLE ask_conversations RENAME TO ask_conversations_legacy_0028",
    """
    CREATE TABLE ask_conversations (
        id TEXT PRIMARY KEY,
        scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'story', 'claim', 'evidence', 'document', 'report', 'question', 'research_question', 'subject', 'monitor', 'note', 'entity', 'research_task', 'source')),
        scope_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK ((scope_type = 'global' AND scope_id IS NULL) OR (scope_type <> 'global' AND scope_id IS NOT NULL))
    )
    """,
    """
    CREATE TABLE ask_runs (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES ask_conversations(id) ON DELETE CASCADE,
        turn_number INTEGER NOT NULL,
        prompt_hash TEXT NOT NULL,
        prompt_length INTEGER NOT NULL CHECK (prompt_length > 0),
        status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'answered', 'qualified', 'refused', 'cancelled', 'failed')),
        answer_json TEXT,
        retrieval_json TEXT,
        citations_json TEXT,
        refusal_code TEXT,
        context_units INTEGER NOT NULL DEFAULT 0 CHECK (context_units >= 0),
        provider_route TEXT NOT NULL DEFAULT 'local_deterministic',
        estimated_cost_usd REAL NOT NULL DEFAULT 0 CHECK (estimated_cost_usd >= 0),
        created_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE (conversation_id, turn_number)
    )
    """,
    """
    INSERT INTO ask_conversations(id, scope_type, scope_id, created_at, updated_at)
    SELECT id, scope_type, scope_id, created_at, updated_at FROM ask_conversations_legacy_0028
    """,
    """
    INSERT INTO ask_runs(id, conversation_id, turn_number, prompt_hash, prompt_length, status,
                         answer_json, retrieval_json, citations_json, refusal_code,
                         context_units, provider_route, estimated_cost_usd, created_at, completed_at)
    SELECT id, conversation_id, turn_number, prompt_hash, prompt_length, status,
           answer_json, retrieval_json, citations_json, refusal_code,
           context_units, provider_route, estimated_cost_usd, created_at, completed_at
    FROM ask_runs_legacy_0028
    """,
    "DROP TABLE ask_runs_legacy_0028",
    "DROP TABLE ask_conversations_legacy_0028",
    "CREATE INDEX ask_conversations_scope_idx ON ask_conversations(scope_type, scope_id, updated_at DESC, id DESC)",
    "CREATE INDEX ask_runs_conversation_idx ON ask_runs(conversation_id, turn_number DESC, id DESC)",
    "CREATE INDEX ask_runs_status_idx ON ask_runs(status, created_at DESC, id DESC)",
)

MIGRATION_0028_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0028_STATEMENTS).encode("utf-8")
).hexdigest()


# 0029: make Story organization correctable without rewriting historical
# evidence or Story observations.  The Claim pointer remains the current
# membership authority; the rebuilt history table records every transition.
MIGRATION_0029_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER claims_story_association_immutable",
    "DROP TRIGGER claim_story_assignment_history_insert",
    "DROP TRIGGER claim_story_assignment_history_immutable_update",
    "DROP TRIGGER claim_story_assignment_history_immutable_delete",
    "CREATE TABLE story_corrections ("
    "id TEXT PRIMARY KEY, "
    "operation_type TEXT NOT NULL CHECK (operation_type IN ('reassign','unassign','merge','split','extract','duplicate_dismissal')), "
    "origin TEXT NOT NULL CHECK (origin IN ('human','automatic','import','repair')), "
    "actor TEXT, reason_code TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', "
    "cause_class TEXT NOT NULL CHECK (cause_class IN ('new_evidence','reprocessing','human_correction','administrative')), "
    "caused_by_type TEXT, caused_by_id TEXT, occurred_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}'"
    ")",
    "CREATE INDEX story_corrections_operation_idx ON story_corrections(operation_type, occurred_at, id)",
    "CREATE INDEX story_corrections_cause_idx ON story_corrections(caused_by_type, caused_by_id)",
    """
    CREATE TRIGGER story_corrections_immutable_update
    BEFORE UPDATE ON story_corrections
    BEGIN SELECT RAISE(ABORT, 'Story corrections are append-only'); END
    """,
    """
    CREATE TRIGGER story_corrections_immutable_delete
    BEFORE DELETE ON story_corrections
    BEGIN SELECT RAISE(ABORT, 'Story corrections are append-only'); END
    """,
    "CREATE TABLE story_transition_authorizations ("
    "id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE"
    ")",
    "CREATE INDEX story_transition_authorizations_claim_idx ON story_transition_authorizations(claim_id)",
    "PRAGMA legacy_alter_table = ON",
    "ALTER TABLE claim_story_assignment_history RENAME TO claim_story_assignment_history_legacy_0029",
    """
    CREATE TABLE claim_story_assignment_history (
        id TEXT PRIMARY KEY,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        from_story_id TEXT REFERENCES stories(id) ON DELETE SET NULL,
        to_story_id TEXT REFERENCES stories(id) ON DELETE RESTRICT,
        correction_id TEXT REFERENCES story_corrections(id) ON DELETE SET NULL,
        origin TEXT NOT NULL DEFAULT 'automatic' CHECK (origin IN ('human','automatic','import','repair')),
        reason_code TEXT NOT NULL DEFAULT 'initial_assignment',
        reason TEXT NOT NULL DEFAULT '',
        occurred_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        CHECK (from_story_id IS NOT to_story_id),
        CHECK (from_story_id IS NOT NULL OR to_story_id IS NOT NULL)
    )
    """,
    """
    INSERT INTO claim_story_assignment_history
        (id, claim_id, from_story_id, to_story_id, correction_id, origin,
         reason_code, reason, occurred_at, created_at)
    SELECT h.id, h.claim_id, h.from_story_id, h.to_story_id, NULL,
           CASE WHEN EXISTS (
               SELECT 1 FROM claims c
               WHERE c.id = h.claim_id AND c.article_analysis_id IS NOT NULL
           ) THEN 'automatic' ELSE 'human' END,
           'initial_assignment', h.reason, h.created_at, h.created_at
    FROM claim_story_assignment_history_legacy_0029 h
    """,
    "DROP TABLE claim_story_assignment_history_legacy_0029",
    "PRAGMA legacy_alter_table = OFF",
    "CREATE INDEX claim_story_assignment_history_claim_idx ON claim_story_assignment_history(claim_id, occurred_at, id)",
    "CREATE INDEX claim_story_assignment_history_from_idx ON claim_story_assignment_history(from_story_id, occurred_at, id)",
    "CREATE INDEX claim_story_assignment_history_to_idx ON claim_story_assignment_history(to_story_id, occurred_at, id)",
    "CREATE INDEX claim_story_assignment_history_correction_idx ON claim_story_assignment_history(correction_id, occurred_at, id)",
    """
    CREATE TRIGGER claim_story_assignment_history_immutable_update
    BEFORE UPDATE ON claim_story_assignment_history
    BEGIN SELECT RAISE(ABORT, 'Claim Story assignment history is append-only'); END
    """,
    """
    CREATE TRIGGER claim_story_assignment_history_immutable_delete
    BEFORE DELETE ON claim_story_assignment_history
    BEGIN SELECT RAISE(ABORT, 'Claim Story assignment history is append-only'); END
    """,
    """
    CREATE TRIGGER claims_story_association_controlled
    BEFORE UPDATE OF story_id ON claims
    WHEN OLD.story_id IS NOT NEW.story_id
         AND NOT EXISTS (
             SELECT 1 FROM story_transition_authorizations a
             WHERE a.claim_id = NEW.id
         )
    BEGIN SELECT RAISE(ABORT, 'Claim Story membership requires a controlled correction'); END
    """,
    "DROP INDEX story_entities_entity_idx",
    "ALTER TABLE story_entities RENAME TO story_entities_legacy_0029",
    """
    CREATE TABLE story_entities (
        story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
        entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
        origin TEXT NOT NULL CHECK (origin IN ('user','deterministic','provider','import','backfill')),
        authority TEXT NOT NULL DEFAULT 'derived' CHECK (authority IN ('manual','derived')),
        created_at TEXT NOT NULL,
        PRIMARY KEY (story_id, entity_id, authority)
    )
    """,
    """
    INSERT INTO story_entities(story_id, entity_id, origin, authority, created_at)
    SELECT story_id, entity_id, origin,
           CASE WHEN origin IN ('user','import') THEN 'manual' ELSE 'derived' END,
           created_at
    FROM story_entities_legacy_0029
    """,
    "DROP TABLE story_entities_legacy_0029",
    "CREATE INDEX story_entities_entity_idx ON story_entities(entity_id, story_id, authority)",
    "CREATE INDEX story_entities_story_idx ON story_entities(story_id, authority, entity_id)",
    *tuple(
        f"""
        CREATE TRIGGER search_dirty_story_entities_{operation}
        AFTER {operation.upper()} ON story_entities
        BEGIN
            UPDATE search_index_meta SET dirty = 1, updated_at = CURRENT_TIMESTAMP WHERE id = 1;
        END
        """
        for operation in ("insert", "update", "delete")
    ),
    """
    CREATE TABLE story_lineage (
        id TEXT PRIMARY KEY,
        source_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        target_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        relationship TEXT NOT NULL CHECK (relationship IN ('merged_into','split_into')),
        correction_id TEXT NOT NULL REFERENCES story_corrections(id) ON DELETE RESTRICT,
        created_at TEXT NOT NULL,
        UNIQUE(source_story_id, target_story_id, relationship),
        CHECK(source_story_id <> target_story_id)
    )
    """,
    "CREATE INDEX story_lineage_source_idx ON story_lineage(source_story_id, relationship, created_at, id)",
    "CREATE INDEX story_lineage_target_idx ON story_lineage(target_story_id, relationship, created_at, id)",
    "CREATE INDEX story_lineage_correction_idx ON story_lineage(correction_id, created_at, id)",
    """
    CREATE TRIGGER story_lineage_immutable_update
    BEFORE UPDATE ON story_lineage
    BEGIN SELECT RAISE(ABORT, 'Story lineage is append-only'); END
    """,
    """
    CREATE TRIGGER story_lineage_immutable_delete
    BEFORE DELETE ON story_lineage
    BEGIN SELECT RAISE(ABORT, 'Story lineage is append-only'); END
    """,
    """
    CREATE TABLE story_duplicate_decisions (
        id TEXT PRIMARY KEY,
        source_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        destination_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        evidence_hash TEXT NOT NULL,
        decision TEXT NOT NULL CHECK (decision IN ('dismissed','approved')),
        correction_id TEXT REFERENCES story_corrections(id) ON DELETE SET NULL,
        reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        CHECK(source_story_id <> destination_story_id),
        UNIQUE(source_story_id, destination_story_id, evidence_hash)
    )
    """,
    "CREATE INDEX story_duplicate_decisions_pair_idx ON story_duplicate_decisions(source_story_id, destination_story_id, decision, created_at DESC)",
    """
    CREATE TRIGGER story_duplicate_decisions_immutable_update
    BEFORE UPDATE ON story_duplicate_decisions
    BEGIN SELECT RAISE(ABORT, 'Story duplicate decisions are append-only'); END
    """,
    """
    CREATE TRIGGER story_duplicate_decisions_immutable_delete
    BEFORE DELETE ON story_duplicate_decisions
    BEGIN SELECT RAISE(ABORT, 'Story duplicate decisions are append-only'); END
    """,
    "ALTER TABLE watches ADD COLUMN historical_target_id TEXT",
    "ALTER TABLE watches ADD COLUMN resolution_state TEXT NOT NULL DEFAULT 'active' CHECK (resolution_state IN ('active','needs_review','merged_into_existing'))",
    "ALTER TABLE watches ADD COLUMN resolution_options_json TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE monitors ADD COLUMN historical_target_id TEXT",
    "ALTER TABLE monitors ADD COLUMN resolution_state TEXT NOT NULL DEFAULT 'active' CHECK (resolution_state IN ('active','needs_review','merged_into_existing'))",
    "ALTER TABLE monitors ADD COLUMN resolution_options_json TEXT NOT NULL DEFAULT '[]'",
)

MIGRATION_0029_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0029_STATEMENTS).encode("utf-8")
).hexdigest()


# 0030: manual Claims may be intentionally unassigned.  The Phase 22 check
# accidentally coupled manual Claim provenance to a non-null Story pointer;
# rebuild only the Claims table so Story correction can change organization
# without weakening automatic provenance immutability.
MIGRATION_0030_STATEMENTS: tuple[str, ...] = (
    "DROP TRIGGER claims_automatic_provenance_immutable",
    "DROP TRIGGER claims_accepted_text_immutable",
    "DROP TRIGGER claims_acceptance_immutable",
    "DROP TRIGGER claims_immutable_delete",
    "DROP TRIGGER claims_automatic_insert_pending",
    "DROP TRIGGER claim_evidence_automatic_contract_insert",
    "DROP TRIGGER article_analysis_promotions_verified_contract_insert",
    "DROP TRIGGER claims_story_association_controlled",
    "PRAGMA legacy_alter_table = ON",
    "ALTER TABLE claims RENAME TO claims_legacy_0030",
    """
    CREATE TABLE claims (
        id TEXT PRIMARY KEY,
        story_id TEXT REFERENCES stories(id) ON DELETE CASCADE,
        proposition TEXT NOT NULL,
        proposition_hash TEXT NOT NULL,
        importance TEXT NOT NULL DEFAULT 'relevant' CHECK (importance IN ('major', 'relevant', 'peripheral')),
        state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'supported', 'partially_supported', 'disputed', 'unsubstantiated', 'superseded')),
        supersedes_claim_id TEXT REFERENCES claims(id),
        article_analysis_id TEXT REFERENCES article_analyses(id),
        candidate_claim_index INTEGER,
        created_at TEXT NOT NULL,
        accepted_at TEXT,
        CHECK ((article_analysis_id IS NULL AND candidate_claim_index IS NULL)
            OR (article_analysis_id IS NOT NULL AND candidate_claim_index IS NOT NULL AND candidate_claim_index >= 0)),
        UNIQUE (article_analysis_id, candidate_claim_index)
    )
    """,
    """
    INSERT INTO claims
        (id, story_id, proposition, proposition_hash, importance, state,
         supersedes_claim_id, article_analysis_id, candidate_claim_index,
         created_at, accepted_at)
    SELECT id, story_id, proposition, proposition_hash, importance, state,
           supersedes_claim_id, article_analysis_id, candidate_claim_index,
           created_at, accepted_at
    FROM claims_legacy_0030
    """,
    "DROP TABLE claims_legacy_0030",
    "PRAGMA legacy_alter_table = OFF",
    """
    CREATE TRIGGER claims_accepted_text_immutable
    BEFORE UPDATE OF proposition, proposition_hash ON claims
    WHEN OLD.accepted_at IS NOT NULL
         AND (NEW.proposition IS NOT OLD.proposition OR NEW.proposition_hash IS NOT OLD.proposition_hash)
    BEGIN SELECT RAISE(ABORT, 'accepted claim text is immutable'); END
    """,
    """
    CREATE TRIGGER claims_automatic_provenance_immutable
    BEFORE UPDATE OF story_id, proposition, proposition_hash, article_analysis_id, candidate_claim_index ON claims
    WHEN OLD.article_analysis_id IS NOT NULL
         AND (OLD.proposition IS NOT NEW.proposition
              OR OLD.proposition_hash IS NOT NEW.proposition_hash
              OR OLD.article_analysis_id IS NOT NEW.article_analysis_id
              OR OLD.candidate_claim_index IS NOT NEW.candidate_claim_index)
    BEGIN SELECT RAISE(ABORT, 'automatic claim provenance is immutable'); END
    """,
    """
    CREATE TRIGGER claims_acceptance_immutable
    BEFORE UPDATE OF accepted_at ON claims
    WHEN OLD.accepted_at IS NOT NULL AND NEW.accepted_at IS NOT OLD.accepted_at
    BEGIN SELECT RAISE(ABORT, 'claim acceptance is immutable'); END
    """,
    """
    CREATE TRIGGER claims_immutable_delete
    BEFORE DELETE ON claims
    BEGIN SELECT RAISE(ABORT, 'claims are append-only'); END
    """,
    """
    CREATE TRIGGER claims_automatic_insert_pending
    BEFORE INSERT ON claims
    WHEN NEW.article_analysis_id IS NOT NULL
         AND (NEW.story_id IS NOT NULL OR NEW.state IS NOT 'pending' OR NEW.accepted_at IS NOT NULL)
    BEGIN SELECT RAISE(ABORT, 'automatic Claims must begin pending and without a Story'); END
    """,
    """
    CREATE TRIGGER claims_story_association_controlled
    BEFORE UPDATE OF story_id ON claims
    WHEN OLD.story_id IS NOT NEW.story_id
         AND NOT EXISTS (SELECT 1 FROM story_transition_authorizations a WHERE a.claim_id = NEW.id)
         AND NOT (
             OLD.article_analysis_id IS NOT NULL
             AND (OLD.proposition IS NOT NEW.proposition
                  OR OLD.proposition_hash IS NOT NEW.proposition_hash
                  OR OLD.article_analysis_id IS NOT NEW.article_analysis_id
                  OR OLD.candidate_claim_index IS NOT NEW.candidate_claim_index)
         )
    BEGIN SELECT RAISE(ABORT, 'Claim Story association membership requires a controlled correction'); END
    """,
    """
    CREATE TRIGGER claim_evidence_automatic_contract_insert
    BEFORE INSERT ON claim_evidence
    WHEN EXISTS (SELECT 1 FROM claims c WHERE c.id = NEW.claim_id AND c.article_analysis_id IS NOT NULL)
    BEGIN
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM claims c
            JOIN evidence_spans es ON es.id = NEW.evidence_span_id
            JOIN article_analyses a ON a.id = c.article_analysis_id
            WHERE c.id = NEW.claim_id
              AND es.article_analysis_id IS c.article_analysis_id
              AND es.verification_method IS 'exact_analyzed_slice_v1'
              AND json_extract(es.provenance_json, '$.candidate_claim_index') IS c.candidate_claim_index
              AND a.input_view_version IS es.view_version
              AND a.input_content_hash IS es.view_content_hash
        ) THEN RAISE(ABORT, 'automatic Claims require verified evidence') END;
    END
    """,
    """
    CREATE TRIGGER article_analysis_promotions_verified_contract_insert
    BEFORE INSERT ON article_analysis_promotions
    WHEN NEW.outcome_code = 'verified'
    BEGIN
        SELECT CASE WHEN NEW.claim_id IS NULL
                          OR json_valid(NEW.evidence_span_ids_json) != 1
                          OR json_type(NEW.evidence_span_ids_json) != 'array'
                          OR json_array_length(NEW.evidence_span_ids_json) < 1
                    THEN RAISE(ABORT, 'invalid verified promotion outcome') END;
        SELECT CASE WHEN NOT EXISTS (
            SELECT 1 FROM claims c
            WHERE c.id = NEW.claim_id
              AND c.article_analysis_id = NEW.article_analysis_id
              AND c.candidate_claim_index = NEW.candidate_claim_index
              AND c.story_id IS NULL
        ) THEN RAISE(ABORT, 'verified promotion Claim does not match analysis') END;
        SELECT CASE WHEN EXISTS (
            SELECT 1 FROM json_each(NEW.evidence_span_ids_json) ids
            LEFT JOIN evidence_spans es ON es.id = ids.value
            LEFT JOIN claim_evidence ce ON ce.claim_id = NEW.claim_id AND ce.evidence_span_id = ids.value
            WHERE es.id IS NULL OR es.article_analysis_id IS NOT NEW.article_analysis_id
               OR es.verification_method IS NOT 'exact_analyzed_slice_v1'
               OR ce.id IS NULL
        ) THEN RAISE(ABORT, 'verified promotion evidence does not match analysis') END;
    END
    """,
)

MIGRATION_0030_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0030_STATEMENTS).encode("utf-8")
).hexdigest()


# 0031: persist bounded duplicate suggestion identity separately from the
# append-only human approval/dismissal decisions.
MIGRATION_0031_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE story_duplicate_suggestions (
        id TEXT PRIMARY KEY,
        source_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        destination_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        evidence_hash TEXT NOT NULL,
        score REAL NOT NULL CHECK (score >= 0.0 AND score <= 1.0),
        explanation_json TEXT NOT NULL DEFAULT '{}',
        resolver_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        CHECK(source_story_id <> destination_story_id),
        UNIQUE(source_story_id, destination_story_id, evidence_hash)
    )
    """,
    "CREATE INDEX story_duplicate_suggestions_pair_idx ON story_duplicate_suggestions(source_story_id, destination_story_id, created_at DESC)",
    "CREATE INDEX story_duplicate_suggestions_hash_idx ON story_duplicate_suggestions(evidence_hash, created_at DESC)",
    """
    CREATE TRIGGER story_duplicate_suggestions_immutable_update
    BEFORE UPDATE ON story_duplicate_suggestions
    BEGIN SELECT RAISE(ABORT, 'Story duplicate suggestions are append-only'); END
    """,
    """
    CREATE TRIGGER story_duplicate_suggestions_immutable_delete
    BEFORE DELETE ON story_duplicate_suggestions
    BEGIN SELECT RAISE(ABORT, 'Story duplicate suggestions are append-only'); END
    """,
)

MIGRATION_0031_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0031_STATEMENTS).encode("utf-8")
).hexdigest()


# 0032: Phase 28 derived intelligence and explicit split-target resolution.
# These tables reference canonical evidence/domain rows but never replace them
# as factual authority. Projection rows are rebuildable; human decisions and
# append-only histories remain separately identifiable.
MIGRATION_0032_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE story_target_resolution_history (
        id TEXT PRIMARY KEY,
        target_kind TEXT NOT NULL CHECK (target_kind IN ('watch', 'monitor')),
        target_id TEXT NOT NULL,
        historical_story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE RESTRICT,
        selected_story_ids_json TEXT NOT NULL DEFAULT '[]',
        resolution TEXT NOT NULL CHECK (resolution IN ('selected', 'disabled')),
        actor TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX story_target_resolution_history_target_idx ON story_target_resolution_history(target_kind, target_id, created_at DESC, id)",
    """
    CREATE TABLE coverage_runs (
        id TEXT PRIMARY KEY,
        target_type TEXT NOT NULL CHECK (target_type IN ('watch', 'research_question', 'story', 'ask', 'source')),
        target_id TEXT NOT NULL,
        target_version TEXT NOT NULL DEFAULT '',
        window_start TEXT NOT NULL,
        window_end TEXT NOT NULL,
        policy_version TEXT NOT NULL,
        included_sources_json TEXT NOT NULL DEFAULT '[]',
        excluded_sources_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'partial', 'failed')),
        causing_job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    "CREATE INDEX coverage_runs_target_idx ON coverage_runs(target_type, target_id, created_at DESC, id)",
    """
    CREATE TABLE coverage_items (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES coverage_runs(id) ON DELETE CASCADE,
        item_key TEXT NOT NULL,
        channel_type TEXT NOT NULL,
        source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
        source_class TEXT NOT NULL DEFAULT '',
        required INTEGER NOT NULL DEFAULT 1 CHECK (required IN (0, 1)),
        state TEXT NOT NULL CHECK (state IN ('observed', 'not_found', 'not_observed', 'not_searched', 'failed_acquisition', 'out_of_scope', 'stale')),
        observation_refs_json TEXT NOT NULL DEFAULT '[]',
        reason TEXT NOT NULL DEFAULT '',
        observed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(run_id, item_key)
    )
    """,
    "CREATE INDEX coverage_items_state_idx ON coverage_items(run_id, state, required, item_key)",
    "CREATE INDEX coverage_items_source_idx ON coverage_items(source_id, state, updated_at)",
    """
    CREATE TABLE coverage_summaries (
        run_id TEXT PRIMARY KEY REFERENCES coverage_runs(id) ON DELETE CASCADE,
        expected_count INTEGER NOT NULL CHECK (expected_count >= 0),
        required_count INTEGER NOT NULL CHECK (required_count >= 0),
        observed_count INTEGER NOT NULL CHECK (observed_count >= 0),
        complete_count INTEGER NOT NULL CHECK (complete_count >= 0),
        completeness REAL NOT NULL CHECK (completeness >= 0.0 AND completeness <= 1.0),
        qualified_negative INTEGER NOT NULL DEFAULT 0 CHECK (qualified_negative IN (0, 1)),
        state_counts_json TEXT NOT NULL DEFAULT '{}',
        explanation_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE evidence_families (
        id TEXT PRIMARY KEY,
        family_key TEXT NOT NULL UNIQUE,
        label TEXT NOT NULL DEFAULT '',
        origin TEXT NOT NULL CHECK (origin IN ('deterministic', 'provider', 'human', 'import')),
        authority TEXT NOT NULL CHECK (authority IN ('derived', 'reviewed')),
        algorithm_version TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE evidence_family_members (
        family_id TEXT NOT NULL REFERENCES evidence_families(id) ON DELETE CASCADE,
        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
        source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
        relationship TEXT NOT NULL DEFAULT 'member',
        confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
        created_at TEXT NOT NULL,
        PRIMARY KEY(family_id, document_id)
    )
    """,
    "CREATE INDEX evidence_family_members_document_idx ON evidence_family_members(document_id, family_id)",
    """
    CREATE TABLE evidence_fragility_analyses (
        id TEXT PRIMARY KEY,
        target_type TEXT NOT NULL CHECK (target_type IN ('claim', 'story', 'report', 'ask')),
        target_id TEXT NOT NULL,
        input_fingerprint TEXT NOT NULL,
        claim_ids_json TEXT NOT NULL DEFAULT '[]',
        distinct_source_count INTEGER NOT NULL DEFAULT 0 CHECK (distinct_source_count >= 0),
        lineage_group_count INTEGER NOT NULL DEFAULT 0 CHECK (lineage_group_count >= 0),
        evidence_family_count INTEGER NOT NULL DEFAULT 0 CHECK (evidence_family_count >= 0),
        fragility_score REAL NOT NULL CHECK (fragility_score >= 0.0 AND fragility_score <= 1.0),
        support_paths_json TEXT NOT NULL DEFAULT '[]',
        explanation_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        UNIQUE(target_type, target_id, input_fingerprint)
    )
    """,
    """
    CREATE TABLE blind_spot_suggestions (
        id TEXT PRIMARY KEY,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        source_class TEXT NOT NULL,
        coverage_run_id TEXT REFERENCES coverage_runs(id) ON DELETE SET NULL,
        priority REAL NOT NULL CHECK (priority >= 0.0 AND priority <= 1.0),
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'dismissed', 'used')),
        created_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by TEXT,
        UNIQUE(target_type, target_id, source_class, coverage_run_id)
    )
    """,
    """
    CREATE TABLE attention_items (
        id TEXT PRIMARY KEY,
        object_type TEXT NOT NULL,
        object_id TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        importance_score REAL NOT NULL CHECK (importance_score >= 0.0 AND importance_score <= 1.0),
        state TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'seen', 'dismissed')),
        source_fingerprint TEXT NOT NULL,
        explanation_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(object_type, object_id, reason_code, source_fingerprint)
    )
    """,
    "CREATE INDEX attention_items_rank_idx ON attention_items(state, importance_score DESC, updated_at DESC, id)",
    """
    CREATE TABLE attention_feedback (
        id TEXT PRIMARY KEY,
        attention_id TEXT NOT NULL REFERENCES attention_items(id) ON DELETE CASCADE,
        feedback TEXT NOT NULL CHECK (feedback IN ('useful', 'not_important', 'already_knew', 'needs_investigation', 'mute_pattern')),
        actor TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE hypotheses (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
        statement TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'rejected', 'archived')),
        origin TEXT NOT NULL CHECK (origin IN ('human', 'deterministic', 'provider')),
        provider_route TEXT NOT NULL DEFAULT 'local_deterministic',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        approved_at TEXT,
        approved_by TEXT
    )
    """,
    "CREATE INDEX hypotheses_question_idx ON hypotheses(question_id, status, updated_at DESC, id)",
    """
    CREATE TABLE hypothesis_claim_links (
        id TEXT PRIMARY KEY,
        hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
        claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
        relationship TEXT NOT NULL CHECK (relationship IN ('supports', 'contradicts', 'discriminates')),
        created_at TEXT NOT NULL,
        UNIQUE(hypothesis_id, claim_id, relationship)
    )
    """,
    """
    CREATE TABLE hypothesis_gaps (
        id TEXT PRIMARY KEY,
        hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'approved', 'used', 'dismissed')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(hypothesis_id, description)
    )
    """,
    """
    CREATE TABLE hypothesis_history (
        id TEXT PRIMARY KEY,
        hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
        from_status TEXT,
        to_status TEXT NOT NULL,
        actor TEXT,
        reason TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX hypothesis_history_idx ON hypothesis_history(hypothesis_id, created_at, id)",
)

MIGRATION_0032_CHECKSUM = hashlib.sha256(
    "\n".join(MIGRATION_0032_STATEMENTS).encode("utf-8")
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
        # Migrations 0021 and 0022 perform SQLite's documented table-rebuild
        # pattern. Foreign-key enforcement must be off before BEGIN so child
        # definitions remain bound to replacement canonical table names;
        # integrity is checked before returning.
        conn.execute("PRAGMA foreign_keys = OFF")
        with storage.write_tx(conn):
            _ensure_ledger(conn)
            existing = {
                row[0]
                for row in conn.execute("SELECT version FROM schema_migrations")
            }
            migrations = {
                1: MIGRATION_0001_STATEMENTS,
                2: MIGRATION_0002_STATEMENTS,
                3: MIGRATION_0003_STATEMENTS,
                4: MIGRATION_0004_STATEMENTS,
                5: MIGRATION_0005_STATEMENTS,
                6: MIGRATION_0006_STATEMENTS,
                7: MIGRATION_0007_STATEMENTS,
                8: MIGRATION_0008_STATEMENTS,
                9: MIGRATION_0009_STATEMENTS,
                10: MIGRATION_0010_STATEMENTS,
                11: MIGRATION_0011_STATEMENTS,
                12: MIGRATION_0012_STATEMENTS,
                13: MIGRATION_0013_STATEMENTS,
                14: MIGRATION_0014_STATEMENTS,
                15: MIGRATION_0015_STATEMENTS,
                16: MIGRATION_0016_STATEMENTS,
                17: MIGRATION_0017_STATEMENTS,
                18: MIGRATION_0018_STATEMENTS,
                19: MIGRATION_0019_STATEMENTS,
                20: MIGRATION_0020_STATEMENTS,
                21: MIGRATION_0021_STATEMENTS,
                22: MIGRATION_0022_STATEMENTS,
                23: MIGRATION_0023_STATEMENTS,
                24: MIGRATION_0024_STATEMENTS,
                25: MIGRATION_0025_STATEMENTS,
                26: MIGRATION_0026_STATEMENTS,
                27: MIGRATION_0027_STATEMENTS,
                28: MIGRATION_0028_STATEMENTS,
                29: MIGRATION_0029_STATEMENTS,
                30: MIGRATION_0030_STATEMENTS,
                31: MIGRATION_0031_STATEMENTS,
                32: MIGRATION_0032_STATEMENTS,
            }
            for version, statements in migrations.items():
                if version in existing:
                    continue
                for statement in statements:
                    conn.execute(statement)
                now = utc_now()
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, now),
                )
                if version == 1:
                    conn.execute(
                        "INSERT INTO app_meta(key, value) VALUES ('schema_version', '1')"
                    )
                    conn.execute(
                        "INSERT INTO app_meta(key, value) VALUES ('schema_seeded_at', ?)",
                        (now,),
                    )
                else:
                    conn.execute(
                        "UPDATE app_meta SET value = ? WHERE key = 'schema_version'",
                        (str(version),),
                    )
                applied.append(version)
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise sqlite3.IntegrityError("migration produced foreign-key violations")
        conn.execute("PRAGMA foreign_keys = ON")
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
