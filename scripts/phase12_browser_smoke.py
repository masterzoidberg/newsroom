from __future__ import annotations

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    output = Path(tempfile.mkdtemp(prefix="newsroom-phase12-"))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        console_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        assert page.get_by_role("heading", name="Keep the signal in view.").is_visible()
        page.screenshot(path=str(output / "login-desktop.png"), full_page=True)
        page.get_by_role("button", name="First run? Set up the local workspace").click()
        page.locator("#auth-username").fill("phase12")
        page.locator("#auth-password").fill("phase12-password")
        page.get_by_role("button", name="Create workspace").click()
        page.wait_for_timeout(1500)
        if page.get_by_text("setup unavailable").is_visible():
            page.get_by_role("button", name="Already set up? Sign in").click()
            page.locator("#auth-password").fill("phase12-password")
            page.get_by_role("button", name="Sign in").click()
        page.wait_for_timeout(1000)
        assert page.get_by_role("heading", name="Inbox").is_visible()
        console_errors.clear()
        assert page.get_by_role("link", name="Story & evidence", exact=True).is_visible()
        page.get_by_role("link", name="Alerts", exact=True).click()
        page.wait_for_url("**/#alerts")
        page.get_by_role("heading", name="Alerts").wait_for()
        page.get_by_role("heading", name="Needs attention").wait_for()
        page.screenshot(path=str(output / "alerts-desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name="Menu").click()
        page.wait_for_timeout(250)
        assert page.get_by_role("navigation", name="Primary navigation").is_visible()
        page.screenshot(path=str(output / "alerts-phone.png"), full_page=True)
        context.set_offline(True)
        page.wait_for_timeout(250)
        assert page.get_by_text("Offline · cached shell only").is_visible()
        unexpected_errors = [error for error in console_errors if "ERR_INTERNET_DISCONNECTED" not in error]
        assert not unexpected_errors, unexpected_errors
        browser.close()
    print(output)


if __name__ == "__main__":
    main()
