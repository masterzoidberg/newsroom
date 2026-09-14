from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:4194"
OUT = ROOT / ".tmp" / "ast41-browser"
OUT.mkdir(parents=True, exist_ok=True)
NOW = "2026-09-12T15:00:00Z"


def response(route, body, status=200):
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


def list_response(items):
    return {"items": items, "total": len(items), "page": 1, "page_size": 100}


def question_item(identifier="rq-existing", wording="Will the launch happen?", state="open"):
    return {
        "id": identifier,
        "question": wording,
        "status": "open",
        "priority": "normal",
        "assessment_state": state,
        "assessment_explanation": "No qualifying canonical evidence is linked yet.",
        "assessment_at": NOW,
        "pursuit_policy": "manual",
    }


def gap_item(status="open"):
    return {
        "id": "gap-launch",
        "question_id": "rq-existing",
        "gap_type": "insufficient_evidence",
        "description": "Verify whether the controlled launch happened.",
        "status": status,
        "rationale": "The question has no verified supporting Claim.",
    }


def watch_item():
    return {
        "id": "watch-question",
        "name": "Launch question Watch",
        "target_type": "research_question",
        "target_id": "rq-existing",
        "policy_id": "policy-question",
        "status": "paused",
        "discovery_enabled": False,
        "priority": "normal",
    }


