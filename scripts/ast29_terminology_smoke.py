from __future__ import annotations

import json
import tempfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright


WATCH_ID = "watch-1"


def smoke(page: Page) -> None:
    vocabulary = [
        {
            "id": "suggestion-1",
            "watch_id": WATCH_ID,
            "term": "unidentified flying object",
            "kind": "alias",
            "origin": "ai",
            "status": "suggested",
            "enabled": 0,
            "expansion_of": "UAP",
            "rationale": "Common alternate wording for the approved term.",
        },
        {
            "id": "approved-1",
            "watch_id": WATCH_ID,
            "term": "official reports",
            "kind": "include",
            "origin": "user",
            "status": "approved",
            "enabled": 1,
            "expansion_of": None,
            "rationale": "Owner-selected monitoring language.",
        },
        {
            "id": "rejected-1",
            "watch_id": WATCH_ID,
            "term": "fictional sightings",
            "kind": "exclude",
            "origin": "deterministic",
            "status": "rejected",
            "enabled": 0,
            "expansion_of": None,
            "rationale": "Not part of this Watch.",
        },
    ]
    calls: list[tuple[str, dict]] = []
    fail_suggestions = False

    def response(route, status=200, body=None):
        route.fulfill(status=status, content_type="application/json", body=json.dumps(body or {}))

    def handle(route):
        nonlocal fail_suggestions
        request = route.request
        path = request.url.split("/api/v1", 1)[-1]
        method = request.method
        payload = json.loads(request.post_data or "{}") if request.post_data else {}

        if method == "GET" and path == "/auth/me":
            return response(route, body={"username": "admin"})
        if method == "GET" and path.startswith("/runtime/status"):
            return response(route, body={"overall": "online", "api": "online", "worker": "online", "scheduler": "online"})
        if method == "GET" and path.startswith("/watches") and "page_size=1" in path:
            return response(route, body={"items": [{"id": WATCH_ID}], "total": 1, "page": 1, "page_size": 1})
        if method == "GET" and path.startswith("/watches") and path == "/watches?page_size=100":
            return response(route, body={"items": [watch()], "total": 1, "page": 1, "page_size": 100})
        if method == "GET" and path == f"/watches/{WATCH_ID}":
            return response(route, body=watch())
        if method == "GET" and path == f"/watches/{WATCH_ID}/health":
            return response(route, body=health())
        if method == "GET" and path == f"/watches/{WATCH_ID}/vocabulary?page_size=100":
            return response(route, body={"items": vocabulary, "total": len(vocabulary), "page": 1, "page_size": 100})
        if method == "GET" and path == f"/watches/{WATCH_ID}/source-candidates?page_size=100":
            return response(route, body={"items": [], "total": 0, "page": 1, "page_size": 100})
        if method == "GET" and path == f"/watches/{WATCH_ID}/sources?page_size=100":
            return response(route, body={"items": [], "total": 0, "page": 1, "page_size": 100})
        if method == "GET" and path == "/topics/topic-1/vocabulary?page_size=100":
            return response(route, body={"items": [{"id": "primary-1", "term": "UAP", "term_type": "include", "concept_kind": "acronym"}], "total": 1, "page": 1, "page_size": 100})
        if method == "GET" and path == "/monitoring-policies?page_size=100":
            return response(route, body={"items": [{"id": "policy-1", "name": "Private hourly", "paid_budget_usd": 0, "base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400, "allowed_channels": ["direct_http"]}], "total": 1, "page": 1, "page_size": 100})
        if method == "GET" and path == "/monitoring-policies/policy-1":
            return response(route, body={"id": "policy-1", "name": "Private hourly", "paid_budget_usd": 0, "base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400, "allowed_channels": ["direct_http"]})
        if method == "GET" and path == "/ai/status":
            return response(route, body=ai_status())
        if method == "POST" and path == f"/watches/{WATCH_ID}/vocabulary/suggest":
            calls.append((path, payload))
            if fail_suggestions:
                return response(route, status=503, body={"error": {"message": "Vocabulary provider is unavailable."}})
            return response(route, status=201, body={"items": vocabulary})
        if method == "POST" and path == f"/watches/{WATCH_ID}/vocabulary":
            calls.append((path, payload))
            vocabulary.append({"id": f"manual-{len(vocabulary)}", "watch_id": WATCH_ID, "term": payload["term"], "kind": payload["kind"], "origin": "user", "status": "approved", "enabled": 1, "expansion_of": payload.get("expansion_of"), "rationale": payload.get("rationale")})
            return response(route, status=201, body=vocabulary[-1])
        if method == "POST" and path.startswith(f"/watches/{WATCH_ID}/vocabulary/") and path.endswith("/review"):
            calls.append((path, payload))
            identifier = path.split("/")[-2]
            next_status = payload["status"]
            for item in vocabulary:
                if item["id"] == identifier:
                    item["status"] = next_status
                    item["enabled"] = 1 if next_status == "approved" else 0
            return response(route, body=next(item for item in vocabulary if item["id"] == identifier))
        return response(route, body={"items": []})

    def watch():
        return {"id": WATCH_ID, "name": "UAP reporting", "target_type": "topic", "target_id": "topic-1", "policy_id": "policy-1", "status": "paused", "discovery_enabled": False}

    def health():
        return {"status": "paused", "discovery_enabled": False, "active_source_count": 0, "pending_source_candidate_count": 0, "pending_vocabulary_suggestion_count": sum(item["status"] == "suggested" for item in vocabulary), "review": {"interest": "UAP reporting", "approved_terms": ["UAP"], "excluded_terms": [], "sources": [], "cadence": {"base_cadence_seconds": 3600, "min_cadence_seconds": 900, "max_cadence_seconds": 86400}, "supported_channels": ["direct_http"], "paid_budget_usd": 0, "paid_mode": "zero-paid", "ready_to_start": False, "blockers": ["Approve at least one usable Source"]}, "progress": {"state": "paused", "label": "Paused", "detail": "Waiting for setup.", "last_attempt": None, "last_result": None, "last_error": None, "retryable": False, "results": []}}

    def ai_status():
        local = {"provider_route": "local", "provider": "local", "model": "local", "reason": "default_local"}
        managed = {"provider_route": "connection", "provider": "openai_compatible", "model": "vocabulary-model", "connection_id": "connection-1", "reason": "configured_connection"}
        return {"generation": 1, "supported_capabilities": ["article_analysis", "vocabulary"], "items": [], "providers": [], "routes": [{"capability": "article_analysis", "provider_route": "local", "connection_id": None, "fallback_policy": "local", "revision": 0, "config_generation": 1, "generation": 1, "effective": local}, {"capability": "vocabulary", "provider_route": "connection", "connection_id": "connection-1", "fallback_policy": "local", "revision": 1, "config_generation": 1, "generation": 1, "effective": managed}], "effective_routes": {"article_analysis": local, "vocabulary": managed}, "paid_enabled": False, "budget_limits": []}

    page.route("**/api/v1/**", handle)
    page.goto("http://127.0.0.1:4173/#monitors")
    page.wait_for_selector("text=Review terminology")
    expect(page.get_by_text("Managed route, paid off")).to_be_visible()
    expect(page.get_by_text("Manual terms always available")).to_be_visible()
    expect(page.get_by_text("suggested · inactive")).to_be_visible()
    expect(page.get_by_text("approved · active")).to_be_visible()
    expect(page.get_by_text("rejected · excluded")).to_be_visible()

    page.get_by_role("button", name="Edit").click()
    page.locator("#edit-vocabulary-term-suggestion-1").fill("unidentified anomalous phenomena")
    page.locator("#edit-vocabulary-kind-suggestion-1").select_option("synonym")
    page.locator("#edit-vocabulary-expansion-suggestion-1").fill("UAP")
    page.locator("#edit-vocabulary-rationale-suggestion-1").fill("Owner-approved alternate wording.")
    page.get_by_role("button", name="Save edited term").click()
    expect(page.get_by_text("unidentified anomalous phenomena")).to_be_visible()
    expect(page.get_by_text("No suggestions waiting for review")).to_be_visible()

    page.get_by_label("Term or meaning").fill("fictional reports")
    page.get_by_label("Kind").select_option("exclude")
    page.get_by_label("Expansion of (optional)").fill("UAP")
    page.get_by_label("Why this term?").fill("Exclude a clearly unrelated meaning.")
    page.get_by_role("button", name="Add approved term").click()
    expect(page.get_by_text("fictional reports")).to_be_visible()
    assert any(path == f"/watches/{WATCH_ID}/vocabulary" and payload == {"term": "fictional reports", "kind": "exclude", "expansion_of": "UAP", "rationale": "Exclude a clearly unrelated meaning."} for path, payload in calls)
    assert any(path.endswith("/suggestion-1/review") and payload == {"status": "rejected"} for path, payload in calls)

    fail_suggestions = True
    page.get_by_role("button", name="Suggest terms").click()
    expect(page.get_by_text("Suggestions could not be loaded.")).to_be_visible()

    page.reload()
    page.wait_for_selector("text=Review terminology")
    expect(page.get_by_text("unidentified anomalous phenomena")).to_be_visible()
    expect(page.get_by_text("fictional reports")).to_be_visible()
    expect(page.get_by_text("suggestion-1")).not_to_be_visible()
    page.get_by_label("Term or meaning").focus()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement?.id") == "watch-vocabulary-kind"
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        smoke(page)
        browser.close()


if __name__ == "__main__":
    main()
