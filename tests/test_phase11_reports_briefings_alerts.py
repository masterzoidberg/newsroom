from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainConflict, DomainValidation, utc_now
from newsroom.evidence import EvidenceService
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorService, MonitoringPolicyService
from newsroom.reports import AlertService, BriefingService, LivingReportService
from newsroom.story_evolution import StoryEvolutionService


PASSWORD = "a-long-test-password-12345"


def _accepted_story(db_path):
    core = CoreService(db_path)
    source = core.create_source(
        {
            "name": "Atlas Official",
            "slug": "atlas-official",
            "source_kind": "official",
            "default_quality": "primary",
        }
    )
    document = core.create_document(
        {
            "source_id": source["id"],
            "canonical_url": "https://atlas.test/release",
            "title": "Atlas release",
        }
    )
    story = core.create_story({"headline": "Atlas release", "lifecycle": "developing"})
    ledger = EvidenceService(db_path)
    version = ledger.create_document_version(
        document["id"], {"content_hash": "phase11-v1", "content_kind": "excerpt"}
    )
    span = ledger.create_evidence_span(
        version["id"], {"excerpt": "Atlas launched on August 16."}
    )
    claim = ledger.create_claim(
        story["id"], {"proposition": "Atlas launched on August 16", "importance": "major"}
    )
    ledger.link_claim_evidence(
        claim["id"], {"evidence_span_id": span["id"], "relationship": "supports"}
    )
    ledger.set_claim_state(claim["id"], "supported", "official release")
    ledger.accept_claim(claim["id"])
    return core, ledger, story, claim, span, document


def _monitor(db_path, story_id):
    policy = MonitoringPolicyService(db_path).create(
        {
            "name": "Phase 11 policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
            "priority": "high",
        }
    )
    return MonitorService(db_path).create(
        {
            "target_type": "story",
            "target_id": story_id,
            "policy_id": policy["id"],
            "next_check_at": utc_now(),
        }
    )


