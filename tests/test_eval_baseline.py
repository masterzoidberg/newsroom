"""Tests for the v1 baseline: export loading, extraction, and scoring."""
from __future__ import annotations

import sqlite3

from newsroom.evals.baseline import (
    load_v1_export,
    run_baseline,
    extract_v1_db,
    V1_MAPPING,
)
from newsroom.evals.corpus import validate_corpus


def test_committed_v1_export_loads_and_scores():
    _, valid = validate_corpus()
    export = load_v1_export()
    results = run_baseline(valid, export)
    # Four v1-derived cases must be scored.
    scored_ids = {r.case_id for r in results}
    assert scored_ids == {
        "multi-outlet-hermes-v0200",
        "duplicate-syndication-hermes-v0201",
        "primary-vs-secondary-nous-funding",
        "similar-distinct-hermes-events",
    }


def test_v1_multi_outlet_grouping_is_correct():
    _, valid = validate_corpus()
    export = load_v1_export()
    results = {r.case_id: r for r in run_baseline(valid, export)}
    r = results["multi-outlet-hermes-v0200"]
    assert r.event.precision == 1.0
    assert r.event.recall == 1.0
    assert r.event.false_merge_count == 0
    assert r.event.false_split_count == 0


def test_v1_similar_distinct_events_not_merged():
    _, valid = validate_corpus()
    export = load_v1_export()
    results = {r.case_id: r for r in run_baseline(valid, export)}
    r = results["similar-distinct-hermes-events"]
    assert r.event.false_merge_count == 0
    assert r.event.precision == 1.0


def test_v1_duplicate_syndication_false_split():
    _, valid = validate_corpus()
    export = load_v1_export()
    results = {r.case_id: r for r in run_baseline(valid, export)}
    r = results["duplicate-syndication-hermes-v0201"]
    assert r.event.false_split_count == 1
    assert r.event.recall == 0.0


def test_v1_has_no_claims_or_evidence():
    export = load_v1_export()
    for pred in export.predictions:
        assert pred.claims == ()
        assert pred.evidence == ()
        assert pred.contradictions == ()


def test_extract_v1_db_is_read_only_and_correct(tmp_path):
    db = tmp_path / "v1.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE stories (id TEXT PRIMARY KEY, headline TEXT, event_key TEXT);
        CREATE TABLE sources (
            id TEXT PRIMARY KEY, story_id TEXT, title TEXT, publisher TEXT,
            author TEXT, url TEXT, canonical_url TEXT, domain TEXT,
            published_at TEXT, retrieved_at TEXT, source_type TEXT,
            source_quality TEXT, is_primary INTEGER
        );
        """
    )
    conn.execute(
        "INSERT INTO stories VALUES (?, ?, ?)",
        ("st_test", "Hermes v0.20.0", "hermes-v0-20-0"),
    )
    conn.execute(
        "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "src_test", "st_test", "Release", None, None,
            "https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.3",
            "https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.3",
            "github.com", None, "2026-08-14T02:32:59Z", "web", "primary", 1,
        ),
    )
    conn.commit()
    conn.close()

    mapping = [
        {
            "db": "dev",
            "story_id": "st_test",
            "case_id": "multi-outlet-hermes-v0200",
            "sources": {
                "https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.3": "github-v0200",
            },
        }
    ]
    export = extract_v1_db({"dev": db}, mapping=mapping)
    assert len(export["predictions"]) == 1
    pred = export["predictions"][0]
    assert pred["case_id"] == "multi-outlet-hermes-v0200"
    assert pred["story_groups"][0]["candidate_ids"] == ["github-v0200"]
    assert pred["primary_sources"] == ["github-v0200"]
