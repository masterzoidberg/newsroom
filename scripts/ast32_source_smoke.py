from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = os.environ.get("AST32_BASE_URL", "http://127.0.0.1:4193")
WATCH_ID = "watch-1"
NOW = "2026-09-12T14:00:00Z"
OUT = ROOT / ".tmp" / "ast32-browser"
OUT.mkdir(parents=True, exist_ok=True)


def response(route, body, status=200):
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(body),
    )


def list_response(items):
    return {"items": items, "total": len(items), "page": 1, "page_size": 100}


def candidate(
    identifier: str,
    name: str,
    homepage_url: str,
    *,
    discovery_method: str,
    rationale: str,
    status: str = "suggested",
    provenance: dict | None = None,
):
    return {
        "id": identifier,
        "watch_id": WATCH_ID,
        "name": name,
        "homepage_url": homepage_url,
        "feed_url": None,
        "domain": urlparse(homepage_url).netloc,
        "discovery_method": discovery_method,
        "status": status,
        "rationale": rationale,
        "provenance": provenance or {},
        "authority_context": "Independent publication",
        "limitations": "Review the page before relying on it.",
    }


def source(
    identifier: str,
    name: str,
    homepage_url: str,
    monitor_id: str,
    *,
    outcome: str = "not_run",
    checked_at: str | None = None,
):
    return {
        "source": {
            "id": identifier,
            "name": name,
            "homepage_url": homepage_url,
            "feed_url": None,
            "domain": urlparse(homepage_url).netloc,
            "enabled": True,
        },
        "monitor": {
            "id": monitor_id,
            "target_id": identifier,
            "enabled": True,
            "last_result": outcome,
            "last_run_at": checked_at,
        },
    }


