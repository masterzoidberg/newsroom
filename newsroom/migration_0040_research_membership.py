"""Schema 40: immutable Research scope and Source membership history.

This migration is intentionally additive.  ``watches`` remains the Research
identity, ``watch_sources`` remains the current projection, and existing
Monitor scope snapshots remain the semantic execution authority.  The new
records explain how the current projection came to be without manufacturing
legacy dates or merging Source identities.
"""
from __future__ import annotations


MIGRATION_0040_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE watches ADD COLUMN original_intent TEXT",
    "ALTER TABLE watches ADD COLUMN current_scope_revision_id TEXT",
    """
    CREATE TABLE watch_scope_revisions (
        id TEXT PRIMARY KEY,
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        revision_number INTEGER NOT NULL CHECK (revision_number > 0),
        intent TEXT NOT NULL,
        focus_areas_json TEXT NOT NULL DEFAULT '[]',
        terms_json TEXT NOT NULL DEFAULT '[]',
        exclusions_json TEXT NOT NULL DEFAULT '[]',
        scope_json TEXT NOT NULL DEFAULT '{}',
        monitor_scope_json TEXT NOT NULL DEFAULT '{}',
        semantic_eligibility INTEGER NOT NULL DEFAULT 1 CHECK (semantic_eligibility IN (0, 1)),
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        target_snapshot_json TEXT NOT NULL DEFAULT '{}',
        origin TEXT NOT NULL CHECK (origin IN (
            'legacy_current','create','approved','target_change','target_scope_change',
            'focus_change','intent_change','system'
        )),
        actor TEXT,
        provenance_status TEXT NOT NULL CHECK (provenance_status IN ('exact','inferred','unknown')),
        provenance_detail TEXT NOT NULL DEFAULT '',
        previous_revision_id TEXT REFERENCES watch_scope_revisions(id) ON DELETE RESTRICT,
        approved_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(watch_id, revision_number)
    )
    """,
    "CREATE INDEX watch_scope_revisions_watch_idx ON watch_scope_revisions(watch_id, revision_number DESC, id)",
    """
    CREATE TRIGGER watch_scope_revisions_immutable_update
    BEFORE UPDATE ON watch_scope_revisions
    BEGIN
        SELECT RAISE(ABORT, 'Watch scope revisions are append-only');
    END
    """,
    """
    CREATE TRIGGER watch_scope_revisions_immutable_delete
    BEFORE DELETE ON watch_scope_revisions
    BEGIN
        SELECT RAISE(ABORT, 'Watch scope revisions are append-only');
    END
    """,
    """
    CREATE TABLE watch_scope_refresh_requests (
        id TEXT PRIMARY KEY,
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        origin TEXT NOT NULL,
        actor TEXT,
        provenance_status TEXT NOT NULL CHECK (provenance_status IN ('exact','inferred','unknown')),
        provenance_detail TEXT NOT NULL DEFAULT '',
        force_revision INTEGER NOT NULL DEFAULT 0 CHECK (force_revision IN (0, 1)),
        requested_at TEXT NOT NULL
    )
    """,
    """
    CREATE VIEW watch_monitor_scope_components AS
    WITH base_scope(watch_id, bucket, seq, value) AS (
        SELECT w.id, 'exact', tt.rowid, tt.term
        FROM watches w JOIN topic_terms tt ON w.target_type = 'topic' AND tt.topic_id = w.target_id
        WHERE tt.term_type = 'include' AND tt.concept_kind = 'term'
        UNION ALL
        SELECT w.id, 'vocabulary', tt.rowid, tt.term
        FROM watches w JOIN topic_terms tt ON w.target_type = 'topic' AND tt.topic_id = w.target_id
        WHERE tt.term_type = 'alias'
        UNION ALL
        SELECT w.id, 'entities', tt.rowid, tt.term
        FROM watches w JOIN topic_terms tt ON w.target_type = 'topic' AND tt.topic_id = w.target_id
        WHERE tt.term_type = 'entity'
        UNION ALL
        SELECT w.id, 'concepts', tt.rowid, tt.term
        FROM watches w JOIN topic_terms tt ON w.target_type = 'topic' AND tt.topic_id = w.target_id
        WHERE tt.concept_kind = 'related_concept'
        UNION ALL
        SELECT w.id, 'semantic', tt.rowid, tt.term
        FROM watches w JOIN topic_terms tt ON w.target_type = 'topic' AND tt.topic_id = w.target_id
        WHERE tt.term_type <> 'exclude'
        UNION ALL
        SELECT w.id, 'exclusions', tt.rowid, tt.term
        FROM watches w JOIN topic_terms tt ON w.target_type = 'topic' AND tt.topic_id = w.target_id
        WHERE tt.term_type = 'exclude'
        UNION ALL
        SELECT w.id, 'exact', 0, s.canonical_name
        FROM watches w JOIN subjects s ON w.target_type = 'subject' AND s.id = w.target_id
        UNION ALL
        SELECT w.id, 'entities', 0, s.canonical_name
        FROM watches w JOIN subjects s ON w.target_type = 'subject' AND s.id = w.target_id
        UNION ALL
        SELECT w.id, 'vocabulary', sa.rowid, sa.alias
        FROM watches w JOIN subject_aliases sa ON w.target_type = 'subject' AND sa.subject_id = w.target_id
        UNION ALL
        SELECT w.id, 'exact', 0, sr.headline
        FROM watches w JOIN story_revisions sr ON w.target_type = 'story' AND sr.story_id = w.target_id
        WHERE sr.revision_number = (SELECT MAX(x.revision_number) FROM story_revisions x WHERE x.story_id = sr.story_id)
        UNION ALL
        SELECT w.id, 'concepts', 1, sr.summary
        FROM watches w JOIN story_revisions sr ON w.target_type = 'story' AND sr.story_id = w.target_id
        WHERE sr.revision_number = (SELECT MAX(x.revision_number) FROM story_revisions x WHERE x.story_id = sr.story_id)
          AND TRIM(sr.summary) <> ''
        UNION ALL
        SELECT w.id, 'concepts', 2, sr.why_it_matters
        FROM watches w JOIN story_revisions sr ON w.target_type = 'story' AND sr.story_id = w.target_id
        WHERE sr.revision_number = (SELECT MAX(x.revision_number) FROM story_revisions x WHERE x.story_id = sr.story_id)
          AND TRIM(sr.why_it_matters) <> ''
        UNION ALL
        SELECT w.id, 'semantic', 0, sr.headline
        FROM watches w JOIN story_revisions sr ON w.target_type = 'story' AND sr.story_id = w.target_id
        WHERE sr.revision_number = (SELECT MAX(x.revision_number) FROM story_revisions x WHERE x.story_id = sr.story_id)
        UNION ALL
        SELECT w.id, 'semantic', 1, sr.summary
        FROM watches w JOIN story_revisions sr ON w.target_type = 'story' AND sr.story_id = w.target_id
        WHERE sr.revision_number = (SELECT MAX(x.revision_number) FROM story_revisions x WHERE x.story_id = sr.story_id)
          AND TRIM(sr.summary) <> ''
        UNION ALL
        SELECT w.id, 'semantic', 2, sr.why_it_matters
        FROM watches w JOIN story_revisions sr ON w.target_type = 'story' AND sr.story_id = w.target_id
        WHERE sr.revision_number = (SELECT MAX(x.revision_number) FROM story_revisions x WHERE x.story_id = sr.story_id)
          AND TRIM(sr.why_it_matters) <> ''
        UNION ALL
        SELECT w.id, 'exact', 0, rq.question
        FROM watches w JOIN research_questions rq ON w.target_type = 'research_question' AND rq.id = w.target_id
        UNION ALL
        SELECT w.id, 'exact', 0, s.name
        FROM watches w JOIN sources s ON w.target_type = 'source' AND s.id = w.target_id
        WHERE TRIM(s.name) <> ''
        UNION ALL
        SELECT w.id, 'exact', 1, s.slug
        FROM watches w JOIN sources s ON w.target_type = 'source' AND s.id = w.target_id
        WHERE TRIM(s.slug) <> ''
        UNION ALL
        SELECT w.id, 'exact', 2, s.domain
        FROM watches w JOIN sources s ON w.target_type = 'source' AND s.id = w.target_id
        WHERE s.domain IS NOT NULL AND TRIM(s.domain) <> ''
    ),
    overlay(watch_id, bucket, seq, value) AS (
        SELECT wv.watch_id, 'vocabulary', 1000000000 + wv.rowid, wv.term
        FROM watch_vocabulary wv
        WHERE wv.status = 'approved' AND wv.enabled = 1 AND wv.kind <> 'exclude'
        UNION ALL
        SELECT wv.watch_id, 'semantic', 1000000000 + wv.rowid, wv.term
        FROM watch_vocabulary wv
        WHERE wv.status = 'approved' AND wv.enabled = 1 AND wv.kind <> 'exclude'
        UNION ALL
        SELECT wv.watch_id, 'exclusions', 1000000000 + wv.rowid, wv.term
        FROM watch_vocabulary wv
        WHERE wv.status = 'approved' AND wv.enabled = 1 AND wv.kind = 'exclude'
    ),
    scope AS (
        SELECT * FROM base_scope WHERE TRIM(value) <> ''
        UNION ALL
        SELECT * FROM overlay WHERE TRIM(value) <> ''
    )
    SELECT
        w.id AS watch_id,
        COALESCE((SELECT json_group_array(value) FROM (
            SELECT value FROM scope s WHERE s.watch_id = w.id AND s.bucket = 'exact' ORDER BY seq
        )), '[]') AS exact_terms_json,
        COALESCE((SELECT json_group_array(value) FROM (
            SELECT value FROM scope s WHERE s.watch_id = w.id AND s.bucket = 'vocabulary'
            GROUP BY value ORDER BY MIN(seq)
        )), '[]') AS vocabulary_json,
        COALESCE((SELECT json_group_array(value) FROM (
            SELECT value FROM scope s WHERE s.watch_id = w.id AND s.bucket = 'entities' ORDER BY seq
        )), '[]') AS entities_json,
        COALESCE((SELECT json_group_array(value) FROM (
            SELECT value FROM scope s WHERE s.watch_id = w.id AND s.bucket = 'concepts' ORDER BY seq
        )), '[]') AS concepts_json,
        COALESCE((SELECT json_group_array(value) FROM (
            SELECT value FROM scope s WHERE s.watch_id = w.id AND s.bucket = 'semantic'
            GROUP BY value ORDER BY MIN(seq)
        )), '[]') AS semantic_terms_json,
        COALESCE((SELECT json_group_array(value) FROM (
            SELECT value FROM scope s WHERE s.watch_id = w.id AND s.bucket = 'exclusions'
            GROUP BY value ORDER BY MIN(seq)
        )), '[]') AS exclusions_json,
        COALESCE((SELECT json_group_array(value) FROM (
            SELECT value FROM scope s WHERE s.watch_id = w.id AND s.bucket <> 'exclusions'
            GROUP BY value ORDER BY MIN(seq), value
        )), '[]') AS revision_terms_json
    FROM watches w
    """,
    """
    CREATE VIEW watch_scope_current AS
    SELECT
        w.id AS watch_id,
        COALESCE(NULLIF(w.original_intent, ''), w.name) AS intent,
        '[]' AS focus_areas_json,
        c.revision_terms_json AS terms_json,
        c.exclusions_json AS exclusions_json,
        CASE WHEN w.target_type = 'source' THEN 0 ELSE 1 END AS semantic_eligibility,
        w.target_type,
        w.target_id,
        CASE w.target_type
            WHEN 'topic' THEN COALESCE((SELECT json_object('id', t.id, 'name', t.name, 'description', t.description) FROM topics t WHERE t.id = w.target_id), '{}')
            WHEN 'subject' THEN COALESCE((SELECT json_object('id', s.id, 'canonical_name', s.canonical_name, 'description', s.description) FROM subjects s WHERE s.id = w.target_id), '{}')
            WHEN 'story' THEN COALESCE((SELECT json_object('id', sr.story_id, 'revision_id', sr.id, 'revision_number', sr.revision_number, 'headline', sr.headline, 'summary', sr.summary, 'why_it_matters', sr.why_it_matters) FROM story_revisions sr WHERE sr.story_id = w.target_id ORDER BY sr.revision_number DESC, sr.id DESC LIMIT 1), '{}')
            WHEN 'research_question' THEN COALESCE((SELECT json_object('id', rq.id, 'question', rq.question, 'status', rq.status) FROM research_questions rq WHERE rq.id = w.target_id), '{}')
            WHEN 'source' THEN COALESCE((SELECT json_object('id', s.id, 'name', s.name, 'homepage_url', s.homepage_url, 'feed_url', s.feed_url, 'source_kind', s.source_kind) FROM sources s WHERE s.id = w.target_id), '{}')
            ELSE '{}'
        END AS target_snapshot_json,
        json_object(
            'concepts', json(c.concepts_json),
            'entities', json(c.entities_json),
            'exact_terms', json(c.exact_terms_json),
            'exclusions', json(c.exclusions_json),
            'semantic_terms', json(c.semantic_terms_json),
            'semantic_threshold', 0.6,
            'vocabulary', json(c.vocabulary_json)
        ) AS monitor_scope_json
    FROM watches w
    JOIN watch_monitor_scope_components c ON c.watch_id = w.id
    """,
    """
    CREATE TRIGGER watch_scope_revisions_set_current
    AFTER INSERT ON watch_scope_revisions
    BEGIN
        UPDATE watches SET current_scope_revision_id = NEW.id WHERE id = NEW.watch_id;
    END
    """,
    """
    CREATE TRIGGER watch_scope_refresh_apply
    AFTER INSERT ON watch_scope_refresh_requests
    BEGIN
        INSERT INTO watch_scope_revisions(
            id, watch_id, revision_number, intent, focus_areas_json,
            terms_json, exclusions_json, scope_json, monitor_scope_json,
            semantic_eligibility, target_type, target_id, target_snapshot_json,
            origin, actor, provenance_status, provenance_detail,
            previous_revision_id, approved_at, created_at
        )
        SELECT
            'wsr_' || lower(hex(randomblob(16))), c.watch_id,
            COALESCE((SELECT MAX(r.revision_number) FROM watch_scope_revisions r WHERE r.watch_id = c.watch_id), 0) + 1,
            c.intent, c.focus_areas_json, c.terms_json, c.exclusions_json,
            json_object(
                'focus_areas', json(c.focus_areas_json),
                'semantic_eligibility', json(CASE WHEN c.semantic_eligibility = 1 THEN 'true' ELSE 'false' END),
                'target_id', c.target_id,
                'target_snapshot', json(c.target_snapshot_json),
                'target_type', c.target_type,
                'terms', json(c.terms_json),
                'exclusions', json(c.exclusions_json)
            ),
            c.monitor_scope_json, c.semantic_eligibility, c.target_type, c.target_id,
            c.target_snapshot_json, NEW.origin, NEW.actor, NEW.provenance_status,
            NEW.provenance_detail,
            (SELECT r.id FROM watch_scope_revisions r WHERE r.watch_id = c.watch_id ORDER BY r.revision_number DESC, r.id DESC LIMIT 1),
            NEW.requested_at, NEW.requested_at
        FROM watch_scope_current c
        WHERE c.watch_id = NEW.watch_id
          AND (
            NEW.force_revision = 1
            OR NOT EXISTS (SELECT 1 FROM watch_scope_revisions r WHERE r.watch_id = c.watch_id)
            OR EXISTS (
                SELECT 1 FROM watch_scope_revisions r
                WHERE r.watch_id = c.watch_id
                  AND r.revision_number = (SELECT MAX(x.revision_number) FROM watch_scope_revisions x WHERE x.watch_id = c.watch_id)
                  AND (
                    r.intent IS NOT c.intent OR r.terms_json IS NOT c.terms_json
                    OR r.exclusions_json IS NOT c.exclusions_json
                    OR r.target_type IS NOT c.target_type OR r.target_id IS NOT c.target_id
                    OR r.target_snapshot_json IS NOT c.target_snapshot_json
                    OR r.semantic_eligibility IS NOT c.semantic_eligibility
                  )
            )
          );

        INSERT INTO monitor_scope_history(id, monitor_id, version, scope_json, change_type, changed_by, created_at)
        SELECT
            'scopehist_' || lower(hex(randomblob(16))), ws.monitor_id,
            COALESCE((SELECT MAX(h.version) FROM monitor_scope_history h WHERE h.monitor_id = ws.monitor_id), 0) + 1,
            c.monitor_scope_json, 'approved', NEW.actor, NEW.requested_at
        FROM watch_sources ws
        JOIN watch_scope_current c ON c.watch_id = ws.watch_id
        WHERE ws.watch_id = NEW.watch_id
          AND NOT EXISTS (
              SELECT 1 FROM monitor_scope_history h
              WHERE h.monitor_id = ws.monitor_id
                AND h.version = (SELECT MAX(h2.version) FROM monitor_scope_history h2 WHERE h2.monitor_id = ws.monitor_id)
                AND h.scope_json = c.monitor_scope_json
          );

        DELETE FROM watch_scope_refresh_requests WHERE id = NEW.id;
    END
    """,
    """
    UPDATE watches
    SET original_intent = COALESCE(
        NULLIF(original_intent, ''),
        CASE target_type
            WHEN 'topic' THEN (SELECT COALESCE(NULLIF(t.description, ''), t.name) FROM topics t WHERE t.id = watches.target_id)
            WHEN 'subject' THEN (SELECT COALESCE(NULLIF(s.description, ''), s.canonical_name) FROM subjects s WHERE s.id = watches.target_id)
            WHEN 'story' THEN (SELECT COALESCE(NULLIF(sr.summary, ''), sr.headline) FROM story_revisions sr WHERE sr.story_id = watches.target_id ORDER BY sr.revision_number DESC, sr.id DESC LIMIT 1)
            WHEN 'research_question' THEN (SELECT rq.question FROM research_questions rq WHERE rq.id = watches.target_id)
            WHEN 'source' THEN (SELECT s.name FROM sources s WHERE s.id = watches.target_id)
            ELSE name
        END,
        name
    )
    """,
    """
    INSERT INTO watch_scope_refresh_requests(
        id, watch_id, origin, actor, provenance_status, provenance_detail,
        force_revision, requested_at
    )
    SELECT
        'wsrq_' || lower(hex(randomblob(16))), id, 'legacy_current', NULL,
        'inferred', 'Current scope reconstructed at schema-40 upgrade; original approval time is unknown.',
        1, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    FROM watches
    ORDER BY id
    """,
    """
    CREATE TABLE watch_lifecycle_events (
        id TEXT PRIMARY KEY,
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL CHECK (event_type IN ('created','status_changed','target_changed','resolution_changed','legacy_current')),
        from_status TEXT,
        to_status TEXT,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        historical_target_id TEXT,
        resolution_state TEXT NOT NULL,
        resolution_options_json TEXT NOT NULL DEFAULT '[]',
        actor TEXT,
        reason TEXT NOT NULL DEFAULT '',
        provenance_status TEXT NOT NULL CHECK (provenance_status IN ('exact','inferred','unknown')),
        occurred_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX watch_lifecycle_events_watch_idx ON watch_lifecycle_events(watch_id, occurred_at, id)",
    """
    CREATE TRIGGER watch_lifecycle_events_immutable_update
    BEFORE UPDATE ON watch_lifecycle_events
    BEGIN SELECT RAISE(ABORT, 'Watch lifecycle history is append-only'); END
    """,
    """
    CREATE TRIGGER watch_lifecycle_events_immutable_delete
    BEFORE DELETE ON watch_lifecycle_events
    BEGIN SELECT RAISE(ABORT, 'Watch lifecycle history is append-only'); END
    """,
    """
    INSERT INTO watch_lifecycle_events(
        id, watch_id, event_type, from_status, to_status, target_type, target_id,
        historical_target_id, resolution_state, resolution_options_json, actor,
        reason, provenance_status, occurred_at, created_at
    )
    SELECT
        'wle_' || lower(hex(randomblob(16))), id, 'legacy_current', NULL, status,
        target_type, target_id, historical_target_id, resolution_state,
        resolution_options_json, NULL,
        'Current Watch state reconstructed at schema-40 upgrade; prior transition time is unknown.',
        'inferred', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    FROM watches
    ORDER BY id
    """,
    """
    CREATE TRIGGER watches_research_history_insert
    AFTER INSERT ON watches
    BEGIN
        UPDATE watches
        SET original_intent = COALESCE(
            NULLIF(NEW.original_intent, ''),
            CASE NEW.target_type
                WHEN 'topic' THEN (SELECT COALESCE(NULLIF(t.description, ''), t.name) FROM topics t WHERE t.id = NEW.target_id)
                WHEN 'subject' THEN (SELECT COALESCE(NULLIF(s.description, ''), s.canonical_name) FROM subjects s WHERE s.id = NEW.target_id)
                WHEN 'story' THEN (SELECT COALESCE(NULLIF(sr.summary, ''), sr.headline) FROM story_revisions sr WHERE sr.story_id = NEW.target_id ORDER BY sr.revision_number DESC, sr.id DESC LIMIT 1)
                WHEN 'research_question' THEN (SELECT rq.question FROM research_questions rq WHERE rq.id = NEW.target_id)
                WHEN 'source' THEN (SELECT s.name FROM sources s WHERE s.id = NEW.target_id)
                ELSE NEW.name
            END,
            NEW.name
        ) WHERE id = NEW.id;
        INSERT INTO watch_scope_refresh_requests(
            id, watch_id, origin, actor, provenance_status, provenance_detail,
            force_revision, requested_at
        ) VALUES (
            'wsrq_' || lower(hex(randomblob(16))), NEW.id, 'create', NULL,
            'exact', 'Watch scope captured in the creation transaction.', 1, NEW.created_at
        );
        INSERT INTO watch_lifecycle_events(
            id, watch_id, event_type, from_status, to_status, target_type, target_id,
            historical_target_id, resolution_state, resolution_options_json, actor,
            reason, provenance_status, occurred_at, created_at
        ) VALUES (
            'wle_' || lower(hex(randomblob(16))), NEW.id, 'created', NULL, NEW.status,
            NEW.target_type, NEW.target_id, NEW.historical_target_id, NEW.resolution_state,
            NEW.resolution_options_json, NULL, 'Watch created', 'exact', NEW.created_at, NEW.created_at
        );
    END
    """,
    """
    CREATE TRIGGER watches_research_history_status
    AFTER UPDATE OF status ON watches
    WHEN OLD.status IS NOT NEW.status
    BEGIN
        INSERT INTO watch_lifecycle_events(
            id, watch_id, event_type, from_status, to_status, target_type, target_id,
            historical_target_id, resolution_state, resolution_options_json, actor,
            reason, provenance_status, occurred_at, created_at
        ) VALUES (
            'wle_' || lower(hex(randomblob(16))), NEW.id, 'status_changed', OLD.status, NEW.status,
            NEW.target_type, NEW.target_id, NEW.historical_target_id, NEW.resolution_state,
            NEW.resolution_options_json, NULL, 'Watch status changed', 'exact', NEW.updated_at, NEW.updated_at
        );
    END
    """,
    """
    CREATE TRIGGER watches_research_history_target
    AFTER UPDATE OF target_type, target_id ON watches
    WHEN OLD.target_type IS NOT NEW.target_type OR OLD.target_id IS NOT NEW.target_id
    BEGIN
        INSERT INTO watch_lifecycle_events(
            id, watch_id, event_type, from_status, to_status, target_type, target_id,
            historical_target_id, resolution_state, resolution_options_json, actor,
            reason, provenance_status, occurred_at, created_at
        ) VALUES (
            'wle_' || lower(hex(randomblob(16))), NEW.id, 'target_changed', OLD.status, NEW.status,
            NEW.target_type, NEW.target_id, NEW.historical_target_id, NEW.resolution_state,
            NEW.resolution_options_json, NULL, 'Watch target changed', 'exact', NEW.updated_at, NEW.updated_at
        );
        INSERT INTO watch_scope_refresh_requests(
            id, watch_id, origin, actor, provenance_status, provenance_detail,
            force_revision, requested_at
        ) VALUES (
            'wsrq_' || lower(hex(randomblob(16))), NEW.id, 'target_change', NULL,
            'exact', 'Target snapshot changed in the same transaction.', 1, NEW.updated_at
        );
    END
    """,
    """
    CREATE TRIGGER watches_research_history_resolution
    AFTER UPDATE OF resolution_state, resolution_options_json ON watches
    WHEN OLD.resolution_state IS NOT NEW.resolution_state OR OLD.resolution_options_json IS NOT NEW.resolution_options_json
    BEGIN
        INSERT INTO watch_lifecycle_events(
            id, watch_id, event_type, from_status, to_status, target_type, target_id,
            historical_target_id, resolution_state, resolution_options_json, actor,
            reason, provenance_status, occurred_at, created_at
        ) VALUES (
            'wle_' || lower(hex(randomblob(16))), NEW.id, 'resolution_changed', OLD.status, NEW.status,
            NEW.target_type, NEW.target_id, NEW.historical_target_id, NEW.resolution_state,
            NEW.resolution_options_json, NULL, 'Watch target resolution changed', 'exact', NEW.updated_at, NEW.updated_at
        );
    END
    """,
    """
    CREATE TABLE source_endpoints (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
        normalized_url TEXT NOT NULL,
        endpoint_kind TEXT NOT NULL CHECK (endpoint_kind IN ('page','feed','rss','atom')),
        active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
        discovered_from TEXT NOT NULL DEFAULT 'source_projection',
        verified_at TEXT,
        verification_outcome TEXT NOT NULL DEFAULT 'unverified',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(source_id, normalized_url, endpoint_kind)
    )
    """,
    "CREATE INDEX source_endpoints_source_idx ON source_endpoints(source_id, active, endpoint_kind, id)",
    "CREATE INDEX source_endpoints_url_idx ON source_endpoints(normalized_url, endpoint_kind, source_id)",
    """
    INSERT INTO source_endpoints(
        id, source_id, normalized_url, endpoint_kind, active, discovered_from,
        verification_outcome, created_at, updated_at
    )
    SELECT 'sep_' || lower(hex(randomblob(16))), id, homepage_url, 'page', 1,
           'legacy_source_projection', 'unverified',
           strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    FROM sources
    WHERE homepage_url IS NOT NULL AND TRIM(homepage_url) <> ''
    """,
    """
    INSERT INTO source_endpoints(
        id, source_id, normalized_url, endpoint_kind, active, discovered_from,
        verification_outcome, created_at, updated_at
    )
    SELECT 'sep_' || lower(hex(randomblob(16))), id, feed_url, 'feed', 1,
           'legacy_source_projection', 'unverified_legacy_feed_kind',
           strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    FROM sources
    WHERE feed_url IS NOT NULL AND TRIM(feed_url) <> ''
    """,
    """
    CREATE TRIGGER sources_endpoints_insert
    AFTER INSERT ON sources
    BEGIN
        INSERT INTO source_endpoints(id, source_id, normalized_url, endpoint_kind, active, discovered_from, verification_outcome, created_at, updated_at)
        SELECT 'sep_' || lower(hex(randomblob(16))), NEW.id, NEW.homepage_url, 'page', 1, 'source_projection', 'unverified', NEW.created_at, NEW.updated_at
        WHERE NEW.homepage_url IS NOT NULL AND TRIM(NEW.homepage_url) <> '';
        INSERT INTO source_endpoints(id, source_id, normalized_url, endpoint_kind, active, discovered_from, verification_outcome, created_at, updated_at)
        SELECT 'sep_' || lower(hex(randomblob(16))), NEW.id, NEW.feed_url, 'feed', 1, 'source_projection', 'unverified_legacy_feed_kind', NEW.created_at, NEW.updated_at
        WHERE NEW.feed_url IS NOT NULL AND TRIM(NEW.feed_url) <> '';
    END
    """,
    """
    CREATE TRIGGER sources_endpoints_update
    AFTER UPDATE OF homepage_url, feed_url ON sources
    WHEN OLD.homepage_url IS NOT NEW.homepage_url OR OLD.feed_url IS NOT NEW.feed_url
    BEGIN
        UPDATE source_endpoints SET active = 0, updated_at = NEW.updated_at
        WHERE source_id = NEW.id AND endpoint_kind IN ('page','feed');
        INSERT INTO source_endpoints(id, source_id, normalized_url, endpoint_kind, active, discovered_from, verification_outcome, created_at, updated_at)
        SELECT 'sep_' || lower(hex(randomblob(16))), NEW.id, NEW.homepage_url, 'page', 1, 'source_projection', 'unverified', NEW.updated_at, NEW.updated_at
        WHERE NEW.homepage_url IS NOT NULL AND TRIM(NEW.homepage_url) <> ''
        ON CONFLICT(source_id, normalized_url, endpoint_kind) DO UPDATE SET active = 1, updated_at = excluded.updated_at;
        INSERT INTO source_endpoints(id, source_id, normalized_url, endpoint_kind, active, discovered_from, verification_outcome, created_at, updated_at)
        SELECT 'sep_' || lower(hex(randomblob(16))), NEW.id, NEW.feed_url, 'feed', 1, 'source_projection', 'unverified_legacy_feed_kind', NEW.updated_at, NEW.updated_at
        WHERE NEW.feed_url IS NOT NULL AND TRIM(NEW.feed_url) <> ''
        ON CONFLICT(source_id, normalized_url, endpoint_kind) DO UPDATE SET active = 1, updated_at = excluded.updated_at;
    END
    """,
    """
    CREATE TABLE watch_source_memberships (
        id TEXT PRIMARY KEY,
        watch_id TEXT NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
        source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
        monitor_id TEXT REFERENCES monitors(id) ON DELETE RESTRICT,
        endpoint_id TEXT REFERENCES source_endpoints(id) ON DELETE RESTRICT,
        approved_candidate_id TEXT REFERENCES source_candidates(id) ON DELETE SET NULL,
        opened_scope_revision_id TEXT REFERENCES watch_scope_revisions(id) ON DELETE RESTRICT,
        interval_state TEXT NOT NULL CHECK (interval_state IN ('open','closed','legacy_unknown')),
        monitored_from TEXT,
        monitored_until TEXT,
        approval_actor TEXT,
        acquisition_policy_snapshot TEXT NOT NULL DEFAULT '{}',
        provenance_status TEXT NOT NULL CHECK (provenance_status IN ('exact','inferred','unknown')),
        provenance_detail TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK (
            (interval_state = 'open' AND monitored_from IS NOT NULL AND monitored_until IS NULL)
            OR (interval_state = 'closed' AND monitored_from IS NOT NULL AND monitored_until IS NOT NULL)
            OR (interval_state = 'legacy_unknown' AND monitored_from IS NULL AND monitored_until IS NULL)
        )
    )
    """,
    "CREATE UNIQUE INDEX watch_source_memberships_one_open_idx ON watch_source_memberships(watch_id, source_id) WHERE interval_state = 'open'",
    "CREATE INDEX watch_source_memberships_watch_idx ON watch_source_memberships(watch_id, interval_state, created_at, id)",
    "CREATE INDEX watch_source_memberships_source_idx ON watch_source_memberships(source_id, interval_state, created_at, id)",
    """
    INSERT INTO watch_source_memberships(
        id, watch_id, source_id, monitor_id, endpoint_id, approved_candidate_id,
        opened_scope_revision_id, interval_state, monitored_from, monitored_until,
        approval_actor, acquisition_policy_snapshot, provenance_status,
        provenance_detail, created_at, updated_at
    )
    SELECT
        'wsm_' || lower(hex(randomblob(16))), ws.watch_id, ws.source_id, ws.monitor_id,
        (SELECT se.id FROM source_endpoints se WHERE se.source_id = ws.source_id AND se.active = 1 ORDER BY CASE se.endpoint_kind WHEN 'feed' THEN 0 WHEN 'rss' THEN 1 WHEN 'atom' THEN 2 ELSE 3 END, se.id LIMIT 1),
        (SELECT sc.id FROM source_candidates sc WHERE sc.watch_id = ws.watch_id AND sc.source_id = ws.source_id AND sc.status = 'approved' ORDER BY sc.reviewed_at DESC, sc.id DESC LIMIT 1),
        w.current_scope_revision_id, 'open', ws.created_at, NULL,
        (SELECT sc.reviewed_by FROM source_candidates sc WHERE sc.watch_id = ws.watch_id AND sc.source_id = ws.source_id AND sc.status = 'approved' ORDER BY sc.reviewed_at DESC, sc.id DESC LIMIT 1),
        COALESCE((SELECT json_object('allowed_channels', json(mp.allowed_channels), 'base_cadence_seconds', mp.base_cadence_seconds, 'query_budget', mp.query_budget, 'paid_budget_usd', mp.paid_budget_usd, 'local_model_budget', mp.local_model_budget) FROM monitoring_policies mp WHERE mp.id = w.policy_id), '{}'),
        'inferred', 'watch_sources.created_at is preserved as the known attachment timestamp; it is not asserted to be first monitoring time.',
        strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    FROM watch_sources ws
    JOIN watches w ON w.id = ws.watch_id
    ORDER BY ws.watch_id, ws.source_id
    """,
    """
    INSERT INTO watch_source_memberships(
        id, watch_id, source_id, monitor_id, endpoint_id, approved_candidate_id,
        opened_scope_revision_id, interval_state, monitored_from, monitored_until,
        approval_actor, acquisition_policy_snapshot, provenance_status,
        provenance_detail, created_at, updated_at
    )
    SELECT
        'wsm_' || lower(hex(randomblob(16))), sc.watch_id, sc.source_id, NULL,
        (SELECT se.id FROM source_endpoints se WHERE se.source_id = sc.source_id AND se.active = 1 ORDER BY CASE se.endpoint_kind WHEN 'feed' THEN 0 WHEN 'rss' THEN 1 WHEN 'atom' THEN 2 ELSE 3 END, se.id LIMIT 1),
        sc.id, NULL, 'legacy_unknown', NULL, NULL, sc.reviewed_by, '{}', 'unknown',
        'Approved legacy candidate has no provable current attachment interval; dates are intentionally unset.',
        strftime('%Y-%m-%dT%H:%M:%SZ', 'now'), strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
    FROM source_candidates sc
    WHERE sc.status = 'approved' AND sc.source_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM watch_sources ws
          WHERE ws.watch_id = sc.watch_id AND ws.source_id = sc.source_id
      )
      AND NOT EXISTS (
          SELECT 1 FROM watch_source_memberships wm
          WHERE wm.watch_id = sc.watch_id AND wm.source_id = sc.source_id
      )
    ORDER BY sc.watch_id, sc.source_id, sc.id
    """,
    """
    CREATE TRIGGER watch_sources_membership_insert
    AFTER INSERT ON watch_sources
    BEGIN
        INSERT INTO watch_source_memberships(
            id, watch_id, source_id, monitor_id, endpoint_id, approved_candidate_id,
            opened_scope_revision_id, interval_state, monitored_from, monitored_until,
            approval_actor, acquisition_policy_snapshot, provenance_status,
            provenance_detail, created_at, updated_at
        )
        SELECT
            'wsm_' || lower(hex(randomblob(16))), NEW.watch_id, NEW.source_id, NEW.monitor_id,
            (SELECT se.id FROM source_endpoints se WHERE se.source_id = NEW.source_id AND se.active = 1 ORDER BY CASE se.endpoint_kind WHEN 'feed' THEN 0 WHEN 'rss' THEN 1 WHEN 'atom' THEN 2 ELSE 3 END, se.id LIMIT 1),
            (SELECT sc.id FROM source_candidates sc WHERE sc.watch_id = NEW.watch_id AND sc.source_id = NEW.source_id AND sc.status = 'approved' ORDER BY sc.reviewed_at DESC, sc.id DESC LIMIT 1),
            w.current_scope_revision_id, 'open', NEW.created_at, NULL,
            (SELECT sc.reviewed_by FROM source_candidates sc WHERE sc.watch_id = NEW.watch_id AND sc.source_id = NEW.source_id AND sc.status = 'approved' ORDER BY sc.reviewed_at DESC, sc.id DESC LIMIT 1),
            COALESCE((SELECT json_object('allowed_channels', json(mp.allowed_channels), 'base_cadence_seconds', mp.base_cadence_seconds, 'query_budget', mp.query_budget, 'paid_budget_usd', mp.paid_budget_usd, 'local_model_budget', mp.local_model_budget) FROM monitoring_policies mp WHERE mp.id = w.policy_id), '{}'),
            'exact', 'Attachment interval opened by the watch_sources mutation in this transaction.',
            NEW.created_at, NEW.created_at
        FROM watches w WHERE w.id = NEW.watch_id;
        INSERT INTO watch_scope_refresh_requests(
            id, watch_id, origin, actor, provenance_status, provenance_detail,
            force_revision, requested_at
        ) VALUES (
            'wsrq_' || lower(hex(randomblob(16))), NEW.watch_id, 'system', NULL,
            'exact', 'Attached Monitor synchronized to the current Watch scope.', 0, NEW.created_at
        );
    END
    """,
    """
    CREATE TRIGGER watch_sources_membership_delete
    BEFORE DELETE ON watch_sources
    BEGIN
        UPDATE watch_source_memberships
        SET interval_state = 'closed',
            monitored_until = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
            updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now'),
            provenance_detail = provenance_detail || ' Detach observed exactly at close time.'
        WHERE watch_id = OLD.watch_id AND source_id = OLD.source_id AND interval_state = 'open';
    END
    """,
    """
    CREATE TRIGGER watch_vocabulary_scope_refresh_insert
    AFTER INSERT ON watch_vocabulary
    WHEN NEW.status = 'approved' AND NEW.enabled = 1
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        VALUES ('wsrq_' || lower(hex(randomblob(16))), NEW.watch_id, 'approved', NEW.reviewed_by, 'exact', 'Approved Watch vocabulary changed.', 0, COALESCE(NEW.reviewed_at, NEW.created_at));
    END
    """,
    """
    CREATE TRIGGER watch_vocabulary_scope_refresh_update
    AFTER UPDATE OF term, kind, status, enabled ON watch_vocabulary
    WHEN (OLD.status = 'approved' AND OLD.enabled = 1) OR (NEW.status = 'approved' AND NEW.enabled = 1)
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        VALUES ('wsrq_' || lower(hex(randomblob(16))), NEW.watch_id, 'approved', NEW.reviewed_by, 'exact', 'Approved Watch vocabulary changed.', 0, COALESCE(NEW.reviewed_at, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')));
    END
    """,
    """
    CREATE TRIGGER watch_vocabulary_scope_refresh_delete
    AFTER DELETE ON watch_vocabulary
    WHEN OLD.status = 'approved' AND OLD.enabled = 1
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        VALUES ('wsrq_' || lower(hex(randomblob(16))), OLD.watch_id, 'approved', OLD.reviewed_by, 'exact', 'Approved Watch vocabulary removed.', 0, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));
    END
    """,
    """
    CREATE TRIGGER topic_terms_watch_scope_insert
    AFTER INSERT ON topic_terms
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Topic scope changed.', 0, NEW.created_at
        FROM watches w WHERE w.target_type = 'topic' AND w.target_id = NEW.topic_id;
    END
    """,
    """
    CREATE TRIGGER topic_terms_watch_scope_update
    AFTER UPDATE OF term, term_type, concept_kind ON topic_terms
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Topic scope changed.', 0, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        FROM watches w WHERE w.target_type = 'topic' AND w.target_id = NEW.topic_id;
    END
    """,
    """
    CREATE TRIGGER topic_terms_watch_scope_delete
    AFTER DELETE ON topic_terms
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Topic scope changed.', 0, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        FROM watches w WHERE w.target_type = 'topic' AND w.target_id = OLD.topic_id;
    END
    """,
    """
    CREATE TRIGGER subject_aliases_watch_scope_insert
    AFTER INSERT ON subject_aliases
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Subject aliases changed.', 0, NEW.created_at
        FROM watches w WHERE w.target_type = 'subject' AND w.target_id = NEW.subject_id;
    END
    """,
    """
    CREATE TRIGGER subject_aliases_watch_scope_delete
    AFTER DELETE ON subject_aliases
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Subject aliases changed.', 0, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
        FROM watches w WHERE w.target_type = 'subject' AND w.target_id = OLD.subject_id;
    END
    """,
    """
    CREATE TRIGGER subjects_watch_scope_update
    AFTER UPDATE OF canonical_name, description ON subjects
    WHEN OLD.canonical_name IS NOT NEW.canonical_name OR OLD.description IS NOT NEW.description
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Subject target changed.', 0, NEW.updated_at
        FROM watches w WHERE w.target_type = 'subject' AND w.target_id = NEW.id;
    END
    """,
    """
    CREATE TRIGGER research_questions_watch_scope_update
    AFTER UPDATE OF question ON research_questions
    WHEN OLD.question IS NOT NEW.question
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Research Question target changed.', 0, NEW.updated_at
        FROM watches w WHERE w.target_type = 'research_question' AND w.target_id = NEW.id;
    END
    """,
    """
    CREATE TRIGGER story_revisions_watch_scope_insert
    AFTER INSERT ON story_revisions
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Story target revision changed.', 0, NEW.created_at
        FROM watches w WHERE w.target_type = 'story' AND w.target_id = NEW.story_id;
    END
    """,
    """
    CREATE TRIGGER sources_watch_scope_update
    AFTER UPDATE OF name, slug, domain, homepage_url, feed_url, source_kind ON sources
    WHEN OLD.name IS NOT NEW.name OR OLD.slug IS NOT NEW.slug OR OLD.domain IS NOT NEW.domain
      OR OLD.homepage_url IS NOT NEW.homepage_url OR OLD.feed_url IS NOT NEW.feed_url
      OR OLD.source_kind IS NOT NEW.source_kind
    BEGIN
        INSERT INTO watch_scope_refresh_requests(id, watch_id, origin, actor, provenance_status, provenance_detail, force_revision, requested_at)
        SELECT 'wsrq_' || lower(hex(randomblob(16))), w.id, 'target_scope_change', NULL, 'exact', 'Source target metadata changed; semantic eligibility remains disabled for Source-only Research.', 0, NEW.updated_at
        FROM watches w WHERE w.target_type = 'source' AND w.target_id = NEW.id;
    END
    """,
)

__all__ = ["MIGRATION_0040_STATEMENTS"]
