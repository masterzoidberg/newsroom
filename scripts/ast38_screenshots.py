import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, expect, sync_playwright


OUT = Path(r"C:\Users\nicol\.codex\visualizations\2026\09\11\01a0919d-c948-71d3-b54f-1273fda91ef9\ast38")
OUT.mkdir(parents=True, exist_ok=True)

RUNTIME = {
    "managed": True,
    "overall": "idle",
    "supervisor": {"status": "healthy", "detail": "Ready", "managed": True},
    "components": {role: {"status": "healthy", "detail": "Ready", "managed": True} for role in ("api", "worker", "scheduler")},
    "work": {"state": "idle", "queued_jobs": 0, "running_jobs": 0},
    "controls": {"available": True, "actions": []},
    "request_id": "request-1",
}

BRIEFING = {"id": "briefing-1", "period": "daily", "timezone_name": "America/New_York", "period_start": "2026-09-11T04:00:00Z", "period_end": "2026-09-12T04:00:00Z", "items": [{"id": "item-1", "report_id": "report-1", "report_revision_id": "revision-1", "story_id": "story-1", "rank": 1, "importance_score": 0.92, "reason": "A material evidence update was recorded.", "claim_ids": ["claim-1"], "evidence_span_ids": ["span-1"]}]}


def fulfill(route, body, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def install(page: Page, *, watches, schedule, latest, schedule_error=False):
    state = {"watches": watches, "schedule": schedule, "schedule_error": schedule_error}

    def handle(route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.removeprefix("/api/v1")
        query = parse_qs(parsed.query)
        if path == "/auth/me": return fulfill(route, {"username": "admin"})
        if path == "/experience": return fulfill(route, {"mode": "simple"})
        if path == "/runtime/status": return fulfill(route, RUNTIME)
        if path == "/watches" and request.method == "GET": return fulfill(route, {"items": state["watches"], "total": len(state["watches"]), "page": 1, "page_size": 100})
        if path == "/briefing-schedule" and request.method == "GET":
            if state["schedule_error"]:
                state["schedule_error"] = False
                return fulfill(route, {"error": {"message": "Briefing preferences could not be loaded."}}, 503)
            return fulfill(route, state["schedule"])
        if path == "/briefing-schedule" and request.method == "PUT":
            payload = request.post_data_json or {}
            state["schedule"] = {**(state["schedule"] or {"id": 1, "cadence": "daily", "timezone_name": "UTC", "scope": {"monitor_ids": []}, "next_due_at": "2026-09-12T00:00:00Z"}), **payload}
            state["schedule"]["enabled"] = payload.get("enabled", True)
            state["schedule"]["paused"] = not state["schedule"]["enabled"]
            if state["schedule"]["paused"]: state["schedule"]["next_due_at"] = None
            return fulfill(route, state["schedule"])
        if path == "/briefings/latest":
            result = latest
            if query.get("period") == ["weekly"] and result:
                result = {**result, "period": "weekly"}
            return fulfill(route, result)
        if path == "/reports" and request.method == "GET":
            report = {"id": "report-1", "name": "Atlas report", "target_type": "topic", "target_id": "topic-1", "timezone_name": "America/New_York", "status": "active", "current_revision": None}
            return fulfill(route, {"items": [report] if state["watches"] else [], "total": 1 if state["watches"] else 0, "page": 1, "page_size": 100})
        if path == "/reports/report-1": return fulfill(route, {"id": "report-1", "name": "Atlas report", "target_type": "topic", "target_id": "topic-1", "timezone_name": "America/New_York", "status": "active", "current_revision": None, "revisions": []})
        if path == "/monitoring-policies" and request.method == "GET": return fulfill(route, {"items": [], "total": 0, "page": 1, "page_size": 100})
        if path == "/watches/setup" and request.method == "POST":
            state["watches"] = [{"id": "watch-1", "name": "Atlas Watch", "target_type": "topic", "target_id": "topic-1", "policy_id": "policy-1", "status": "paused"}]
            return fulfill(route, {"resumed": False, "watch_id": "watch-1", "topic_id": "topic-1", "policy_id": "policy-1", "status": "paused", "next_action": "add_sources", "primary_terms": ["Atlas"]}, 201)
        if path == "/attention": return fulfill(route, {"items": []})
        if path == "/review-boundary/changes": return fulfill(route, {"cursor": None, "since": "2026-09-11T00:00:00Z", "items": [], "next_cursor": None, "has_more": False, "bounded": True})
        if path.endswith("/health"): return fulfill(route, {"watch_id": "watch-1", "status": "paused", "active_source_count": 0, "pending_source_candidate_count": 0, "pending_vocabulary_suggestion_count": 0, "review": {"interest": "Atlas", "approved_terms": ["Atlas"], "excluded_terms": [], "sources": [], "cadence": {"base_cadence_seconds": 3600}, "supported_channels": [], "paid_budget_usd": 0, "paid_mode": "zero-paid", "ready_to_start": False, "blockers": ["Add a Source"]}, "progress": {"state": "idle", "label": "Not started", "detail": "No collection yet.", "results": []}})
        if path.startswith("/watches/") and request.method == "GET": return fulfill(route, {"id": "watch-1", "name": "Atlas Watch", "target_type": "topic", "target_id": "topic-1", "policy_id": "policy-1", "status": "paused"})
        if path.startswith("/watches/") or path.startswith("/topics/"): return fulfill(route, {"items": [], "total": 0, "page": 1, "page_size": 100})
        return fulfill(route, {"items": [], "total": 0, "page": 1, "page_size": 100})

    page.route("**/api/v1/**", handle)
    return state


def narrow(page: Page):
    metrics = page.evaluate("({innerWidth: window.innerWidth, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth})")
    assert metrics["innerWidth"] == 390 and metrics["clientWidth"] == 390 and metrics["scrollWidth"] <= metrics["clientWidth"], metrics


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page(viewport={"width": 1280, "height": 900})
    install(page, watches=[{"id": "watch-1", "name": "Atlas", "target_type": "topic", "target_id": "topic-1", "status": "active"}], schedule={"id": 1, "cadence": "daily", "timezone_name": "America/New_York", "scope": {"monitor_ids": []}, "enabled": True, "paused": False, "next_due_at": "2026-09-12T04:00:00Z"}, latest=BRIEFING)
    page.goto("http://127.0.0.1:4181/#reports")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="Briefing preferences")).to_be_visible()
    expect(page.get_by_text("A material evidence update was recorded.")).to_be_visible()
    page.screenshot(path=str(OUT / "reports-desktop-latest.png"), full_page=True)
    page.get_by_role("button", name="Pause briefings").click()
    expect(page.get_by_text("Briefings are paused. Saving these choices resumes the schedule.")).to_be_visible()
    page.screenshot(path=str(OUT / "reports-desktop-paused.png"), full_page=True)
    page.set_viewport_size({"width": 390, "height": 844})
    narrow(page)
    page.screenshot(path=str(OUT / "reports-phone-paused.png"), full_page=True)
    page.close()

    page = browser.new_page(viewport={"width": 1280, "height": 900})
    install(page, watches=[], schedule=None, latest=None)
    page.goto("http://127.0.0.1:4181/#monitors")
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Create your first Watch").first.click()
    page.fill("#watch-interest", "Atlas")
    page.fill("#watch-primary-term", "Atlas")
    page.get_by_role("button", name="Confirm primary term").click()
    page.get_by_label("Create a Living Report for this Watch").check()
    page.get_by_label("Enable a daily workspace briefing").check()
    expect(page.get_by_text("First intelligence choices")).to_be_visible()
    page.screenshot(path=str(OUT / "watch-onboarding-choices.png"), full_page=True)
    page.close()

    page = browser.new_page(viewport={"width": 390, "height": 844})
    install(page, watches=[{"id": "watch-1", "name": "Atlas", "target_type": "topic", "target_id": "topic-1", "status": "active"}], schedule={"id": 1, "cadence": "daily", "timezone_name": "America/New_York", "scope": {"monitor_ids": []}, "enabled": True, "paused": False, "next_due_at": "2026-09-12T04:00:00Z"}, latest=BRIEFING)
    page.goto("http://127.0.0.1:4181/#inbox")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Latest briefing")).to_be_visible()
    expect(page.get_by_text("A material evidence update was recorded.")).to_be_visible()
    narrow(page)
    page.screenshot(path=str(OUT / "inbox-phone-latest.png"), full_page=True)
    page.close()

    page = browser.new_page(viewport={"width": 1280, "height": 900})
    install(page, watches=[{"id": "watch-1", "name": "Atlas", "target_type": "topic", "target_id": "topic-1", "status": "active"}], schedule=None, latest=None)
    page.goto("http://127.0.0.1:4181/#reports")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text("Save a briefing cadence to begin receiving scheduled output.")).to_be_visible()
    page.screenshot(path=str(OUT / "reports-desktop-empty.png"), full_page=True)
    page.close()

    page = browser.new_page(viewport={"width": 390, "height": 844})
    install(page, watches=[{"id": "watch-1", "name": "Atlas", "target_type": "topic", "target_id": "topic-1", "status": "active"}], schedule={"id": 1, "cadence": "daily", "timezone_name": "America/New_York", "scope": {"monitor_ids": []}, "enabled": True, "paused": False, "next_due_at": "2026-09-12T04:00:00Z"}, latest=BRIEFING, schedule_error=True)
    page.goto("http://127.0.0.1:4181/#reports")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="Briefing preferences")).to_be_visible()
    expect(page.get_by_text("Briefing preferences could not be loaded.")).to_be_visible()
    page.get_by_role("button", name="Try again").click()
    expect(page.get_by_text("A material evidence update was recorded.")).to_be_visible()
    narrow(page)
    page.screenshot(path=str(OUT / "reports-phone-recovered.png"), full_page=True)
    page.close()

    browser.close()

print(f"AST-38 screenshots written to {OUT}")
