"""Current Story context derived from the canonical Claim/Evidence graph.

``story_documents`` remains historical observation provenance.  These helpers
are the shared current-state read path used by matching, reporting, monitoring,
and Story diagnostics.
"""
from __future__ import annotations

import sqlite3


CURRENT_DOCUMENTS_QUERY = """
    WITH ranked_documents AS (
        SELECT
            c.story_id,
            d.id AS document_id,
            d.source_id,
            d.canonical_url,
            d.title,
            d.published_at,
            dv.id AS document_version_id,
            dv.retrieved_at,
            sd.event_key,
            COALESCE(sd.entities_json, '[]') AS entities_json,
            COALESCE(sd.locations_json, '[]') AS locations_json,
            ROW_NUMBER() OVER (
                PARTITION BY c.story_id, d.id
                ORDER BY COALESCE(dv.retrieved_at, '') DESC, dv.id DESC
            ) AS document_rank
        FROM claims c
        JOIN claim_evidence ce ON ce.claim_id = c.id
        JOIN evidence_spans es ON es.id = ce.evidence_span_id
        JOIN document_versions dv ON dv.id = es.document_version_id
        JOIN documents d ON d.id = dv.document_id
        LEFT JOIN story_documents sd
          ON sd.story_id = c.story_id AND sd.document_id = d.id
        WHERE c.story_id = ?
    )
    SELECT story_id, document_id, source_id, canonical_url, title, published_at,
           document_version_id, retrieved_at, event_key, entities_json, locations_json
    FROM ranked_documents
    WHERE document_rank = 1
    ORDER BY COALESCE(published_at, retrieved_at), document_id
"""


def current_story_documents(conn: sqlite3.Connection, story_id: str) -> list[sqlite3.Row]:
    return conn.execute(CURRENT_DOCUMENTS_QUERY, (story_id,)).fetchall()


def current_story_document_ids(conn: sqlite3.Connection, story_id: str) -> tuple[str, ...]:
    return tuple(row["document_id"] for row in current_story_documents(conn, story_id))


def current_story_source_ids(conn: sqlite3.Connection, story_id: str) -> tuple[str, ...]:
    return tuple(sorted({row["source_id"] for row in current_story_documents(conn, story_id)}))


def effective_story_entity_ids(conn: sqlite3.Connection, story_id: str) -> tuple[str, ...]:
    rows = conn.execute(
        """
        SELECT entity_id FROM story_entities
        WHERE story_id = ? AND authority = 'manual'
        UNION
        SELECT ce.entity_id
        FROM claims c
        JOIN claim_entities ce ON ce.claim_id = c.id
        WHERE c.story_id = ?
        ORDER BY entity_id
        """,
        (story_id, story_id),
    ).fetchall()
    return tuple(row[0] for row in rows)


def reconcile_story_entity_projection_tx(conn: sqlite3.Connection, story_id: str) -> int:
    """Rebuild only the disposable derived Story-Entity rows."""

    conn.execute(
        "DELETE FROM story_entities WHERE story_id = ? AND authority = 'derived'",
        (story_id,),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO story_entities
            (story_id, entity_id, origin, authority, created_at)
        SELECT DISTINCT c.story_id, ce.entity_id,
               CASE WHEN ce.origin IN ('user', 'import') THEN ce.origin ELSE ce.origin END,
               'derived', CURRENT_TIMESTAMP
        FROM claims c
        JOIN claim_entities ce ON ce.claim_id = c.id
        WHERE c.story_id = ?
        """,
        (story_id,),
    )
    return conn.execute(
        "SELECT COUNT(*) FROM story_entities WHERE story_id = ? AND authority = 'derived'",
        (story_id,),
    ).fetchone()[0]


__all__ = [
    "CURRENT_DOCUMENTS_QUERY",
    "current_story_documents",
    "current_story_document_ids",
    "current_story_source_ids",
    "effective_story_entity_ids",
    "reconcile_story_entity_projection_tx",
]
