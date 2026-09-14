"""Schema-40 follow-on statements kept separate for reviewable overlay semantics."""
from __future__ import annotations


MIGRATION_0040_OVERLAY_STATEMENTS: tuple[str, ...] = (
    "DROP VIEW watch_scope_current",
    """
    CREATE VIEW watch_scope_current AS
    SELECT
        w.id AS watch_id,
        COALESCE(
            (SELECT r.intent FROM watch_scope_revisions r WHERE r.watch_id = w.id ORDER BY r.revision_number DESC, r.id DESC LIMIT 1),
            NULLIF(w.original_intent, ''),
            w.name
        ) AS intent,
        COALESCE(
            (SELECT r.focus_areas_json FROM watch_scope_revisions r WHERE r.watch_id = w.id ORDER BY r.revision_number DESC, r.id DESC LIMIT 1),
            '[]'
        ) AS focus_areas_json,
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
)

__all__ = ["MIGRATION_0040_OVERLAY_STATEMENTS"]
