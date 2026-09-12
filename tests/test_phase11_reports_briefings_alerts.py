from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from newsroom import storage
from newsroom.app import create_app
from newsroom.config import RuntimeConfig
from newsroom.domain import CoreService, DomainConflict, DomainValidation, new_id, utc_now
from newsroom.evidence import EvidenceService
from newsroom.intelligent_monitoring import WatchService
from newsroom.jobs import BRIEFING_GENERATE_JOB_TYPE, JobService, SchedulerService
from newsroom.migrations import apply_migrations
from newsroom.monitoring import MonitorService, MonitoringPolicyService
from newsroom.reports import (
    AlertService,
    BriefingScheduleService,
    BriefingService,
    LivingReportService,
)
from newsroom.story_evolution import StoryEvolutionService
from newsroom.worker import WorkerProcess


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


def _watch(db_path, target_id, *, name="Atlas Watch"):
    policy = MonitoringPolicyService(db_path).create(
        {
            "name": "Phase 11 Watch policy",
            "allowed_channels": ["direct_http"],
            "base_cadence_seconds": 60,
            "min_cadence_seconds": 30,
            "max_cadence_seconds": 300,
            "priority": "normal",
        }
    )
    return WatchService(db_path).create(
        {
            "name": name,
            "target_type": "story",
            "target_id": target_id,
            "policy_id": policy["id"],
        }
    )