class Fixture:
    def __init__(self, *, existing_questions=None):
        self.questions = existing_questions or []
        self.watches = []
        self.pursuits = 0
        self.setup_payloads = []
        self.pursuit_payloads = []

    def watch_context(self):
        tasks = []
        if self.pursuits >= 1:
            tasks.append({
                "id": "task-no-findings",
                "status": "completed_no_findings",
                "mode": "manual",
                "outcome": {"outcome_note": "The bounded search completed without qualifying findings."},
                "limits": {"max_queries": 12, "max_candidates": 25, "max_documents": 5},
            })
        if self.pursuits >= 2:
            tasks[-1] = {
                "id": "task-failed",
                "status": "failed",
                "mode": "manual",
                "outcome": {"outcome_note": "The bounded pursuit failed before qualifying evidence was found."},
                "limits": {"max_queries": 12, "max_candidates": 25, "max_documents": 5},
            }
        gap = gap_item("open")
        question = question_item()
        return {
            "question_id": question["id"],
            "question": question["question"],
            "assessment_state": question["assessment_state"],
            "assessment_explanation": question["assessment_explanation"],
            "gaps": [gap],
            "open_gap_count": 1,
            "active_gap": gap,
            "tasks": tasks,
            "evidence_gated": True,
            "candidate_note": "Hypotheses remain review-only until canonical evidence is verified; candidate material is not an accepted Claim.",
        }

    def watch_detail(self):
        watch = watch_item()
        watch["research_question"] = question_item()
        watch["research_context"] = self.watch_context()
        watch["vocabulary"] = []
        watch["source_candidates"] = []
        watch["sources"] = []
        return watch

    def health(self):
        return {
            "watch_id": "watch-question",
            "status": "paused",
            "discovery_enabled": False,
            "active_source_count": 0,
            "pending_source_candidate_count": 0,
            "pending_vocabulary_suggestion_count": 0,
            "last_attempt": None,
            "last_success": None,
            "next_scheduled_run": None,
            "last_error": None,
            "review": {
                "interest": "Will the launch happen?",
                "approved_terms": ["launch"],
                "excluded_terms": [],
                "sources": [],
                "cadence": {"base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400},
                "supported_channels": ["direct_http"],
                "paid_budget_usd": 0,
                "paid_mode": "zero-paid",
                "ready_to_start": False,
                "blockers": ["Approve at least one usable Source"],
            },
            "progress": {
                "state": "idle",
                "label": "Not started",
                "detail": "No collection attempt has completed.",
                "retryable": False,
                "results": [],
            },
        }

    def handle(self, route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.removeprefix("/api/v1")
        query = parse_qs(parsed.query)
        payload = request.post_data_json or {}

        if path == "/auth/me":
            return response(route, {"username": "admin"})
        if path == "/experience":
            return response(route, {"mode": "simple"})
        if path == "/runtime/status":
            component = {"status": "healthy", "detail": "Fixture ready", "managed": True}
            return response(route, {"managed": True, "overall": "idle", "supervisor": component, "components": {"api": component, "worker": component, "scheduler": component}, "work": {"state": "idle", "queued_jobs": 0, "running_jobs": 0}, "controls": {"available": False, "actions": []}, "request_id": "ast41-fixture"})
        if path == "/research-questions" and request.method == "GET":
            return response(route, list_response(self.questions))
        if path == "/watches" and request.method == "GET":
            return response(route, list_response(self.watches))
        if path == "/monitoring-policies" and request.method == "GET":
            return response(route, list_response([]))
        if path == "/watches/setup" and request.method == "POST":
            self.setup_payloads.append(deepcopy(payload))
            self.watches = [watch_item()]
            wording = payload.get("question") or "Will the launch happen?"
            self.questions = [question_item("rq-existing", wording)]
            return response(route, {"draft_type": "question_watch", "version": 1, "resumed": False, "request_id": payload["request_id"], "watch_id": "watch-question", "research_question_id": "rq-existing", "question_created": not bool(self.questions[:-1]), "name": payload["name"], "interest": wording, "question": question_item("rq-existing", wording), "research_question": question_item("rq-existing", wording), "gap": gap_item(), "primary_terms": payload["primary_terms"], "status": "paused", "target_type": "research_question", "target_id": "rq-existing", "discovery_enabled": False, "priority": "normal", "next_action": "add_sources", "policy_id": "policy-question", "paid_budget_usd": 0, "paid_escalation_enabled": False, "monitor_count": 0, "job_count": 0, "policy": {"id": "policy-question", "name": "Question Watch setup policy", "allowed_channels": ["direct_http"], "base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400, "priority": "normal", "query_budget": 10, "paid_budget_usd": 0, "local_model_budget": 10}, "watch": watch_item()}, 201)
        if path.startswith("/research-questions/") and path.endswith("/pursue") and request.method == "POST":
            self.pursuits += 1
            self.pursuit_payloads.append(deepcopy(payload))
            return response(route, {"id": f"attempt-{self.pursuits}", "status": "planned"}, 201)
        if path == "/watches/watch-question" and request.method == "GET":
            return response(route, self.watch_detail())
        if path == "/watches/watch-question/health":
            return response(route, self.health())
        if path == "/watches/watch-question/vocabulary":
            return response(route, list_response([]))
        if path == "/watches/watch-question/source-candidates":
            return response(route, list_response([]))
        if path == "/watches/watch-question/sources":
            return response(route, list_response([]))
        if path == "/monitoring-policies/policy-question":
            return response(route, {"id": "policy-question", "name": "Question Watch setup policy", "allowed_channels": ["direct_http"], "base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400, "paid_budget_usd": 0})
        if path == "/ai/status":
            return response(route, {"paid_enabled": False, "routes": []})
        if path.startswith("/topics/") or path.startswith("/monitors/"):
            return response(route, list_response([]))
        return response(route, list_response([]))


def install(page: Page, fixture: Fixture):
    page.route("**/api/v1/**", fixture.handle)


def assert_narrow(page: Page, label: str):
    metrics = page.evaluate("({innerWidth: window.innerWidth, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth})")
    assert metrics["innerWidth"] == 390 and metrics["clientWidth"] == 390 and metrics["scrollWidth"] <= metrics["clientWidth"] + 1, f"{label}: {metrics}"


def open_question_setup(page: Page):
    page.goto(f"{BASE_URL}/#monitors", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    first_watch = page.get_by_role("button", name="Create your first Watch", exact=True)
    if first_watch.count():
        first_watch.first.click()
    expect(page.get_by_role("heading", name="Watches", exact=True)).to_be_visible()
    page.get_by_label("Research question", exact=True).check()
    expect(page.locator("#watch-question-source")).to_have_value("new")


def new_question_journey(browser):
    fixture = Fixture()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    install(page, fixture)
    open_question_setup(page)
    page.locator("#watch-question").fill("Will the launch happen?")
    expect(page.locator("#watch-setup-name")).to_have_value("")
    expect(page.locator("#watch-primary-term")).to_have_value("")
    page.locator("#watch-setup-name").fill("Launch question Watch")
    page.locator("#watch-primary-term").fill("launch")
    page.get_by_role("button", name="Confirm primary term", exact=True).click()
    page.get_by_role("button", name="Save paused Watch", exact=True).click()
    expect(page.get_by_role("heading", name="Research Question context", exact=True)).to_be_visible()
    expect(page.get_by_text("Will the launch happen?", exact=True).last).to_be_visible()
    expect(page.get_by_role("button", name="Pursue open Gap", exact=True)).to_be_visible()
    assert fixture.setup_payloads[0]["target_type"] == "research_question"
    assert fixture.setup_payloads[0]["question"] == "Will the launch happen?"
    assert fixture.setup_payloads[0]["name"] == "Launch question Watch"
    assert fixture.setup_payloads[0]["primary_terms"] == ["launch"]
    assert "target_id" not in fixture.setup_payloads[0]

    page.get_by_role("button", name="Pursue open Gap", exact=True).click()
    expect(page.get_by_text("Latest bounded Task: No findings", exact=True)).to_be_visible()
    expect(page.get_by_text("Gap remains open.", exact=False)).to_be_visible()
    page.get_by_role("button", name="Pursue open Gap", exact=True).click()
    expect(page.get_by_text("Latest bounded Task: Pursuit failed", exact=True)).to_be_visible()
    expect(page.get_by_text("Gap remains open.", exact=False)).to_be_visible()
    assert fixture.pursuit_payloads == [
        {"mode": "manual", "query_units": 1, "limits": {"max_queries": 12, "max_candidates": 25, "max_documents": 5}},
        {"mode": "manual", "query_units": 1, "limits": {"max_queries": 12, "max_candidates": 25, "max_documents": 5}},
    ]
    page.screenshot(path=str(OUT / "ast41-new-question-failure.png"), full_page=True)

    page.set_viewport_size({"width": 390, "height": 844})
    assert_narrow(page, "question Watch failure at 390px")
    page.get_by_label("Research question", exact=True).check()
    page.locator("#watch-question").focus()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement?.id") == "watch-setup-name"
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 2})
    assert page.evaluate("visualViewport.scale") == 2
    assert_narrow(page, "question Watch at 200% zoom")
    page.screenshot(path=str(OUT / "ast41-question-failure-390-200.png"), full_page=True)
    page.close()


def discard_setup_journey(browser):
    fixture = Fixture()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    install(page, fixture)
    open_question_setup(page)
    page.locator("#watch-question").fill("What is Congress doing about UAPs?")
    page.locator("#watch-setup-name").fill("UAP Congress Watch")
    expect(page.get_by_role("button", name="Discard Watch draft", exact=True)).to_be_visible()
    page.once("dialog", lambda dialog: dialog.dismiss())
    page.get_by_role("button", name="Discard Watch draft", exact=True).click()
    expect(page.locator("#watch-question")).to_have_value("What is Congress doing about UAPs?")
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Discard Watch draft", exact=True).click()
    expect(page.locator("#watch-interest")).to_have_value("")
    expect(page.locator("#watch-setup-name")).to_have_value("")
    assert page.evaluate("window.sessionStorage.getItem('newsroom.watch-setup.v2')") is None
    page.goto(f"{BASE_URL}/#inbox", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    page.goto(f"{BASE_URL}/#monitors", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="Watches", exact=True)).to_be_visible()
    page.get_by_label("Research question", exact=True).check()
    expect(page.locator("#watch-question")).to_have_value("")
    expect(page.locator("#watch-setup-name")).to_have_value("")
    page.close()


def existing_question_journey(browser):
    wording = "Will the satellite launch happen?"
    fixture = Fixture(existing_questions=[question_item("rq-existing", wording)])
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    install(page, fixture)
    open_question_setup(page)
    page.locator("#watch-question-source").select_option("existing")
    expect(page.get_by_label("Select by question wording", exact=True)).to_be_visible()
    page.locator("#watch-existing-question").select_option(label=wording)
    page.locator("#watch-setup-name").fill("Satellite launch Watch")
    page.locator("#watch-primary-term").fill("satellite launch")
    page.get_by_role("button", name="Confirm primary term", exact=True).click()
    page.get_by_role("button", name="Save paused Watch", exact=True).click()
    expect(page.get_by_role("heading", name="Research Question context", exact=True)).to_be_visible()
    assert fixture.setup_payloads[0]["question"] == wording
    assert fixture.setup_payloads[0]["name"] == "Satellite launch Watch"
    assert "target_id" not in fixture.setup_payloads[0]
    page.screenshot(path=str(OUT / "ast41-existing-question.png"), full_page=True)
    page.close()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        discard_setup_journey(browser)
        new_question_journey(browser)
        existing_question_journey(browser)
        browser.close()
    print(f"AST-41 browser evidence written to {OUT}")


if __name__ == "__main__":
    main()