class Fixture:
    def __init__(
        self,
        mode: str,
        *,
        candidates: list[dict] | None = None,
        sources: list[dict] | None = None,
    ):
        self.mode = mode
        self.candidates = deepcopy(candidates or [])
        self.sources = deepcopy(sources or [])
        self.discovery_calls: list[dict] = []
        self.review_calls: list[tuple[str, dict]] = []
        self.monitor_patch_calls: list[tuple[str, dict]] = []
        self.request_log: list[tuple[str, str, dict]] = []
        self.activity_errors = {
            item["monitor"]["id"]
            for item in self.sources
            if item["monitor"].get("last_result") in {"error", "failed"}
        }
        self.search_results = [
            {
                "id": "source-existing",
                "name": "Trusted Existing",
                "homepage_url": "https://existing.example/news",
                "feed_url": "https://existing.example/feed.xml",
                "domain": "existing.example",
                "enabled": True,
            }
        ]
        self.last_discovery_status: str | None = None
        self.last_discovery_run: str | None = None
        self.last_error: str | None = None

    @property
    def watch(self):
        return {
            "id": WATCH_ID,
            "name": "Signal Watch",
            "target_type": "topic",
            "target_id": "topic-1",
            "policy_id": "policy-1",
            "status": "active",
            "discovery_enabled": True,
        }

    def health(self):
        active_count = len(self.sources)
        pending_count = sum(
            item.get("status", "suggested") == "suggested"
            for item in self.candidates
        )
        review_sources = [
            {
                "name": item["source"]["name"],
                "domain": item["source"].get("domain"),
                "usable": True,
                "enabled": bool(item["monitor"].get("enabled", True)),
            }
            for item in self.sources
        ]
        return {
            "watch_id": WATCH_ID,
            "status": "active",
            "discovery_enabled": True,
            "active_source_count": active_count,
            "pending_source_candidate_count": pending_count,
            "pending_vocabulary_suggestion_count": 0,
            "last_attempt": NOW,
            "last_success": None,
            "next_scheduled_run": None,
            "last_discovery_run": self.last_discovery_run,
            "last_discovery_status": self.last_discovery_status,
            "last_error": self.last_error,
            "review": {
                "interest": "Signal Watch",
                "approved_terms": ["Signal"],
                "excluded_terms": [],
                "sources": review_sources,
                "cadence": {
                    "base_cadence_seconds": 3600,
                    "min_cadence_seconds": 900,
                    "max_cadence_seconds": 86400,
                    "next_check_at": None,
                },
                "supported_channels": ["direct_http"],
                "paid_budget_usd": 0,
                "paid_mode": "zero-paid",
                "ready_to_start": bool(active_count),
                "blockers": [] if active_count else ["Approve at least one usable Source"],
            },
            "progress": {
                "state": "idle",
                "label": "Not started",
                "detail": "No collection attempt has completed.",
                "last_attempt": None,
                "last_result": None,
                "last_error": None,
                "retryable": False,
                "results": [],
            },
        }

    def runtime_status(self):
        component = {"status": "healthy", "detail": "Fixture ready", "managed": True}
        return {
            "managed": True,
            "overall": "idle",
            "supervisor": component,
            "components": {
                "api": component,
                "worker": component,
                "scheduler": component,
            },
            "work": {"state": "idle", "queued_jobs": 0, "running_jobs": 0},
            "controls": {"available": False, "actions": []},
            "request_id": "ast32-fixture",
        }

    def activity(self, monitor_id: str):
        if monitor_id in self.activity_errors:
            return None
        item = next(
            (
                item
                for item in self.sources
                if item["monitor"]["id"] == monitor_id
            ),
            None,
        )
        outcome = item["monitor"].get("last_result", "not_run") if item else "not_run"
        if outcome == "not_run":
            return []
        return [
            {
                "id": f"activity-{monitor_id}",
                "monitor_id": monitor_id,
                "outcome": outcome,
                "error_code": None,
                "observed_at": item["monitor"].get("last_run_at") if item else None,
            }
        ]

    def monitor_health(self):
        items = []
        for item in self.sources:
            monitor = item["monitor"]
            failed = monitor.get("last_result") in {"error", "failed"}
            items.append(
                {
                    "monitor": deepcopy(monitor),
                    "health": {
                        "latest_status": "failed" if failed else monitor.get("last_result", "not_run"),
                        "last_checked_at": monitor.get("last_run_at"),
                        "failed_acquisition": 1 if failed else 0,
                        "failed_processing": 0,
                    },
                }
            )
        return {"items": items}

    def record(self, request, path, payload):
        self.request_log.append((request.method, path, payload))

    def _discover(self):
        self.last_discovery_run = NOW
        self.discovery_calls.append({"limit": 25})
        if self.mode == "populated":
            self.last_discovery_status = "completed"
            self.candidates = [
                candidate(
                    "candidate-primary",
                    "Aurora Bulletin",
                    "https://signal.example/briefing",
                    discovery_method="ai_suggestion",
                    rationale="It covers the approved Signal scope with a clear publication identity.",
                    provenance={
                        "capability": "source_discovery",
                        "trigger": "empty_corpus",
                        "provider_route": "local",
                    },
                ),
                candidate(
                    "candidate-duplicate",
                    "Aurora Bulletin mirror",
                    "https://signal.example/briefing",
                    discovery_method="ai_suggestion",
                    rationale="Duplicate canonical URL retained for review history.",
                    provenance={
                        "capability": "source_discovery",
                        "trigger": "empty_corpus",
                        "provider_route": "local",
                    },
                ),
            ]
        elif self.mode == "unsafe":
            self.last_discovery_status = "unsafe_filtered"
            self.last_error = (
                "Unsafe or invalid recommendations were filtered. "
                "Add a Source manually or try again later."
            )
            self.candidates = []
        else:
            self.last_discovery_status = "empty"
            self.candidates = []

    def _review_candidate(self, identifier: str, status: str):
        item = next(item for item in self.candidates if item["id"] == identifier)
        item["status"] = status
        self.review_calls.append(
            (f"/watches/{WATCH_ID}/source-candidates/{identifier}/review", {"status": status})
        )
        if status != "approved":
            return item

        canonical_url = item.get("homepage_url") or item.get("feed_url")
        existing = next(
            (
                attached
                for attached in self.sources
                if attached["source"].get("homepage_url") == canonical_url
                or attached["source"].get("feed_url") == canonical_url
            ),
            None,
        )
        if existing is None:
            self.sources.append(
                source(
                    f"source-{identifier}",
                    item["name"],
                    canonical_url,
                    f"monitor-{identifier}",
                )
            )

        for other in self.candidates:
            if (
                other["id"] != identifier
                and other.get("status") == "suggested"
                and (other.get("homepage_url") or other.get("feed_url")) == canonical_url
            ):
                other["status"] = "rejected"
                other["rationale"] = "Retained as rejected history because its canonical URL is already attached."
        return item

    def handle(self, route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.removeprefix("/api/v1")
        query = parse_qs(parsed.query)
        try:
            payload = json.loads(request.post_data or "{}")
        except json.JSONDecodeError:
            payload = {}
        self.record(request, path, payload)

        if request.method == "GET" and path == "/auth/me":
            return response(route, {"username": "admin"})
        if request.method == "GET" and path == "/experience":
            return response(route, {"mode": "simple"})
        if request.method == "GET" and path == "/runtime/status":
            return response(route, self.runtime_status())
        if request.method == "GET" and path == "/watches" and query.get("page_size") == ["1"]:
            return response(route, {"items": [{"id": WATCH_ID}], "total": 1, "page": 1, "page_size": 1})
        if request.method == "GET" and path == "/watches" and query.get("page_size") == ["100"]:
            return response(route, list_response([self.watch]))
        if request.method == "GET" and path == f"/watches/{WATCH_ID}":
            return response(route, self.watch)
        if request.method == "GET" and path == f"/watches/{WATCH_ID}/health":
            return response(route, self.health())
        if request.method == "GET" and path == f"/watches/{WATCH_ID}/vocabulary":
            return response(route, list_response([]))
        if request.method == "GET" and path == f"/watches/{WATCH_ID}/source-candidates":
            return response(route, list_response(deepcopy(self.candidates)))
        if request.method == "GET" and path == f"/watches/{WATCH_ID}/sources":
            return response(route, list_response(deepcopy(self.sources)))
        if request.method == "GET" and path == "/topics/topic-1/vocabulary":
            return response(
                route,
                list_response(
                    [
                        {
                            "id": "primary-1",
                            "term": "Signal",
                            "term_type": "include",
                            "concept_kind": "term",
                        }
                    ]
                ),
            )
        if request.method == "GET" and path == "/monitoring-policies":
            return response(
                route,
                list_response(
                    [
                        {
                            "id": "policy-1",
                            "name": "Private hourly",
                            "paid_budget_usd": 0,
                            "base_cadence_seconds": 3600,
                            "min_cadence_seconds": 900,
                            "max_cadence_seconds": 86400,
                            "allowed_channels": ["direct_http"],
                        }
                    ]
                ),
            )
        if request.method == "GET" and path == "/monitoring-policies/policy-1":
            return response(
                route,
                {
                    "id": "policy-1",
                    "name": "Private hourly",
                    "paid_budget_usd": 0,
                    "base_cadence_seconds": 3600,
                    "min_cadence_seconds": 900,
                    "max_cadence_seconds": 86400,
                    "allowed_channels": ["direct_http"],
                },
            )
        if request.method == "GET" and path == "/ai/status":
            return response(
                route,
                {
                    "generation": 1,
                    "supported_capabilities": ["source_discovery", "vocabulary"],
                    "items": [],
                    "providers": [],
                    "routes": [],
                    "effective_routes": {},
                    "paid_enabled": False,
                    "budget_limits": [],
                },
            )
        if request.method == "GET" and path == "/sources" and "q" in query:
            return response(route, list_response(self.search_results))
        if request.method == "GET" and path == "/sources":
            return response(route, list_response([item["source"] for item in self.sources]))
        if request.method == "GET" and path == "/source-suggestions":
            return response(route, {"items": []})
        if request.method == "GET" and path == "/diagnostics/monitor-health":
            return response(route, self.monitor_health())
        if request.method == "GET" and path.startswith("/monitors/") and path.endswith("/activity"):
            monitor_id = path.split("/")[2]
            activity = self.activity(monitor_id)
            if activity is None:
                return response(route, {"error": {"message": "Monitor activity is unavailable."}}, status=503)
            return response(route, list_response(activity))
        if request.method == "GET" and path == "/attention":
            return response(route, {"items": []})
        if request.method == "GET" and path == "/review-boundary/changes":
            return response(route, {"cursor": None, "since": NOW, "items": [], "next_cursor": None, "has_more": False, "bounded": True})

        if request.method == "POST" and path == f"/watches/{WATCH_ID}/discover-sources":
            if self.mode == "unavailable":
                return response(
                    route,
                    {"error": {"message": "Source discovery provider is unavailable."}},
                    status=503,
                )
            self._discover()
            return response(route, {"items": deepcopy(self.candidates)})
        if request.method == "POST" and path == f"/watches/{WATCH_ID}/source-candidates":
            identifier = f"candidate-manual-{len(self.candidates) + 1}"
            existing = next(
                (item for item in self.search_results if item["id"] == payload.get("source_id")),
                {},
            )
            homepage_url = payload.get("homepage_url") or payload.get("feed_url") or existing.get("homepage_url")
            item = candidate(
                identifier,
                payload["name"],
                homepage_url,
                discovery_method=payload.get("discovery_method", "manual"),
                rationale=payload.get("rationale", "Added manually by the owner."),
            )
            item["source_id"] = payload.get("source_id")
            self.candidates.append(item)
            return response(route, item, status=201)
        if request.method == "POST" and path.startswith(f"/watches/{WATCH_ID}/source-candidates/") and path.endswith("/review"):
            identifier = path.split("/")[-2]
            return response(route, self._review_candidate(identifier, payload["status"]))
        if request.method == "PATCH" and path.startswith("/monitors/"):
            monitor_id = path.split("/")[2]
            self.monitor_patch_calls.append((monitor_id, payload))
            for item in self.sources:
                if item["monitor"]["id"] == monitor_id:
                    item["monitor"]["enabled"] = bool(payload.get("enabled", True))
                    item["monitor"]["last_result"] = "no_change"
                    item["monitor"]["last_run_at"] = NOW
            self.activity_errors.discard(monitor_id)
            monitor = next(
                (
                    item["monitor"]
                    for item in self.sources
                    if item["monitor"]["id"] == monitor_id
                ),
                {"id": monitor_id},
            )
            return response(route, monitor)

        return response(route, {"items": []})


def install(page: Page, fixture: Fixture):
    page.route("**/api/v1/**", fixture.handle)


def open_view(page: Page, view: str):
    page.goto(f"{BASE_URL}/#{view}", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("heading", name="Watches" if view == "monitors" else "Sources", exact=True)).to_be_visible()


def stat_value(page: Page, label: str) -> str:
    card = page.locator(".stat-card").filter(has_text=label).first
    return card.locator("strong").inner_text()


def assert_no_horizontal_overflow(page: Page, label: str):
    metrics = page.evaluate(
        r"""() => ({
            innerWidth: window.innerWidth,
            clientWidth: document.documentElement.clientWidth,
            scrollWidth: document.documentElement.scrollWidth,
            offenders: Array.from(document.querySelectorAll("*"))
                .map((element) => {
                    const rect = element.getBoundingClientRect();
                    return {
                        tag: element.tagName,
                        id: element.id,
                        className: typeof element.className === "string" ? element.className : "",
                        left: Math.round(rect.left),
                        right: Math.round(rect.right),
                        text: (element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 160),
                    };
                })
                .filter((item) => item.right > document.documentElement.clientWidth + 1 || item.left < -1)
                .sort((left, right) => (right.right - right.left) - (left.right - left.left))
                .slice(0, 12),
        })"""
    )
    assert metrics["scrollWidth"] <= metrics["clientWidth"] + 1, f"{label}: {metrics}"


def assert_focus_sequence(page: Page, ids: list[str]):
    page.locator("#manual-source-name").focus()
    for expected in ids:
        page.keyboard.press("Tab")
        actual = page.evaluate("document.activeElement?.id")
        assert actual == expected, f"Expected focus on {expected}, got {actual}"


def populated_and_responsive(browser):
    fixture = Fixture("populated")
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    install(page, fixture)
    open_view(page, "monitors")

    expect(page.get_by_role("heading", name="Recommended Sources", exact=True)).to_be_visible()
    expect(page.get_by_text("unverified", exact=True).first).to_be_visible()
    expect(page.get_by_text("Recommendation provenance", exact=True).first).to_be_visible()
    expect(page.get_by_text("Manual fallback:", exact=False).first).to_be_visible()

    page.get_by_role("button", name="Recommend Sources", exact=True).click()
    expect(page.get_by_text("Aurora Bulletin", exact=True)).to_be_visible()
    expect(page.get_by_text("Aurora Bulletin mirror", exact=True)).to_be_visible()
    candidate_row = page.locator(".resource-row").filter(has_text="Aurora Bulletin").first
    candidate_row.get_by_role("button", name="Approve and attach", exact=True).click()
    expect(page.get_by_text("Aurora Bulletin mirror", exact=True)).to_be_visible()
    duplicate_row = page.locator(".resource-row").filter(has_text="Aurora Bulletin mirror").first
    expect(duplicate_row.get_by_text("rejected", exact=True)).to_be_visible()
    expect(page.get_by_text("Aurora Bulletin", exact=True)).to_have_count(2)
    assert stat_value(page, "Active Sources") == "1"
    assert len(fixture.sources) == 1
    assert fixture.discovery_calls == [{"limit": 25}]
    assert any(
        path == f"/watches/{WATCH_ID}/source-candidates/candidate-primary/review"
        and payload == {"status": "approved"}
        for _method, path, payload in fixture.request_log
    )

    page.set_viewport_size({"width": 390, "height": 844})
    assert_no_horizontal_overflow(page, "390px populated")
    assert_focus_sequence(page, ["manual-source-homepage", "manual-source-feed", "manual-source-rationale"])
    page.screenshot(path=str(OUT / "ast32-populated-390.png"), full_page=True)

    page.set_viewport_size({"width": 390, "height": 844})
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setPageScaleFactor", {"pageScaleFactor": 2})
    assert page.evaluate("visualViewport.scale") == 2
    assert_no_horizontal_overflow(page, "200% visual zoom")
    expect(page.locator("#manual-source-name")).to_be_visible()
    expect(page.get_by_role("button", name="Approve and attach", exact=False)).to_have_count(0)
    page.screenshot(path=str(OUT / "ast32-populated-200-percent-equivalent.png"), full_page=True)
    page.close()


def empty_manual_and_existing(browser):
    fixture = Fixture("empty")
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    install(page, fixture)
    open_view(page, "monitors")

    expect(page.get_by_text("No recommendations yet", exact=True)).to_be_visible()
    expect(page.get_by_text("Manual fallback:", exact=False).first).to_be_visible()

    page.locator("#existing-source-search").fill("Trusted")
    page.get_by_role("button", name="Search Sources", exact=True).click()
    expect(page.get_by_text("Trusted Existing", exact=True)).to_be_visible()
    existing_row = page.locator('[aria-label="Existing Source search results"]').locator(".resource-row").filter(has_text="Trusted Existing")
    existing_row.get_by_role("button", name="Preview Source", exact=True).click()
    expect(page.get_by_text("Trusted Existing", exact=True)).to_be_visible()
    existing_candidate = page.locator(".resource-row").filter(has_text="Trusted Existing").first
    existing_candidate.get_by_role("button", name="Reject", exact=True).click()
    expect(page.get_by_text("rejected", exact=True)).to_be_visible()

    page.locator("#manual-source-name").fill("Manual Gazette")
    page.locator("#manual-source-homepage").fill("https://manual.example/news")
    page.locator("#manual-source-feed").fill("https://manual.example/feed.xml")
    page.locator("#manual-source-rationale").fill("Owner-selected manual fallback.")
    page.get_by_role("button", name="Preview Source for approval", exact=True).click()
    manual_row = page.locator(".resource-row").filter(has_text="Manual Gazette").first
    expect(manual_row).to_be_visible()
    expect(page.get_by_text("No attached Sources", exact=True)).to_be_visible()
    assert stat_value(page, "Active Sources") == "0"
    manual_row.get_by_role("button", name="Approve and attach", exact=True).click()
    expect(page.get_by_text("Manual Gazette", exact=True)).to_have_count(2)
    assert stat_value(page, "Active Sources") == "1"
    assert len(fixture.sources) == 1
    assert any(
        path == f"/watches/{WATCH_ID}/source-candidates"
        and payload.get("discovery_method") == "manual"
        for _method, path, payload in fixture.request_log
    )
    page.set_viewport_size({"width": 390, "height": 844})
    assert_no_horizontal_overflow(page, "390px manual fallback")
    page.screenshot(path=str(OUT / "ast32-manual-390.png"), full_page=True)
    page.close()


def discovery_fallbacks(browser):
    unsafe = Fixture("unsafe")
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    install(page, unsafe)
    open_view(page, "monitors")
    page.get_by_role("button", name="Recommend Sources", exact=True).click()
    expect(page.get_by_role("alert").get_by_text("Unsafe or invalid recommendations were filtered", exact=False)).to_be_visible()
    expect(page.get_by_role("alert").get_by_text("Manual fallback remains available above", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Approve and attach", exact=True)).to_have_count(0)
    assert unsafe.candidates == []
    assert len(unsafe.sources) == 0
    page.close()

    unavailable = Fixture("unavailable")
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    install(page, unavailable)
    open_view(page, "monitors")
    page.get_by_role("button", name="Recommend Sources", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Source discovery provider is unavailable.")
    expect(page.get_by_role("button", name="Preview Source for approval", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Recommend Sources", exact=True)).to_be_enabled()
    page.screenshot(path=str(OUT / "ast32-unavailable-manual-fallback.png"), full_page=True)
    page.close()


def partial_source_failure(browser):
    sources = [
        source(
            "source-failed",
            "Failed source",
            "https://failed.example/news",
            "monitor-failed",
            outcome="error",
            checked_at="2026-09-12T13:00:00Z",
        ),
        source(
            "source-good",
            "Successful sibling",
            "https://good.example/news",
            "monitor-good",
            outcome="no_change",
            checked_at="2026-09-12T13:30:00Z",
        ),
    ]
    fixture = Fixture("partial", sources=sources)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    install(page, fixture)
    open_view(page, "monitors")

    failed_row = page.locator(".resource-row").filter(has_text="Failed source").last
    good_row = page.locator(".resource-row").filter(has_text="Successful sibling").last
    expect(failed_row.get_by_text("Failed", exact=True)).to_be_visible()
    expect(failed_row.get_by_text("Last failure: error", exact=False)).to_be_visible()
    expect(failed_row.get_by_text("Health detail unavailable:", exact=False)).to_be_visible()
    expect(failed_row.get_by_role("button", name="Retry source", exact=True)).to_be_visible()
    expect(good_row.get_by_text("Healthy · no change", exact=True)).to_be_visible()
    expect(good_row.get_by_text("Last failure: None recorded", exact=True)).to_be_visible()
    expect(page.get_by_text("one failed page or feed never hides a successful sibling", exact=False)).to_be_visible()

    failed_row.get_by_role("button", name="Retry source", exact=True).click()
    expect(good_row.get_by_text("Successful sibling", exact=True)).to_be_visible()
    expect(page.get_by_text("Failed", exact=True)).to_have_count(0)
    assert fixture.monitor_patch_calls
    monitor_id, payload = fixture.monitor_patch_calls[-1]
    assert monitor_id == "monitor-failed"
    assert payload["enabled"] is True
    assert "next_check_at" in payload
    page.set_viewport_size({"width": 390, "height": 844})
    assert_no_horizontal_overflow(page, "390px partial failure")
    page.screenshot(path=str(OUT / "ast32-partial-390.png"), full_page=True)
    page.close()


def admin_source_health(browser):
    sources = [
        source(
            "source-failed",
            "Failed source",
            "https://failed.example/news",
            "monitor-failed",
            outcome="error",
            checked_at="2026-09-12T13:00:00Z",
        ),
        source(
            "source-good",
            "Successful sibling",
            "https://good.example/news",
            "monitor-good",
            outcome="no_change",
            checked_at="2026-09-12T13:30:00Z",
        ),
    ]
    fixture = Fixture("partial", sources=sources)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    install(page, fixture)
    open_view(page, "sources")

    expect(page.get_by_role("heading", name="Source health", exact=True)).to_be_visible()
    failed_row = page.locator(".resource-row").filter(has_text="Failed source")
    good_row = page.locator(".resource-row").filter(has_text="Successful sibling")
    expect(failed_row.get_by_text("Failed", exact=True)).to_be_visible()
    expect(failed_row.get_by_text("Last failure:", exact=False)).to_be_visible()
    expect(failed_row.get_by_role("button", name="Retry source", exact=True)).to_be_visible()
    expect(good_row.get_by_text("Healthy · change found", exact=True)).to_be_visible()
    expect(page.get_by_text("Shared Source edits affect every Watch", exact=False)).to_be_visible()

    failed_row.get_by_role("button", name="Retry source", exact=True).click()
    expect(good_row.get_by_text("Successful sibling", exact=True)).to_be_visible()
    expect(page.get_by_text("Failed", exact=True)).to_have_count(0)
    assert fixture.monitor_patch_calls
    assert any(
        method == "GET" and path == "/diagnostics/monitor-health"
        for method, path, _payload in fixture.request_log
    )
    page.set_viewport_size({"width": 390, "height": 844})
    assert_no_horizontal_overflow(page, "390px admin health")
    page.screenshot(path=str(OUT / "ast32-admin-health-390.png"), full_page=True)
    page.close()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        populated_and_responsive(browser)
        empty_manual_and_existing(browser)
        discovery_fallbacks(browser)
        partial_source_failure(browser)
        admin_source_health(browser)
        browser.close()
    print(f"AST-32 browser evidence written to {OUT}")


if __name__ == "__main__":
    main()
