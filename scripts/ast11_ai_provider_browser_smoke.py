"""AST-11 browser regression against an isolated in-browser API fixture.

The fixture intercepts only the local ``/api/v1`` requests made by the built
frontend. It records the submitted sentinel credential, never returns it, and
keeps all provider behavior synthetic. No Newsroom runtime, database, or
external provider is contacted.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Page, Route, sync_playwright


SENTINEL = "ast11-browser-secret-do-not-persist"
PROVIDER_ID = "provider_ast11_fixture"
BASE_URL = "https://provider.example.test/v1"


class MockAPI:
    def __init__(self) -> None:
        self.provider: dict[str, Any] | None = None
        self.generation = 1
        self.route_connection: str | None = None
        self.paid_enabled = False
        self.budget_limits: list[dict[str, Any]] = []
        self.usage: list[dict[str, Any]] = []
        self.credential_requests: list[dict[str, Any]] = []
        self.request_bodies: list[tuple[str, str, dict[str, Any]]] = []
        self.response_bodies: list[tuple[str, str]] = []
        self.remove_credential_attempts = 0

    def _provider(self) -> dict[str, Any]:
        assert self.provider is not None
        return self.provider

    def _bump(self) -> None:
        self.generation += 1
        if self.provider is not None:
            self.provider["generation"] = self.generation
            self.provider["config_generation"] = self.generation

    def _effective(self) -> dict[str, Any]:
        provider = self.provider
        selected = provider is not None and self.route_connection == provider["id"]
        usable = selected and bool(provider["enabled"]) and bool(provider["credential_configured"])
        if usable:
            return {
                "provider_route": "connection",
                "provider": provider["display_name"],
                "model": provider["model"],
                "connection_id": provider["id"],
                "reason": "managed_connection",
            }
        return {
            "provider_route": "local",
            "provider": "local",
            "model": "local",
            "connection_id": None,
            "reason": "default_local" if not selected else "connection_unavailable",
        }

    def _route(self) -> dict[str, Any]:
        effective = self._effective()
        return {
            "capability": "article_analysis",
            "provider_route": "connection" if self.route_connection else "local",
            "connection_id": self.route_connection,
            "fallback_policy": "local",
            "revision": self.generation,
            "config_generation": self.generation,
            "generation": self.generation,
            "effective": effective,
        }

    def _provider_payload(self) -> dict[str, Any]:
        provider = self._provider()
        return dict(provider)

    def status(self) -> dict[str, Any]:
        route = self._route()
        effective = route["effective"]
        operation = {
            "capability": "article_analysis",
            "provider_route": effective["provider_route"],
            "provider": effective["provider"],
            "model": effective["model"],
            "generation": self.generation,
            "source": "managed_metadata" if self.provider is not None else "default_local",
            "reason": effective["reason"],
            "connection_id": effective["connection_id"],
        }
        items = [self._provider_payload()] if self.provider is not None else []
        return {
            "generation": self.generation,
            "supported_capabilities": ["article_analysis"],
            "items": items,
            "providers": items,
            "routes": [route],
            "effective_routes": {"article_analysis": effective},
            "effective_operation_routes": {"article_analysis": operation},
            "paid_enabled": self.paid_enabled,
            "budget_limits": list(self.budget_limits),
        }

    @staticmethod
    def _error(message: str) -> dict[str, Any]:
        return {"error": {"message": message}}

    def fulfill(self, route: Route, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload)
        self.response_bodies.append((urlsplit(route.request.url).path, body))
        route.fulfill(
            status=status,
            content_type="application/json",
            headers={"Cache-Control": "no-store"},
            body=body,
        )

    def handle(self, route: Route) -> None:
        request = route.request
        path = urlsplit(request.url).path
        api_path = path.removeprefix("/api/v1")
        raw = request.post_data or "{}"
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}
        if request.method != "GET":
            self.request_bodies.append((request.method, api_path, data))

        if request.method == "GET" and api_path == "/auth/me":
            self.fulfill(route, {"username": "ast11"})
        elif request.method == "GET" and api_path == "/watches":
            self.fulfill(route, {"items": [{"id": "watch_ast11"}], "page": 1, "page_size": 1, "total": 1})
        elif request.method == "GET" and api_path == "/runtime/status":
            self.fulfill(
                route,
                {
                    "managed": True,
                    "overall": "idle",
                    "supervisor": {"status": "healthy", "detail": "fixture", "managed": True},
                    "components": {
                        role: {"status": "healthy", "detail": "fixture", "managed": True}
                        for role in ("api", "worker", "scheduler")
                    },
                    "work": {"state": "idle", "queued_jobs": 0, "running_jobs": 0},
                    "controls": {"available": True, "actions": []},
                    "request_id": "ast11-fixture",
                },
            )
        elif request.method == "GET" and api_path == "/settings":
            self.fulfill(route, {"items": [], "page": 1, "page_size": 100, "total": 0})
        elif request.method == "GET" and api_path == "/notification-preferences":
            self.fulfill(route, {"browser_enabled": False, "permission_state": "default", "online": True})
        elif request.method == "GET" and api_path == "/experience":
            self.fulfill(route, {"mode": "simple"})
        elif request.method == "GET" and api_path == "/ai/status":
            self.fulfill(route, self.status())
        elif request.method == "GET" and api_path == "/provider-usage":
            self.fulfill(route, {"items": list(self.usage), "page": 1, "page_size": 50, "total": len(self.usage)})
        elif request.method == "POST" and api_path == "/ai/providers":
            self.provider = {
                "id": PROVIDER_ID,
                "display_name": data["display_name"],
                "adapter_kind": "openai_compatible",
                "base_url": data["base_url"],
                "model": data["model"],
                "enabled": False,
                "credential_required": data["credential_required"],
                "credential_configured": False,
                "credential_ref_version": None,
                "credential_cleanup_required": False,
                "credential_removal_required": False,
                "max_input_chars": data.get("max_input_chars", 24000),
                "max_output_tokens": data.get("max_output_tokens", 1200),
                "revision": 1,
                "config_generation": self.generation,
                "generation": self.generation,
                "validation_status": "unvalidated",
                "validation_code": None,
                "validation_revision": None,
                "validated_at": None,
                "created_at": "2026-09-12T12:00:00Z",
                "updated_at": "2026-09-12T12:00:00Z",
                "supported_capabilities": ["article_analysis"],
            }
            self.fulfill(route, self._provider_payload(), 201)
        elif request.method == "PATCH" and api_path == f"/ai/providers/{PROVIDER_ID}":
            if data.get("display_name") == "stale edit":
                self.fulfill(route, self._error("Provider revision is stale."), 409)
            elif self.provider is None or data.get("expected_revision") != self.provider["revision"]:
                self.fulfill(route, self._error("Provider revision is stale."), 409)
            else:
                provider = self._provider()
                for key in ("display_name", "base_url", "model", "enabled", "credential_required", "max_input_chars", "max_output_tokens"):
                    if key in data:
                        provider[key] = data[key]
                provider["revision"] += 1
                self._bump()
                self.fulfill(route, self._provider_payload())
        elif request.method == "PUT" and api_path == f"/ai/providers/{PROVIDER_ID}/credential":
            secret = data.get("secret")
            self.credential_requests.append(dict(data))
            if not isinstance(secret, str) or not secret:
                self.fulfill(route, self._error("Credential is required."), 422)
            elif self.provider is None or data.get("expected_revision") != self.provider["revision"]:
                self.fulfill(route, self._error("Provider revision is stale."), 409)
            else:
                provider = self._provider()
                provider["credential_configured"] = True
                provider["credential_ref_version"] = 1
                provider["revision"] += 1
                self._bump()
                self.fulfill(route, self._provider_payload())
        elif request.method == "POST" and api_path == f"/ai/providers/{PROVIDER_ID}/test":
            if self.provider is None or data.get("expected_revision") != self.provider["revision"]:
                self.fulfill(route, self._error("Provider revision is stale."), 409)
            else:
                now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                provider = self._provider()
                provider["validation_status"] = "passed"
                provider["validation_code"] = "structured_output_ok"
                provider["validation_revision"] = provider["revision"]
                provider["validated_at"] = now
                provider["revision"] += 1
                self._bump()
                self.usage.insert(
                    0,
                    {
                        "id": "usage_ast11_test",
                        "capability": "article_analysis",
                        "provider": provider["display_name"],
                        "request_type": "validation",
                        "query_units": 1,
                        "token_units": 32,
                        "estimated_cost_usd": 0.01,
                        "latency_ms": 42,
                        "outcome": json.dumps({"status": "passed"}),
                        "created_at": now,
                    },
                )
                self.fulfill(
                    route,
                    {
                        "capability": "article_analysis",
                        "connection_id": PROVIDER_ID,
                        "status": "passed",
                        "validation_status": "passed",
                        "validation_code": "structured_output_ok",
                        "validation_revision": provider["validation_revision"],
                        "validated_at": now,
                        "revision": provider["revision"],
                        "generation": self.generation,
                        "provider": provider["display_name"],
                        "model": provider["model"],
                    },
                )
        elif request.method == "DELETE" and api_path == f"/ai/providers/{PROVIDER_ID}/credential":
            self.remove_credential_attempts += 1
            if self.remove_credential_attempts == 1:
                self.fulfill(route, self._error("Credential vault unavailable."), 503)
            elif self.provider is None or data.get("expected_revision") != self.provider["revision"]:
                self.fulfill(route, self._error("Provider revision is stale."), 409)
            else:
                provider = self._provider()
                provider["credential_configured"] = False
                provider["credential_ref_version"] = None
                provider["enabled"] = False
                provider["revision"] += 1
                self.route_connection = None
                self._bump()
                self.fulfill(route, self._provider_payload())
        elif request.method == "DELETE" and api_path == f"/ai/providers/{PROVIDER_ID}":
            if self.provider is None or data.get("expected_revision") != self.provider["revision"]:
                self.fulfill(route, self._error("Provider revision is stale."), 409)
            elif self.provider["credential_configured"]:
                self.fulfill(route, {"id": PROVIDER_ID, "deleted": False, "generation": self.generation, "removal_required": True})
            else:
                self.provider = None
                self.route_connection = None
                self._bump()
                self.fulfill(route, {"id": PROVIDER_ID, "deleted": True, "generation": self.generation})
        elif request.method == "PUT" and api_path == "/ai/routes/article_analysis":
            self.route_connection = data.get("connection_id") if data.get("provider_route") == "connection" else None
            self._bump()
            self.fulfill(route, self._route())
        elif request.method == "PUT" and api_path == "/budgets/paid-enabled":
            self.paid_enabled = bool(data.get("enabled"))
            self.fulfill(route, {"enabled": self.paid_enabled, "updated_at": "2026-09-12T12:00:00Z"})
        elif request.method == "PUT" and api_path == "/budgets/limits":
            self.budget_limits = [{
                "id": "limit_ast11_global",
                "scope_type": "global",
                "scope_id": None,
                "period": data["period"],
                "cap_type": data["cap_type"],
                "cap_value": data["cap_value"],
                "enabled": True,
                "created_at": "2026-09-12T12:00:00Z",
                "updated_at": "2026-09-12T12:00:00Z",
            }]
            self.fulfill(route, self.budget_limits[0])
        else:
            self.fulfill(route, self._error(f"Unhandled fixture route: {request.method} {api_path}"), 404)


def wait_for_settings(page: Page) -> None:
    page.get_by_role("heading", name="AI Providers").wait_for(state="visible")
    page.get_by_role("heading", name="Paid routing and limits").wait_for(state="visible")


def assert_no_overflow(page: Page) -> None:
    dimensions = page.evaluate(
        "() => ({innerWidth: window.innerWidth, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth})"
    )
    assert dimensions["innerWidth"] == 390, dimensions
    assert dimensions["clientWidth"] == 390, dimensions
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 1, dimensions
    for selector in (".ai-provider-card", ".ai-budget-form", ".ai-settings"):
        for box in page.locator(selector).all():
            bounds = box.bounding_box()
            assert bounds is not None and bounds["x"] >= -1 and bounds["x"] + bounds["width"] <= 391, (selector, bounds)


def run(url: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    fixture = MockAPI()
    console_errors: list[str] = []
    page_errors: list[str] = []
    browser_requests: list[str] = []

    def record_console(message: Any) -> None:
        if message.type == "error" and not message.text.startswith("Failed to load resource:"):
            console_errors.append(message.text)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        page.route("**/api/v1/**", fixture.handle)
        page.on("console", record_console)
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.on("request", lambda request: browser_requests.append(request.url))
        page.on("dialog", lambda dialog: dialog.accept())

        page.goto(f"{url.rstrip('/')}/#settings")
        page.wait_for_load_state("networkidle")
        wait_for_settings(page)
        assert page.get_by_text("No managed providers", exact=True).is_visible()
        assert page.get_by_text("Local / offline", exact=True).first.is_visible()

        page.get_by_role("button", name="Add provider").first.click()
        page.get_by_label("Provider preset").select_option("minimax_token_plan")
        assert page.get_by_label("Display name").input_value() == "MiniMax Token Plan"
        assert page.get_by_label("Model").input_value() == "MiniMax-M3"
        assert page.get_by_label("Base URL").input_value() == "https://api.minimax.cn/v1"
        assert page.get_by_label("MiniMax Token Plan subscription key").count() == 1
        assert page.get_by_role("link", name="Get a Token Plan key", exact=True).is_visible()
        page.get_by_role("button", name="Cancel", exact=True).first.click()

        page.get_by_role("button", name="Add provider").first.click()
        for field_id in (
            "ai-provider-name",
            "ai-provider-model",
            "ai-provider-url",
            "ai-provider-input-limit",
            "ai-provider-output-limit",
            "ai-provider-secret",
        ):
            assert page.locator(f"label[for='{field_id}']").count() == 1
        page.get_by_label("Display name").fill("Fixture OpenAI")
        page.get_by_label("Model").fill("fixture-model")
        page.get_by_label("Base URL").fill(BASE_URL)
        page.get_by_label("Credential (optional until enable)").fill(SENTINEL)
        page.get_by_role("button", name="Add provider", exact=True).last.click()
        page.get_by_role("heading", name="Fixture OpenAI").wait_for(state="visible")
        assert page.locator("input[type='password']").count() == 0
        assert SENTINEL not in page.content()
        storage = page.evaluate("() => ({local: {...localStorage}, session: {...sessionStorage}})")
        assert SENTINEL not in json.dumps(storage)
        assert len(fixture.credential_requests) == 1
        assert fixture.credential_requests[0].get("secret") == SENTINEL
        assert all(SENTINEL not in body for _, body in fixture.response_bodies)

        test_button = page.get_by_role("button", name="Test structured output")
        assert test_button.is_disabled()
        page.locator(f"#ai-test-authorize-{PROVIDER_ID}").check()
        assert test_button.is_enabled()
        test_button.click()
        page.get_by_text("structured_output_ok", exact=True).wait_for(state="visible")
        assert page.get_by_text("$0.01", exact=True).first.is_visible()

        page.get_by_role("button", name="Enable", exact=True).click()
        page.get_by_text("enabled", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Set as Article Analysis default", exact=True).click()
        page.get_by_text("Managed", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Turn paid routing on", exact=True).click()
        page.get_by_role("button", name="Turn paid routing off", exact=True).wait_for(state="visible")
        page.get_by_label("Limit value").fill("2.50")
        page.get_by_role("button", name="Save global limit", exact=True).click()
        page.get_by_text("active", exact=True).wait_for(state="visible")

        page.get_by_role("button", name="Edit", exact=True).click()
        page.get_by_label("Model").fill("fixture-model-v2")
        page.get_by_label("Display name").fill("stale edit")
        page.get_by_role("button", name="Save provider", exact=True).click()
        page.locator(".ai-editor [role='alert']").wait_for(state="visible")
        page.get_by_label("Display name").fill("Fixture OpenAI reviewed")
        page.get_by_role("button", name="Save provider", exact=True).click()
        page.get_by_role("heading", name="Fixture OpenAI reviewed").wait_for(state="visible")
        assert page.get_by_text("fixture-model-v2", exact=True).first.is_visible()

        page.screenshot(path=str(output / "desktop-provider-settings.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 1000})
        page.reload()
        page.wait_for_load_state("networkidle")
        wait_for_settings(page)
        assert_no_overflow(page)
        general_cards = page.locator(".content-grid > .section-card").all()
        assert len(general_cards) == 3
        general_boxes = [card.bounding_box() for card in general_cards]
        assert all(box is not None and box["width"] > 300 for box in general_boxes), general_boxes
        assert general_boxes[0]["x"] == general_boxes[1]["x"] == general_boxes[2]["x"], general_boxes
        page.screenshot(path=str(output / "mobile-provider-settings.png"), full_page=True)

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.get_by_role("button", name="Remove credential", exact=True).click()
        page.locator("[role='alert']").filter(has_text="Credential vault unavailable.").wait_for(state="visible")
        page.get_by_role("button", name="Remove credential", exact=True).click()
        page.get_by_text("Not configured", exact=True).wait_for(state="visible")
        page.get_by_role("button", name="Remove provider", exact=True).click()
        page.get_by_text("No managed providers", exact=True).wait_for(state="visible")
        assert page.get_by_text("Local / offline", exact=True).first.is_visible()
        assert fixture.route_connection is None
        assert fixture.paid_enabled is True
        assert fixture.budget_limits[0]["cap_value"] == 2.5
        assert not page.locator("input[type='password']").count()
        assert SENTINEL not in page.content()

        assert not page_errors, page_errors
        assert not console_errors, console_errors
        assert all("provider.example.test" not in request for request in browser_requests)
        browser.close()

    manifest = {
        "task": "AST-11",
        "fixture_host": "in_browser_route_mock",
        "desktop_viewport": [1440, 1000],
        "mobile_viewport": [390, 1000],
        "journeys": [
            "settings empty state",
            "MiniMax Token Plan preset and subscription-key guidance",
            "add provider and credential clearing",
            "explicit bounded test authorization",
            "enable, route, paid switch and typed budget",
            "stale edit recovery",
            "failed credential removal and retry",
            "provider deletion and local fallback",
        ],
        "credential_request_count": len(fixture.credential_requests),
        "credential_response_leaks": [path for path, body in fixture.response_bodies if SENTINEL in body],
        "external_provider_calls": [request for request in browser_requests if "provider.example.test" in request],
        "console_errors": console_errors,
        "page_errors": page_errors,
        "trial_contacted": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = run(args.url, Path(args.output).resolve())
    if manifest["credential_response_leaks"] or manifest["external_provider_calls"]:
        raise RuntimeError("credential or external-provider leak detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
