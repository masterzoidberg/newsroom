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
WATCH_ID = "11111111-2222-4333-8444-555555555555"
TOPIC_ID = "top_astra24_fixture"
POLICY_ID = "pol_astra24_fixture"
CATEGORY_ID = "cat_astra24_fixture"
CSRF_TOKEN = "astra24-fixture-csrf"


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

        # First attempt deliberately drops only this API connection. The static
        # fixture server remains alive, reproducing an unreachable API request
        # without contacting or stopping any real Newsroom process.
        if attempt == 1:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.close_connection = True
            return

        expected = {
            "interest": INTEREST,
            "name": WATCH_NAME,
            "primary_terms": [PRIMARY_TERM],
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                self._json({"error": {"message": f"unexpected fixture payload field: {key}"}}, 409)
                return
        if payload.get("request_id") != self.setup_attempts[0].get("request_id"):
            self._json({"error": {"message": "retry request identity changed"}}, 409)
            return

        FixtureHandler.watch_exists = True
        self._json(
            {
                "draft_type": "paused_watch",
                "version": 1,
                "resumed": False,
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
            201,
        )


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _wait_text(driver: webdriver.Chrome, text: str, timeout: float = 12.0) -> None:
    WebDriverWait(driver, timeout).until(lambda current: text in current.find_element(By.TAG_NAME, "body").text)


def _body_text(driver: webdriver.Chrome) -> str:
    return driver.find_element(By.TAG_NAME, "body").text


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
    zoom_before = 0
    zoom_after = 0
    try:
        base = f"http://127.0.0.1:{port}/"
        driver.get(base + "#inbox")
        _wait_text(driver, "Keep the signal in view.")
        if "Create your first Watch" not in _body_text(driver):
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

        _click_text(driver, "Save paused Watch")
        _wait_text(driver, "Could not save this Watch.")
        _wait_text(driver, "Start Newsroom")
        draft_before_reload = driver.execute_script(
            "return window.localStorage.getItem('newsroom.watch-setup.v1')"
        )
        if not draft_before_reload:
            raise RuntimeError("failed save did not retain the setup draft")
        saved_before = json.loads(draft_before_reload)
        if saved_before.get("primary_terms") != [PRIMARY_TERM]:
            raise RuntimeError("failed save did not retain confirmed primary terms")
        screenshots.append(_screenshot(driver, output, "04-api-unreachable.png"))

        driver.refresh()
        _wait_text(driver, "What do you want Newsroom to watch?")
        if driver.find_element(By.ID, "watch-interest").get_attribute("value") != INTEREST:
            raise RuntimeError("reload lost the interest draft")
        if driver.find_element(By.ID, "watch-setup-name").get_attribute("value") != WATCH_NAME:
            raise RuntimeError("reload lost the Watch name")
        if PRIMARY_TERM not in _body_text(driver):
            raise RuntimeError("reload lost the confirmed primary term")
        draft_after_reload = driver.execute_script(
            "return window.localStorage.getItem('newsroom.watch-setup.v1')"
        )
        if json.loads(draft_after_reload).get("request_id") != saved_before.get("request_id"):
            raise RuntimeError("reload changed the retry request identity")
        screenshots.append(_screenshot(driver, output, "05-reload-recovery.png"))

        _click_text(driver, "Save paused Watch")
        _wait_text(driver, "Setup saved as a paused Watch.")
        _wait_text(driver, "Next: Add Sources")
        if len(FixtureHandler.setup_attempts) != 2:
            raise RuntimeError(f"expected exactly two setup attempts, got {len(FixtureHandler.setup_attempts)}")
        identities = [str(item.get("request_id")) for item in FixtureHandler.setup_attempts]
        if len(set(identities)) != 1:
            raise RuntimeError(f"retry created a new request identity: {identities}")
        screenshots.append(_screenshot(driver, output, "06-paused-success.png"))

        driver.refresh()
        _wait_text(driver, "Confirmed primary scope")
        _wait_text(driver, PRIMARY_TERM)
        _wait_text(driver, "Next: Add Sources")
        if "Paused" not in _body_text(driver):
            raise RuntimeError("reloaded saved Watch is not visibly paused")
        screenshots.append(_screenshot(driver, output, "07-paused-reload.png"))

        driver.execute_script("window.location.hash='inbox'")
        _wait_text(driver, "Inbox")
        if "Keep the signal in view." in _body_text(driver):
            raise RuntimeError("returning workspace was trapped in Welcome")
        screenshots.append(_screenshot(driver, output, "08-returning-home.png"))

        driver.set_window_size(390, 844)
        driver.execute_script("window.location.hash='monitors'")
        _wait_text(driver, "Confirmed primary scope")
        _assert_no_horizontal_overflow(driver, "390px Watch view")
        screenshots.append(_screenshot(driver, output, "09-mobile-390.png"))

        driver.set_window_size(1440, 1000)
        driver.execute_script("window.location.hash='monitors'")
        _wait_text(driver, "Confirmed primary scope")
        zoom_before = int(driver.execute_script("return window.innerWidth"))
        for _ in range(5):
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("=").key_up(Keys.CONTROL).perform()
            time.sleep(0.08)
        zoom_after = int(driver.execute_script("return window.innerWidth"))
        if zoom_after >= zoom_before:
            raise RuntimeError(
                f"browser zoom did not reduce the CSS viewport: before={zoom_before}, after={zoom_after}"
            )
        _assert_no_horizontal_overflow(driver, "200% zoom Watch view")
        screenshots.append(_screenshot(driver, output, "10-zoom-200.png"))
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
            "api_unreachable",
            "reload_recovery",
            "paused_success",
            "paused_reload",
            "returning_home",
            "mobile_390",
            "zoom_200",
        ],
        "setup_attempt_count": len(FixtureHandler.setup_attempts),
        "same_retry_identity": len({str(item.get('request_id')) for item in FixtureHandler.setup_attempts}) == 1,
        "server_watch_count": 1 if FixtureHandler.watch_exists else 0,
        "keyboard_focus_sequence": keyboard_focus,
        "zoom_css_viewport_before": zoom_before,
        "zoom_css_viewport_after": zoom_after,
        "browser_zoom_method": "five Ctrl+= steps from default Chrome zoom",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