def test_watch_context_maps_to_one_canonical_report_and_converges_on_retry(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, _, _, _ = _accepted_story(tmp_db)
    watch = _watch(tmp_db, story["id"])
    reports = LivingReportService(tmp_db)

    assert reports.get_for_watch(watch["id"]) is None
    first = reports.create_for_watch(
        watch["id"], {"name": "Atlas Watch report", "timezone_name": "UTC"}
    )
    repeated = reports.create_for_watch(
        watch["id"], {"name": "A different retry name", "timezone_name": "UTC"}
    )

    assert first["target_type"] == "story"
    assert first["target_id"] == story["id"]
    assert repeated["id"] == first["id"]
    assert repeated["name"] == first["name"]
    assert reports.get_for_watch(watch["id"])["id"] == first["id"]


def test_report_without_accepted_evidence_keeps_no_revision_and_reports_deferred(tmp_db):
    apply_migrations(tmp_db)
    core = CoreService(tmp_db)
    story = core.create_story({"headline": "Waiting for evidence"})
    watch = _watch(tmp_db, story["id"], name="Waiting Watch")
    report = LivingReportService(tmp_db).create_for_watch(watch["id"])

    generated = LivingReportService(tmp_db).generate(report["id"])

    assert generated["current_revision"] is None
    assert generated["generation"]["status"] == "deferred"
    assert generated["generation"]["reason_code"] == "no_accepted_evidence"
    assert generated["generation"]["report_id"] == report["id"]
    assert generated["generation"]["revision_id"] is None
    assert generated["generation"]["input_identity"]
    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM report_revisions").fetchone()[0] == 0
    finally:
        conn.close()


def test_failed_generation_preserves_the_last_successful_watch_report_revision(tmp_db, monkeypatch):
    apply_migrations(tmp_db)
    _, _, story, _, _, _ = _accepted_story(tmp_db)
    watch = _watch(tmp_db, story["id"])
    reports = LivingReportService(tmp_db)
    report = reports.create_for_watch(watch["id"])
    first = reports.generate(report["id"])
    first_revision_id = first["current_revision_id"]

    original_collect = reports._collect_sections

    def corrupt_collect(conn, story_ids, claims):
        sections, _ = original_collect(conn, story_ids, claims)
        return sections, [{"text": "An unsupported proposition", "claim_ids": ["missing-claim"]}]

    monkeypatch.setattr(reports, "_collect_sections", corrupt_collect)
    with pytest.raises(DomainConflict, match="material report input changed"):
        reports.generate(report["id"])

    preserved = reports.get(report["id"])
    assert preserved["current_revision_id"] == first_revision_id
    assert preserved["current_revision"]["id"] == first_revision_id


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


def test_alert_rule_dedupe_window_suppresses_equivalent_later_revision(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, _, _, document = _accepted_story(tmp_db)
    evolution = StoryEvolutionService(tmp_db)
    reports = LivingReportService(tmp_db)
    report = reports.create(
        {"name": "Deduplicated report", "target_type": "story", "target_id": story["id"]}
    )
    alerts = AlertService(tmp_db)
    alerts.create_rule(
        {
            "name": "Deduplicate material changes",
            "target_type": "report",
            "target_id": report["id"],
            "event_types": ["material_update"],
            "dedupe_window_seconds": 86400,
        }
    )

    evolution.record_observation(
        story["id"], document["id"], "material_update", material_change=True
    )
    first_revision = reports.generate(report["id"])["current_revision"]
    first = alerts.emit_for_report_revision(report["id"], first_revision["id"])

    evolution.record_observation(
        story["id"], document["id"], "material_update", material_change=True
    )
    second_revision = reports.generate(report["id"])["current_revision"]
    repeated = alerts.emit_for_report_revision(report["id"], second_revision["id"])

    assert first["created_count"] == 1
    assert repeated["created_count"] == 0
    assert alerts.list_alerts()["total"] == 1


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


def test_alert_inbox_threshold_history_and_watch_scope_are_persisted(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, _, _, _ = _accepted_story(tmp_db)
    monitor = _monitor(tmp_db, story["id"])
    alerts = AlertService(tmp_db)
    rule = alerts.create_rule(
        {
            "name": "Watch corroboration",
            "target_type": "all",
            "event_types": ["corroboration"],
            "min_importance": 0.45,
        }
    )
    alert_id = new_id("alert")
    now = utc_now()
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute(
                """
                INSERT INTO alerts(
                    id, rule_id, story_id, event_type, title, body,
                    importance_score, dedupe_key, cause_json, status, created_at
                ) VALUES (?, ?, ?, 'corroboration', ?, ?, 0.45, ?, ?, 'unread', ?)
                """,
                (
                    alert_id,
                    rule["id"],
                    story["id"],
                    "Corroboration: Atlas release",
                    "A lower-priority corroborating source was recorded.",
                    new_id("dedupe"),
                    json.dumps([]),
                    now,
                ),
            )
    finally:
        conn.close()

    assert alerts.list_alerts(status="unread", min_importance=0.5)["total"] == 0
    assert alerts.list_alerts(status="unread", min_importance=0.45)["total"] == 1
    alerts.acknowledge(alert_id, "owner")
    assert alerts.list_alerts(status="acknowledged", min_importance=0.0)["total"] == 1

    updated = alerts.update_rule(
        rule["id"],
        {"target_type": "monitor", "target_id": monitor["id"], "min_importance": 0.75},
    )
    assert updated["target_type"] == "monitor"
    assert updated["target_id"] == monitor["id"]
    assert updated["min_importance"] == 0.75
    assert alerts.get_rule(rule["id"])["target_id"] == monitor["id"]

    with pytest.raises(DomainValidation, match="between 0 and 1"):
        alerts.list_alerts(min_importance=1.1)


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


def test_briefing_schedule_is_durable_timezone_aware_and_pauseable(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, _, _, _ = _accepted_story(tmp_db)
    monitor = _monitor(tmp_db, story["id"])
    schedules = BriefingScheduleService(tmp_db)

    schedule = schedules.create(
        {
            "cadence": "daily",
            "timezone_name": "America/New_York",
            "scope": {"monitor_ids": [monitor["id"]]},
        },
        now="2026-11-01T03:59:00Z",
    )

    assert schedule["cadence"] == "daily"
    assert schedule["timezone_name"] == "America/New_York"
    assert schedule["scope"] == {"monitor_ids": [monitor["id"]]}
    assert schedule["next_due_at"] == "2026-11-01T04:00:00Z"
    assert schedule["paused"] is False

    paused = schedules.pause(now="2026-11-01T04:00:00Z")
    assert paused["paused"] is True
    assert paused["next_due_at"] is None
    assert SchedulerService(tmp_db).tick(now="2026-11-01T04:00:00Z")["briefing_job_ids"] == []

    resumed = schedules.resume(now="2026-11-01T05:01:00Z")
    assert resumed["paused"] is False
    assert resumed["next_due_at"] == "2026-11-02T05:00:00Z"


def test_due_briefing_schedule_coalesces_concurrent_ticks_and_replay(tmp_db):
    apply_migrations(tmp_db)
    _, _, story, _, _, _ = _accepted_story(tmp_db)
    monitor = _monitor(tmp_db, story["id"])
    schedules = BriefingScheduleService(tmp_db)
    schedule = schedules.create(
        {
            "cadence": "daily",
            "timezone_name": "UTC",
            "scope": {"monitor_ids": [monitor["id"]]},
        },
        now="2026-08-16T11:00:00Z",
    )
    due = schedule["next_due_at"]
    barrier = threading.Barrier(2)
    results = []

    def tick():
        barrier.wait()
        results.append(SchedulerService(tmp_db).tick(now=due))

    first = threading.Thread(target=tick)
    second = threading.Thread(target=tick)
    first.start()
    second.start()
    first.join()
    second.join()

    conn = storage.connect(tmp_db)
    try:
        jobs = conn.execute(
            "SELECT * FROM jobs WHERE job_type = ?", (BRIEFING_GENERATE_JOB_TYPE,)
        ).fetchall()
    finally:
        conn.close()
    assert len(jobs) == 1
    assert sum(len(result["briefing_job_ids"]) for result in results) == 1

    worker = WorkerProcess(
        tmp_db,
        schedules.handlers(),
        worker_id="briefing-worker",
        queue=JobService(tmp_db),
    )
    finished = worker.run_once(now=due)
    assert finished["status"] == "succeeded"
    replay = JobService(tmp_db).rerun(finished["id"])
    worker.run_once(now=due)

    conn = storage.connect(tmp_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM briefings").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE job_type = ?", (BRIEFING_GENERATE_JOB_TYPE,)
        ).fetchone()[0] == 2
    finally:
        conn.close()
    assert replay["job_type"] == BRIEFING_GENERATE_JOB_TYPE


def test_briefing_schedule_bounds_missed_intervals_and_keeps_zero_paid_default(tmp_db):
    apply_migrations(tmp_db)
    schedules = BriefingScheduleService(tmp_db)
    schedule = schedules.create(
        {"cadence": "daily", "timezone_name": "UTC"},
        now="2026-08-01T12:00:00Z",
    )
    result = SchedulerService(tmp_db).tick(now="2026-08-16T12:00:00Z")

    assert result["briefing_enqueued"] == 3
    assert result["briefing_missed"] > 0
    refreshed = schedules.get()
    assert refreshed["next_due_at"] > "2026-08-16T12:00:00Z"
    conn = storage.connect(tmp_db)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM jobs WHERE job_type = ? ORDER BY created_at",
            (BRIEFING_GENERATE_JOB_TYPE,),
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 3
    assert all('"paid_requests":0' in row[0] for row in rows)
    assert schedule["id"] == refreshed["id"]


def test_briefing_schedule_api_exposes_preferences_and_latest_output(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.get("/api/v1/briefing-schedule").status_code == 401
    assert client.post(
        "/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}

    assert client.get("/api/v1/briefing-schedule").json() is None
    assert client.put(
        "/api/v1/briefing-schedule",
        json={"cadence": "daily", "timezone_name": "America/New_York"},
    ).status_code == 403
    saved = client.put(
        "/api/v1/briefing-schedule",
        json={"cadence": "daily", "timezone_name": "America/New_York"},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    schedule = saved.json()
    assert schedule["enabled"] is True
    assert schedule["paused"] is False
    assert schedule["timezone_name"] == "America/New_York"
    assert schedule["next_due_at"]

    paused = client.put(
        "/api/v1/briefing-schedule",
        json={"enabled": False},
        headers=headers,
    )
    assert paused.status_code == 200
    assert paused.json()["paused"] is True
    assert paused.json()["next_due_at"] is None
    assert client.get("/api/v1/briefings/latest").json() is None


def test_schema36_upgrade_and_online_backup_preserve_briefing_schedule(tmp_db, tmp_path):
    apply_migrations(tmp_db)
    conn = storage.connect(tmp_db)
    try:
        with storage.write_tx(conn):
            conn.execute("INSERT INTO app_meta(key, value) VALUES ('schedule_test', 'preserved')")
            conn.execute("DROP INDEX briefing_schedules_due_idx")
            conn.execute("DROP TABLE briefing_schedules")
            conn.execute("DELETE FROM schema_migrations WHERE version = 37")
            conn.execute("UPDATE app_meta SET value = '36' WHERE key = 'schema_version'")
    finally:
        conn.close()

    upgraded = apply_migrations(tmp_db)
    assert upgraded.applied_versions == (37,)
    schedule = BriefingScheduleService(tmp_db).create(
        {"cadence": "weekly", "timezone_name": "America/New_York"},
        now="2026-03-08T07:01:00Z",
    )
    assert schedule["next_due_at"] == "2026-03-09T04:00:00Z"

    backup = storage.online_backup(tmp_path / "briefing-schedule.db", source_path=tmp_db)
    restored = tmp_path / "briefing-schedule-restored.db"
    storage.restore_backup(backup, restored)
    assert BriefingScheduleService(restored).get() == schedule
    conn = storage.connect(restored)
    try:
        assert conn.execute(
            "SELECT value FROM app_meta WHERE key = 'schedule_test'"
        ).fetchone()[0] == "preserved"
    finally:
        conn.close()
    assert storage.integrity_check(restored) == "ok"


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


def test_report_generation_api_evaluates_alert_rules(tmp_path):
    config = RuntimeConfig.for_environment("dev", root=tmp_path / "dev")
    client = TestClient(create_app(config=config, frontend_dist=tmp_path / "missing-dist"))
    assert client.post(
        "/api/v1/auth/setup", json={"username": "admin", "password": PASSWORD}
    ).status_code == 201
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": PASSWORD}
    ).status_code == 200
    headers = {"X-CSRF-Token": client.cookies.get("newsroom_csrf")}

    _, _, story, _, _, document = _accepted_story(config.database_path)
    StoryEvolutionService(config.database_path).record_observation(
        story["id"], document["id"], "material_update", material_change=True
    )
    reports = LivingReportService(config.database_path)
    report = reports.create(
        {"name": "API alert report", "target_type": "story", "target_id": story["id"]}
    )
    AlertService(config.database_path).create_rule(
        {
            "name": "API material changes",
            "target_type": "report",
            "target_id": report["id"],
            "event_types": ["material_update", "new_primary_evidence"],
        }
    )

    generated = client.post(f"/api/v1/reports/{report['id']}/generate", headers=headers)

    assert generated.status_code == 200, generated.text
    alerts = client.get("/api/v1/alerts").json()
    assert alerts["total"] == 1
    assert alerts["items"][0]["report_id"] == report["id"]
