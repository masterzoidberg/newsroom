from __future__ import annotations

import pytest

from newsroom.coverage import CoverageService
from newsroom.domain import CoreService, DomainValidation
from newsroom.migrations import apply_migrations
from newsroom.ask import AskService


def test_coverage_preserves_observation_states_and_qualified_negative(tmp_db):
    apply_migrations(tmp_db)
    source = CoreService(tmp_db).create_source({"name": "Official", "slug": "official"})
    coverage = CoverageService(tmp_db)
    run = coverage.create_run(
        "watch",
        "watch-1",
        "2026-08-24T00:00:00Z",
        "2026-08-24T23:59:59Z",
        expected_channels=[
            {"key": "official", "channel_type": "official_archive", "source_id": source["id"], "source_class": "official"},
            {"key": "regulatory", "channel_type": "regulatory", "source_class": "regulatory"},
        ],
    )
    coverage.record_item(run["id"], "official", "not_found", reason="search completed")
    coverage.record_item(run["id"], "regulatory", "failed_acquisition", reason="provider timeout")
    completed = coverage.complete(run["id"])
    assert completed["summary"]["state_counts"] == {"failed_acquisition": 1, "not_found": 1}
    assert completed["summary"]["qualified_negative"] is False
    assert completed["items"][0]["state"] in {"not_found", "failed_acquisition"}


def test_coverage_requires_explicit_states_and_distinguishes_not_searched(tmp_db):
    apply_migrations(tmp_db)
    coverage = CoverageService(tmp_db)
    run = coverage.create_run(
        "story", "story-1", "2026-08-24T00:00:00Z", "2026-08-24T23:59:59Z",
        expected_channels=[{"key": "primary", "channel_type": "primary", "source_class": "primary"}],
    )
    result = coverage.complete(run["id"])
    assert result["items"][0]["state"] == "not_searched"
    assert result["summary"]["qualified_negative"] is False
    with pytest.raises(DomainValidation):
        coverage.record_item(run["id"], "primary", "unknown")


def test_complete_expected_window_qualifies_negative_absence(tmp_db):
    apply_migrations(tmp_db)
    coverage = CoverageService(tmp_db)
    run = coverage.create_run(
        "research_question", "rq-1", "2026-08-24T00:00:00Z", "2026-08-24T23:59:59Z",
        expected_channels=[{"key": "official", "channel_type": "official_archive", "source_class": "official"}],
    )
    coverage.record_item(run["id"], "official", "not_found", reason="official window searched")
    summary = coverage.complete(run["id"])["summary"]
    assert summary["completeness"] == 1.0
    assert summary["qualified_negative"] is True


def test_incomplete_expected_channel_creates_researchable_blind_spot(tmp_db):
    apply_migrations(tmp_db)
    coverage = CoverageService(tmp_db)
    run = coverage.create_run(
        "story", "story-2", "2026-08-24T00:00:00Z", "2026-08-24T23:59:59Z",
        expected_channels=[{"key": "regulatory", "channel_type": "registry", "source_class": "regulatory"}],
    )
    coverage.complete(run["id"])
    spots = coverage.generate_blind_spots(run["id"])
    assert spots["count"] == 1
    assert spots["items"][0]["source_class"] == "regulatory"
    assert coverage.review_blind_spot(spots["items"][0]["id"], "approved")["status"] == "approved"


def test_ask_uses_qualified_absence_language_for_incomplete_coverage(tmp_db):
    apply_migrations(tmp_db)
    story = CoreService(tmp_db).create_story({"headline": "Coverage story"})
    coverage = CoverageService(tmp_db)
    run = coverage.create_run(
        "story", story["id"], "2026-08-24T00:00:00Z", "2026-08-24T23:59:59Z",
        expected_channels=[{"key": "official", "channel_type": "official", "source_class": "official"}],
    )
    coverage.complete(run["id"])
    ask = AskService(tmp_db)
    conversation = ask.create_conversation(scope_type="story", scope_id=story["id"])
    answer = ask.ask(conversation["id"], "What happened in this story?")
    assert "should not be treated as evidence of absence" in answer["answer"]
    assert answer["status"] == "qualified"
