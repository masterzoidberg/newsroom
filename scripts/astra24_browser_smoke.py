"""AST-24 interactive browser qualification against an isolated local fixture.

The fixture owns an ephemeral loopback port, serves only the built frontend, and
implements the minimum API surface needed to prove the Welcome -> paused Watch
journey. It never contacts a real Newsroom runtime, trial database, provider, or
external discovery service.
"""
from __future__ import annotations

import argparse
import json
import socket
import socketserver
import threading
import time
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait


INTEREST = "civil aviation safety reporting"
WATCH_NAME = "Aviation safety"
PRIMARY_TERM = "civil aviation safety"
CHANGED_INTEREST = "ocean conservation"
EDITED_AFTER_FAILURE_NAME = "Edited after ambiguous save"
WATCH_ID = "11111111-2222-4333-8444-555555555555"
TOPIC_ID = "top_astra24_fixture"
POLICY_ID = "pol_astra24_fixture"
CATEGORY_ID = "cat_astra24_fixture"
CSRF_TOKEN = "astra24-fixture-csrf"
SETUP_DRAFT_KEY = "newsroom.watch-setup.v2"
SETUP_PENDING_KEY = "newsroom.watch-setup.pending.v1"


class FixtureHandler(SimpleHTTPRequestHandler):
    dist: Path
    watch_exists = False
    setup_attempts: list[dict[str, object]] = []
    delay_watch_list_seconds = 0.0
    lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.dist), **kwargs)

    def log_message(self, _format: str, *_args) -> None:
        return

    def _json(self, payload: object, status: int = 200, *, csrf_cookie: bool = False) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if csrf_cookie:
            self.send_header(
                "Set-Cookie",
                f"newsroom_csrf={CSRF_TOKEN}; Path=/; SameSite=Strict",
            )
        self.end_headers()
        self.wfile.write(body)

    @classmethod
    def _watch(cls) -> dict[str, object]:
        return {
            "id": WATCH_ID,
            "name": WATCH_NAME,
            "target_type": "topic",
            "target_id": TOPIC_ID,
            "policy_id": POLICY_ID,
            "status": "paused",
            "priority": "normal",
            "discovery_enabled": 0,
        }

    @staticmethod
    def _policy() -> dict[str, object]:
        return {
            "id": POLICY_ID,
            "name": "Watch setup",
            "allowed_channels": ["rss", "atom", "direct_http", "page"],
            "base_cadence_seconds": 3600,
            "min_cadence_seconds": 900,
            "max_cadence_seconds": 86400,
            "priority": "normal",
            "query_budget": 12,
            "paid_budget_usd": 0.0,
            "local_model_budget": 100,
        }

    @staticmethod
    def _term() -> dict[str, object]:
        return {
            "id": "term_astra24_fixture",
            "topic_id": TOPIC_ID,
            "term": PRIMARY_TERM,
            "term_normalized": PRIMARY_TERM,
            "term_type": "include",
            "weight": 1.0,
            "concept_kind": "term",
        }

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        split = urlsplit(self.path)
        path = split.path
        query = parse_qs(split.query)

        if path == "/api/v1/auth/me":
            self._json({"username": "astra24"}, csrf_cookie=True)
            return
        if path == "/api/v1/experience":
            self._json({"mode": "simple"})
            return
        if path == "/api/v1/runtime/status":
            self._json(
                {
                    "managed": True,
                    "overall": "idle",
                    "supervisor": {
                        "status": "healthy",
                        "detail": "fixture",
                        "managed": True,
                    },
                    "components": {
                        role: {
                            "status": "healthy",
                            "detail": "fixture",
                            "managed": True,
                        }
                        for role in ("api", "worker", "scheduler")
                    },
                    "work": {"state": "idle", "queued_jobs": 0, "running_jobs": 0},
                    "controls": {"available": True, "actions": []},
                    "request_id": "astra24-runtime-fixture",
                }
            )
            return
        if path == "/api/v1/reports":
            self._json({"items": [], "page": 1, "page_size": 50, "total": 0})
            return
        if path == "/api/v1/attention":
            self._json({"items": []})
            return
        if path == "/api/v1/watches":
            page_size = query.get("page_size", ["25"])[0]
            if page_size == "100" and self.delay_watch_list_seconds:
                time.sleep(self.delay_watch_list_seconds)
            items = [self._watch()] if self.watch_exists else []
            self._json(
                {
                    "items": items,
                    "page": 1,
                    "page_size": int(page_size),
                    "total": len(items),
                }
            )
            return
        if path == "/api/v1/monitoring-policies":
            items = [self._policy()] if self.watch_exists else []
            self._json({"items": items, "page": 1, "page_size": 100, "total": len(items)})
            return
        if path == f"/api/v1/watches/{WATCH_ID}":
            if not self.watch_exists:
                self._json({"error": {"message": "not found"}}, 404)
                return
            self._json(self._watch())
            return
        if path == f"/api/v1/watches/{WATCH_ID}/health":
            self._json(
                {
                    "status": "paused",
                    "discovery_enabled": False,
                    "active_source_count": 0,
                    "pending_source_candidate_count": 0,
                    "pending_vocabulary_suggestion_count": 0,
                    "last_attempt": None,
                    "next_scheduled_run": None,
                    "last_discovery_run": None,
                    "last_error": None,
                }
            )
            return
        if path == f"/api/v1/watches/{WATCH_ID}/vocabulary":
            self._json({"items": [], "page": 1, "page_size": 100, "total": 0})
            return
        if path == f"/api/v1/watches/{WATCH_ID}/source-candidates":
            self._json({"items": [], "page": 1, "page_size": 100, "total": 0})
            return
        if path == f"/api/v1/watches/{WATCH_ID}/sources":
            self._json({"items": [], "page": 1, "page_size": 100, "total": 0})
            return
        if path == f"/api/v1/topics/{TOPIC_ID}/vocabulary":
            self._json({"items": [self._term()], "page": 1, "page_size": 100, "total": 1})
            return

        if path == "/" or not Path(path.lstrip("/")).suffix:
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        path = urlsplit(self.path).path
        if path != "/api/v1/watches/setup":
            self._json({"error": {"message": "fixture route not found"}}, 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        with self.lock:
            self.setup_attempts.append(payload)
            attempt = len(self.setup_attempts)

        expected = {
            "interest": INTEREST,
            "name": WATCH_NAME,
            "primary_terms": [PRIMARY_TERM],
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                self._json({"error": {"message": f"unexpected fixture payload field: {key}"}}, 409)
                return
        if attempt > 1 and payload != self.setup_attempts[0]:
            self._json({"error": {"message": "retry payload changed"}}, 409)
            return

        # The first request commits one logical Watch and then loses its response.
        # This exercises the ambiguous-completion path: reload sees the server
        # record, while retry must still resend the immutable original payload.
        if attempt == 1:
            FixtureHandler.watch_exists = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True
            return

        self._json(
            {
                "draft_type": "paused_watch",
                "version": 1,
                "resumed": True,
                "request_id": payload["request_id"],
                "category_id": CATEGORY_ID,
                "topic_id": TOPIC_ID,
                "policy_id": POLICY_ID,
                "watch_id": WATCH_ID,
                "name": WATCH_NAME,
                "interest": INTEREST,
                "primary_terms": [PRIMARY_TERM],
                "status": "paused",
                "target_type": "topic",
                "discovery_enabled": False,
                "priority": "normal",
                "next_action": "add_sources",
                "paid_budget_usd": 0.0,
                "paid_escalation_enabled": False,
                "monitor_count": 0,
                "job_count": 0,
                "category": {"id": CATEGORY_ID, "name": "Watch setup"},
                "topic": {"id": TOPIC_ID, "name": WATCH_NAME},
                "topic_terms": [self._term()],
                "policy": self._policy(),
                "watch": self._watch(),
            },
            200,
        )


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _wait_text(driver: webdriver.Chrome, text: str, timeout: float = 12.0) -> None:
    expected = text.casefold()
    WebDriverWait(driver, timeout).until(
        lambda current: expected in current.find_element(By.TAG_NAME, "body").text.casefold()
    )


def _body_text(driver: webdriver.Chrome) -> str:
    return driver.find_element(By.TAG_NAME, "body").text


def _contains_text(driver: webdriver.Chrome, text: str) -> bool:
    return text.casefold() in _body_text(driver).casefold()


def _screenshot(driver: webdriver.Chrome, output: Path, name: str) -> str:
    target = output / name
    if not driver.save_screenshot(str(target)) or target.stat().st_size < 1000:
        raise RuntimeError(f"screenshot was not rendered: {target}")
    return name


def _click_text(driver: webdriver.Chrome, label: str) -> None:
    driver.find_element(By.XPATH, f"//button[normalize-space()={json.dumps(label)}]").click()


def _assert_no_horizontal_overflow(driver: webdriver.Chrome, label: str) -> None:
    result = driver.execute_script(
        "return {client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth};"
    )
    if int(result["scroll"]) > int(result["client"]) + 2:
        raise RuntimeError(f"{label} has horizontal overflow: {result}")


def _assert_element_within_viewport(driver: webdriver.Chrome, element, label: str) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
    time.sleep(0.05)
    result = driver.execute_script(
        "const r=arguments[0].getBoundingClientRect();"
        "return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:window.innerWidth,height:window.innerHeight};",
        element,
    )
    if float(result["left"]) < -2 or float(result["right"]) > float(result["width"]) + 2:
        raise RuntimeError(f"{label} escaped horizontal viewport: {result}")
    if float(result["bottom"]) <= 0 or float(result["top"]) >= float(result["height"]):
        raise RuntimeError(f"{label} was not visible after scrolling: {result}")


def _keyboard_sequence(driver: webdriver.Chrome) -> list[str]:
    driver.execute_script("document.getElementById('main-content').focus()")
    sequence: list[str] = []
    for _ in range(12):
        ActionChains(driver).send_keys(Keys.TAB).perform()
        focused = driver.execute_script(
            "const e=document.activeElement; return (e.id || e.textContent || e.tagName || '').trim().slice(0,80);"
        )
        sequence.append(str(focused))
    if "watch-interest" not in sequence or "watch-setup-name" not in sequence:
        raise RuntimeError(f"keyboard traversal did not reach setup fields: {sequence}")
    return sequence


def _storage_json(driver: webdriver.Chrome, key: str) -> dict[str, object] | None:
    raw = driver.execute_script("return window.sessionStorage.getItem(arguments[0])", key)
    return json.loads(raw) if raw else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-dist", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-commit", default="unknown")
    args = parser.parse_args()

    dist = Path(args.frontend_dist).resolve()
    output = Path(args.output).resolve()
    if not (dist / "index.html").is_file():
        raise RuntimeError(f"frontend dist missing index.html: {dist}")
    output.mkdir(parents=True, exist_ok=True)
    FixtureHandler.dist = dist
    FixtureHandler.watch_exists = False
    FixtureHandler.setup_attempts = []
    FixtureHandler.delay_watch_list_seconds = 0.0

    server = ThreadingServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--window-size=1440,1000")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(20)
    screenshots: list[str] = []
    keyboard_focus: list[str] = []
    mobile_metrics: dict[str, int] = {}
    tab_isolation: dict[str, object] = {}
    zoom_before = 0
    zoom_after = 0
    first_handle = ""
    try:
        base = f"http://127.0.0.1:{port}/"
        driver.get(base + "#inbox")
        _wait_text(driver, "Keep the signal in view.")
        if not _contains_text(driver, "Create your first Watch"):
            raise RuntimeError("empty workspace did not render the Welcome primary action")
        screenshots.append(_screenshot(driver, output, "01-welcome-desktop.png"))

        FixtureHandler.delay_watch_list_seconds = 1.5
        _click_text(driver, "Create your first Watch")
        _wait_text(driver, "Loading Watches")
        screenshots.append(_screenshot(driver, output, "02-loading-watches.png"))
        FixtureHandler.delay_watch_list_seconds = 0.0
        _wait_text(driver, "What do you want Newsroom to watch?")

        interest = driver.find_element(By.ID, "watch-interest")
        interest.send_keys(INTEREST)
        name = driver.find_element(By.ID, "watch-setup-name")
        name.clear()
        name.send_keys(WATCH_NAME)
        primary = driver.find_element(By.ID, "watch-primary-term")
        primary.clear()
        primary.send_keys(PRIMARY_TERM)
        _click_text(driver, "Confirm primary term")
        _wait_text(driver, "Confirmed primary monitoring term")
        keyboard_focus = _keyboard_sequence(driver)
        screenshots.append(_screenshot(driver, output, "03-populated-setup.png"))

        # CR-01: a material interest change must invalidate prior approval.
        interest.clear()
        interest.send_keys(CHANGED_INTEREST)
        _wait_text(driver, "Interest changed. Reconfirm at least one primary term before saving.")
        if _contains_text(driver, "Confirmed primary monitoring term"):
            raise RuntimeError("changed interest retained previously confirmed primary scope")
        save_button = driver.find_element(By.XPATH, "//button[normalize-space()='Save paused Watch']")
        if save_button.is_enabled():
            raise RuntimeError("changed interest left Save enabled without reconfirmed scope")
        screenshots.append(_screenshot(driver, output, "04-interest-change-requires-reconfirm.png"))

        interest.clear()
        interest.send_keys(INTEREST)
        primary = driver.find_element(By.ID, "watch-primary-term")
        primary.clear()
        primary.send_keys(PRIMARY_TERM)
        _click_text(driver, "Confirm primary term")
        _wait_text(driver, "Confirmed primary monitoring term")

        # CR-03: a new tab receives its own session draft and request identity.
        first_handle = driver.current_window_handle
        first_draft = _storage_json(driver, SETUP_DRAFT_KEY)
        if not first_draft or not first_draft.get("request_id"):
            raise RuntimeError("primary tab did not persist its setup draft")
        first_request_id = str(first_draft["request_id"])
        driver.switch_to.new_window("tab")
        driver.get(base + "#monitors")
        _wait_text(driver, "What do you want Newsroom to watch?")
        WebDriverWait(driver, 5).until(lambda current: _storage_json(current, SETUP_DRAFT_KEY) is not None)
        second_draft = _storage_json(driver, SETUP_DRAFT_KEY)
        if not second_draft or not second_draft.get("request_id"):
            raise RuntimeError("second tab did not create an independent setup draft")
        second_request_id = str(second_draft["request_id"])
        if second_request_id == first_request_id:
            raise RuntimeError("second tab inherited the first tab request identity")
        second_interest = driver.find_element(By.ID, "watch-interest")
        second_interest.send_keys(CHANGED_INTEREST)
        second_draft_after_edit = _storage_json(driver, SETUP_DRAFT_KEY)
        if not second_draft_after_edit or second_draft_after_edit.get("interest") != CHANGED_INTEREST:
            raise RuntimeError("second tab did not persist its independent edit")
        driver.close()
        driver.switch_to.window(first_handle)
        if driver.find_element(By.ID, "watch-interest").get_attribute("value") != INTEREST:
            raise RuntimeError("second-tab edit overwrote the first tab form")
        first_draft_after_second_tab = _storage_json(driver, SETUP_DRAFT_KEY)
        if not first_draft_after_second_tab or first_draft_after_second_tab.get("request_id") != first_request_id:
            raise RuntimeError("second-tab edit overwrote the first tab request identity")
        tab_isolation = {
            "independent_request_identity": True,
            "first_tab_interest_preserved": True,
        }

        # CR-02: persist one immutable submitted snapshot before the ambiguous POST.
        _click_text(driver, "Save paused Watch")
        _wait_text(driver, "Could not confirm this save.")
        _wait_text(driver, "Start Newsroom")
        draft_before_reload = _storage_json(driver, SETUP_DRAFT_KEY)
        pending_before_reload = _storage_json(driver, SETUP_PENDING_KEY)
        if not draft_before_reload or not pending_before_reload:
            raise RuntimeError("failed save did not retain draft and immutable pending submission")
        expected_submission = {
            "request_id": pending_before_reload.get("request_id"),
            "interest": INTEREST,
            "name": WATCH_NAME,
            "primary_terms": [PRIMARY_TERM],
        }
        if pending_before_reload != expected_submission:
            raise RuntimeError(f"pending submission did not match original save: {pending_before_reload}")

        # Later edits remain separate from the immutable retry payload.
        name = driver.find_element(By.ID, "watch-setup-name")
        name.clear()
        name.send_keys(EDITED_AFTER_FAILURE_NAME)
        edited_draft = _storage_json(driver, SETUP_DRAFT_KEY)
        pending_after_edit = _storage_json(driver, SETUP_PENDING_KEY)
        if not edited_draft or edited_draft.get("name") != EDITED_AFTER_FAILURE_NAME:
            raise RuntimeError("later edit was not retained in editable draft")
        if pending_after_edit != pending_before_reload:
            raise RuntimeError("later edit mutated the immutable pending submission")
        screenshots.append(_screenshot(driver, output, "05-api-unreachable-edited-draft.png"))

        driver.refresh()
        _wait_text(driver, "Create another Watch")
        _wait_text(driver, "A previous save still needs confirmation.")
        if driver.find_element(By.ID, "watch-setup-name").get_attribute("value") != EDITED_AFTER_FAILURE_NAME:
            raise RuntimeError("reload lost edits made after ambiguous save")
        pending_after_reload = _storage_json(driver, SETUP_PENDING_KEY)
        if pending_after_reload != pending_before_reload:
            raise RuntimeError("reload changed the immutable retry payload")
        screenshots.append(_screenshot(driver, output, "06-reload-pending-recovery.png"))

        _click_text(driver, "Retry the same save")
        _wait_text(driver, "Recovered the same saved paused Watch.")
        _wait_text(driver, "Next: Add Sources")
        if len(FixtureHandler.setup_attempts) != 2:
            raise RuntimeError(f"expected exactly two setup attempts, got {len(FixtureHandler.setup_attempts)}")
        if FixtureHandler.setup_attempts[0] != FixtureHandler.setup_attempts[1]:
            raise RuntimeError(f"retry changed submitted payload: {FixtureHandler.setup_attempts}")
        if _storage_json(driver, SETUP_PENDING_KEY) is not None:
            raise RuntimeError("successful retry did not clear pending submission")
        screenshots.append(_screenshot(driver, output, "07-paused-success.png"))

        driver.refresh()
        _wait_text(driver, "Confirmed primary scope")
        _wait_text(driver, PRIMARY_TERM)
        _wait_text(driver, "Next: Add Sources")
        if not _contains_text(driver, "Paused"):
            raise RuntimeError("reloaded saved Watch is not visibly paused")
        screenshots.append(_screenshot(driver, output, "08-paused-reload.png"))

        driver.execute_script("window.location.hash='inbox'")
        _wait_text(driver, "Inbox")
        if _contains_text(driver, "Keep the signal in view."):
            raise RuntimeError("returning workspace was trapped in Welcome")
        screenshots.append(_screenshot(driver, output, "09-returning-home.png"))

        # CR-04: qualify an actual measured 390 CSS-pixel viewport, not outer size.
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": False},
        )
        driver.execute_script("window.location.hash='monitors'")
        _wait_text(driver, "Confirmed primary scope")
        metrics = driver.execute_script(
            "return {innerWidth: window.innerWidth, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth};"
        )
        mobile_metrics = {key: int(value) for key, value in metrics.items()}
        if mobile_metrics["innerWidth"] != 390 or mobile_metrics["clientWidth"] != 390:
            raise RuntimeError(f"mobile qualification did not reach measured 390 CSS px: {mobile_metrics}")
        _assert_no_horizontal_overflow(driver, "390px Watch view")
        setup_interest = driver.find_element(By.ID, "watch-interest")
        _assert_element_within_viewport(driver, setup_interest, "390px interest field")
        screenshots.append(_screenshot(driver, output, "10-mobile-390-setup.png"))
        scope_heading = driver.find_element(By.XPATH, "//*[normalize-space()='Confirmed primary scope']")
        _assert_element_within_viewport(driver, scope_heading, "390px confirmed scope")
        _assert_no_horizontal_overflow(driver, "390px scrolled confirmed scope")
        screenshots.append(_screenshot(driver, output, "11-mobile-390-scope.png"))

        # Reset mobile emulation before the separate effective-200% qualification.
        driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
        driver.set_window_size(1440, 1000)
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False},
        )
        driver.execute_script("window.location.hash='monitors'")
        _wait_text(driver, "Confirmed primary scope")
        zoom_before = int(driver.execute_script("return window.innerWidth"))
        driver.execute_cdp_cmd(
            "Emulation.setDeviceMetricsOverride",
            {"width": 720, "height": 500, "deviceScaleFactor": 2, "mobile": False},
        )
        zoom_after = int(driver.execute_script("return window.innerWidth"))
        if zoom_before != 1440 or zoom_after != 720:
            raise RuntimeError(
                f"effective 200% viewport was not deterministic: before={zoom_before}, after={zoom_after}"
            )
        _assert_no_horizontal_overflow(driver, "200% zoom Watch view")
        screenshots.append(_screenshot(driver, output, "12-zoom-200.png"))
    finally:
        driver.quit()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    manifest = {
        "source_commit": args.source_commit,
        "fixture_host": "127.0.0.1",
        "fixture_port_ephemeral": port != 8127,
        "trial_contacted": False,
        "paid_calls": 0,
        "external_discovery_requests": 0,
        "screenshots": screenshots,
        "states": [
            "empty_welcome",
            "loading",
            "populated_setup",
            "interest_change_requires_reconfirmation",
            "tab_isolation",
            "api_unreachable_after_server_commit",
            "reload_pending_recovery",
            "paused_success",
            "paused_reload",
            "returning_home",
            "mobile_390_setup",
            "mobile_390_scope",
            "zoom_200",
        ],
        "setup_attempt_count": len(FixtureHandler.setup_attempts),
        "same_retry_identity": len({str(item.get('request_id')) for item in FixtureHandler.setup_attempts}) == 1,
        "same_retry_payload": len(FixtureHandler.setup_attempts) == 2 and FixtureHandler.setup_attempts[0] == FixtureHandler.setup_attempts[1],
        "server_watch_count": 1 if FixtureHandler.watch_exists else 0,
        "tab_isolation": tab_isolation,
        "keyboard_focus_sequence": keyboard_focus,
        "mobile_css_viewport": mobile_metrics,
        "zoom_css_viewport_before": zoom_before,
        "zoom_css_viewport_after": zoom_after,
        "browser_zoom_method": "Chrome DevTools Emulation.setDeviceMetricsOverride from 1440 CSS px at DPR 1 to 720 CSS px at DPR 2",
        "browser_zoom_literal_keyboard_shortcut_supported": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