def test_living_report_is_versioned_closed_world_and_explains_evidence_causes(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, claim, span, _ = _accepted_story(tmp_db)
    reports = LivingReportService(tmp_db)
    report = reports.create(
        {"name": "Atlas report", "target_type": "story", "target_id": story["id"]}
    )

    generated = reports.generate(report["id"])
    revision = generated["current_revision"]

    assert revision["claim_ids"] == [claim["id"]]
    assert revision["claim_set_hash"]
    assert revision["audit"]["passed"] is True
    assert revision["propositions"] == [
        {"text": "Atlas launched on August 16", "claim_ids": [claim["id"]]}
    ]
    assert set(
        (
            "current_status",
            "what_changed",
            "active_stories",
            "evidence_strength",
            "contradictions",
            "unresolved_questions",
            "recommended_investigations",
        )
    ) <= set(revision["sections"])
    assert any(cause["evidence_span_id"] == span["id"] for cause in revision["change_causes"])

    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn = storage.connect(tmp_db)
        try:
            conn.execute(
                "UPDATE report_revisions SET current_status = 'changed' WHERE id = ?",
                (revision["id"],),
            )
        finally:
            conn.close()


def test_repeated_report_generation_does_not_create_material_alerts(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, _, _, _ = _accepted_story(tmp_db)
    reports = LivingReportService(tmp_db)
    report = reports.create(
        {"name": "Alertable report", "target_type": "story", "target_id": story["id"]}
    )
    first = reports.generate(report["id"])["current_revision"]
    alerts = AlertService(tmp_db)
    rule = alerts.create_rule(
        {
            "name": "Material report changes",
            "target_type": "report",
            "target_id": report["id"],
            "event_types": ["new_primary_evidence", "material_update"],
            "min_importance": 0.5,
        }
    )
    initial = alerts.emit_for_report_revision(report["id"], first["id"])
    repeated_revision = reports.generate(report["id"])["current_revision"]
    repeated = alerts.emit_for_report_revision(report["id"], repeated_revision["id"])

    assert initial["created_count"] == 1
    assert repeated["created_count"] == 0
    assert alerts.list_alerts()["total"] == 1
    assert rule["id"]


def test_material_change_alert_has_durable_in_app_ack_and_browser_fallback(tmp_db):
    apply_migrations(tmp_db)
    core, ledger, story, _, _, _ = _accepted_story(tmp_db)
    reports = LivingReportService(tmp_db)
    report = reports.create(
        {"name": "Change report", "target_type": "story", "target_id": story["id"]}
    )
    reports.generate(report["id"])
    alerts = AlertService(tmp_db)
    alerts.create_rule(
        {
            "name": "Browser change rule",
            "target_type": "report",
            "target_id": report["id"],
            "event_types": ["material_update", "new_primary_evidence"],
            "browser_enabled": True,
        }
    )
    alerts.set_notification_preferences(
        browser_enabled=True, permission_state="denied", online=True
    )

    second_source = core.create_source(
        {
            "name": "Atlas Primary Update",
            "slug": "atlas-primary-update",
            "source_kind": "official",
            "default_quality": "primary",
        }
    )
    second_document = core.create_document(
        {
            "source_id": second_source["id"],
            "canonical_url": "https://atlas.test/update",
            "title": "Atlas update",
        }
    )
    second_version = ledger.create_document_version(
        second_document["id"], {"content_hash": "phase11-v2", "content_kind": "excerpt"}
    )
    second_span = ledger.create_evidence_span(
        second_version["id"], {"excerpt": "Atlas expanded on August 17."}
    )
    second_claim = ledger.create_claim(
        story["id"], {"proposition": "Atlas expanded on August 17", "importance": "major"}
    )
    ledger.link_claim_evidence(
        second_claim["id"], {"evidence_span_id": second_span["id"], "relationship": "supports"}
    )
    ledger.set_claim_state(second_claim["id"], "supported", "official update")
    ledger.accept_claim(second_claim["id"])
    StoryEvolutionService(tmp_db).record_observation(
        story["id"], second_document["id"], "material_update", material_change=True
    )

    revision = reports.generate(report["id"])["current_revision"]
    emitted = alerts.emit_for_report_revision(report["id"], revision["id"])
    alert = emitted["items"][0]
    deliveries = alerts.get_alert(alert["id"])["deliveries"]

    assert emitted["created_count"] == 1
    assert any(item["channel"] == "in_app" and item["status"] == "sent" for item in deliveries)
    assert any(item["channel"] == "browser" and item["status"] == "denied" for item in deliveries)
    acknowledged = alerts.acknowledge(alert["id"], "user_1")
    assert acknowledged["status"] == "acknowledged"


def test_daily_briefing_is_timezone_aware_ranked_and_deduplicated(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, _, _, _ = _accepted_story(tmp_db)
    monitor = _monitor(tmp_db, story["id"])
    reports = LivingReportService(tmp_db)
    report = reports.create(
        {"name": "Monitor report", "target_type": "monitor", "target_id": monitor["id"]}
    )
    reports.generate(report["id"])
    now = datetime.now(timezone.utc)
    briefing_service = BriefingService(tmp_db)
    briefing = briefing_service.generate(
        period="daily",
        monitor_ids=[monitor["id"]],
        period_start=(now - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        period_end=(now + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        timezone_name="America/New_York",
    )
    repeated = briefing_service.generate(
        period="daily",
        monitor_ids=[monitor["id"]],
        period_start=briefing["period_start"],
        period_end=briefing["period_end"],
        timezone_name="America/New_York",
    )

    assert briefing["items"]
    assert briefing["items"][0]["story_id"] == story["id"]
    assert briefing["items"][0]["importance_score"] > 0
    assert repeated["id"] == briefing["id"]
    assert len(repeated["items"]) == len(briefing["items"])
    with pytest.raises(DomainValidation, match="timezone"):
        briefing_service.generate(
            period="weekly",
            monitor_ids=[monitor["id"]],
            timezone_name="Not/A_Timezone",
        )


def test_report_and_alert_api_require_authentication_and_csrf(tmp_path):
    client = TestClient(
        create_app(
            config=RuntimeConfig.for_environment("dev", root=tmp_path / "dev"),
            frontend_dist=tmp_path / "missing-dist",
        )
    )
    assert client.get("/api/v1/reports").status_code == 401
    assert client.post(
        "/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).status_code == 200
    payload = {"name": "Protected report", "target_type": "story", "target_id": "missing"}
    assert client.post("/api/v1/reports", json=payload).status_code == 403
