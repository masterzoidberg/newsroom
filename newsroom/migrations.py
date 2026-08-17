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
