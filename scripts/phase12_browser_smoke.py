from __future__ import annotations

from pathlib import Path

from playwright.sync_api import APIRequestContext, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "reviews" / "phase12-screenshots"
BASE_URL = "http://127.0.0.1:8127"


def _post(request: APIRequestContext, path: str, csrf: str, payload: dict | None = None) -> dict:
    response = request.post(
        f"{BASE_URL}/api/v1{path}",
        headers={"X-CSRF-Token": csrf},
        data=payload,
    )
    assert response.ok, f"{path}: {response.status} {response.text()}"
    return response.json()


def _open(page: Page, name: str, heading: str) -> None:
    page.get_by_role("link", name=name, exact=True).click()
    page.get_by_role("heading", name=heading).wait_for()


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        console_errors: list[str] = []
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.goto(BASE_URL, wait_until="networkidle")
        assert page.get_by_role("heading", name="Keep the signal in view.").is_visible()
        page.screenshot(path=str(OUTPUT / "01-login-desktop.png"), full_page=True)
        credentials = {"username": "phase12", "password": "phase12-password"}
        setup = context.request.post(
            f"{BASE_URL}/api/v1/auth/setup", data=credentials
        )
        assert setup.status == 201, setup.text()
        login = context.request.post(
            f"{BASE_URL}/api/v1/auth/login", data=credentials
        )
        assert login.ok, login.text()
        page.reload(wait_until="networkidle")
        page.get_by_role("heading", name="Inbox").wait_for()

        csrf = next(
            cookie["value"]
            for cookie in context.cookies()
            if cookie["name"] == "newsroom_csrf"
        )
        seeded = _post(
            context.request,
            "/runs/manual",
            csrf,
            {
                "source": {
                    "name": "Phase 12 Official",
                    "slug": "phase-12-official",
                    "source_kind": "official",
                    "default_quality": "primary",
                },
                "document": {
                    "canonical_url": "https://phase12.test/atlas",
                    "title": "Atlas launch announcement",
                },
                "document_version": {
                    "retrieved_at": "2026-08-16T12:00:00Z",
                    "content_hash": "phase12-browser-v1",
                    "content_kind": "excerpt",
                },
                "story": {"headline": "Atlas launch"},
                "claims": [
                    {
                        "proposition": "Atlas launched on August 16",
                        "importance": "major",
                        "evidence": [
                            {
                                "excerpt": "Atlas launched on August 16.",
                                "locator_type": "paragraph",
                                "locator_value": "p1",
                                "relationship": "supports",
                            }
                        ],
                        "state": "supported",
                        "accept": True,
                    }
                ],
                "revision": {
                    "headline": "Atlas launched",
                    "summary": "The official source announced the Atlas launch.",
                    "why_it_matters": "The launch is a material product milestone.",
                    "material_change": True,
                    "claim_indexes": [0],
                    "propositions": [
                        {
                            "text": "Atlas launched on August 16.",
                            "claim_indexes": [0],
                        }
                    ],
                },
            },
        )
        story_id = seeded["story"]["id"]
        _post(
            context.request,
            f"/stories/{story_id}/evolution",
            csrf,
            {
                "document_id": seeded["document"]["id"],
                "update_class": "material_update",
                "material_change": True,
            },
        )

        _open(page, "Story & evidence", "Story & evidence")
        page.locator("#story-id").fill(story_id)
        page.get_by_role("button", name="Inspect Story").click()
        page.get_by_role("heading", name="Claims and exact spans").wait_for()
        assert page.get_by_text("Atlas launched on August 16", exact=True).is_visible()
        page.screenshot(path=str(OUTPUT / "02-story-evidence-desktop.png"), full_page=True)

        _open(page, "Research questions", "Research questions")
        page.locator("#question").fill("Which independent primary source confirms the launch date?")
        page.get_by_role("button", name="Add question").click()
        page.get_by_text(
            "Which independent primary source confirms the launch date?", exact=True
        ).wait_for()
        page.screenshot(path=str(OUTPUT / "03-question-desktop.png"), full_page=True)

        _open(page, "Alerts", "Alerts")
        page.locator("#rule-name").fill("Material report updates")
        page.get_by_role("button", name="Save rule").click()
        page.get_by_text("Material report updates", exact=True).wait_for()

        _open(page, "Reports", "Living Reports")
        page.locator("#report-name").fill("Atlas status")
        page.locator("#report-target-id").fill(story_id)
        page.get_by_role("button", name="Create Living Report").click()
        page.get_by_role("button", name="Generate revision").click()
        page.get_by_text("Closed-world audit passed").wait_for()
        page.screenshot(path=str(OUTPUT / "04-report-desktop.png"), full_page=True)

        _open(page, "Alerts", "Alerts")
        page.get_by_text("Material update: Atlas status", exact=True).wait_for()
        page.screenshot(path=str(OUTPUT / "05-alert-desktop.png"), full_page=True)

        page.set_viewport_size({"width": 820, "height": 1180})
        page.screenshot(path=str(OUTPUT / "06-alert-tablet.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name="Menu").click()
        assert page.get_by_role("navigation", name="Primary navigation").is_visible()
        page.screenshot(path=str(OUTPUT / "07-alert-phone.png"), full_page=True)

        registration = page.evaluate("navigator.serviceWorker.ready.then(r => Boolean(r.active))")
        assert registration is True
        console_errors.clear()
        context.set_offline(True)
        page.wait_for_timeout(250)
        assert page.get_by_text("Offline · cached shell only").is_visible()
        page.screenshot(path=str(OUTPUT / "08-offline-workspace-phone.png"), full_page=True)
        page.reload(wait_until="domcontentloaded")
        page.get_by_role("heading", name="Keep the signal in view.").wait_for()
        page.screenshot(path=str(OUTPUT / "09-offline-shell-phone.png"), full_page=True)
        unexpected_errors = [
            error for error in console_errors if "ERR_INTERNET_DISCONNECTED" not in error
        ]
        assert not unexpected_errors, unexpected_errors
        browser.close()
    print(OUTPUT)


if __name__ == "__main__":
    main()
