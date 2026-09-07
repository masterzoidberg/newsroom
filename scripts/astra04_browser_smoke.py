"""Safe AST-04 browser evidence against an isolated mocked local API."""
from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
import socketserver
import subprocess
import threading
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit


class FixtureHandler(SimpleHTTPRequestHandler):
    fixture_state = "idle"
    dist: Path

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(self.dist), **kwargs)

    def log_message(self, _format: str, *_args) -> None:
        return

    def _json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        path = urlsplit(self.path).path
        if path == "/api/v1/auth/me":
            self._json({"username": "astra04"})
            return
        if path == "/api/v1/experience":
            self._json({"mode": "simple"})
            return
        if path == "/api/v1/settings":
            self._json({"items": [], "page": 1, "page_size": 100, "total": 0})
            return
        if path == "/api/v1/budgets/limits":
            self._json({"items": []})
            return
        if path == "/api/v1/notification-preferences":
            self._json({"browser_enabled": False, "permission_state": "default", "online": True})
            return
        if path == "/api/v1/runtime/status":
            if self.fixture_state == "unavailable":
                self._json({"error": {"code": "fixture_unavailable", "message": "fixture unavailable"}}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            worker_status = "stale" if self.fixture_state == "degraded" else "healthy"
            worker_detail = "heartbeat is stale" if worker_status == "stale" else "heartbeat is fresh"
            self._json(
                {
                    "managed": True,
                    "overall": "degraded" if worker_status == "stale" else "idle",
                    "supervisor": {"status": "healthy", "detail": "heartbeat is fresh", "managed": True},
                    "components": {
                        "api": {"status": "healthy", "detail": "heartbeat is fresh", "managed": True},
                        "worker": {"status": worker_status, "detail": worker_detail, "managed": True},
                        "scheduler": {"status": "healthy", "detail": "heartbeat is fresh", "managed": True},
                    },
                    "work": {"state": "idle", "queued_jobs": 0, "running_jobs": 0},
                    "controls": {
                        "available": True,
                        "actions": ["restart_api", "restart_worker", "restart_scheduler", "stop_newsroom"],
                    },
                    "request_id": "fixture-request",
                }
            )
            return
        if path == "/" or not Path(path.lstrip("/")).suffix:
            self.path = "/index.html"
        super().do_GET()


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def _chrome() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("no Chromium-compatible browser found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontend-dist", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    dist = Path(args.frontend_dist).resolve()
    output = Path(args.output).resolve()
    if not (dist / "index.html").is_file():
        raise RuntimeError(f"frontend dist missing index.html: {dist}")
    output.mkdir(parents=True, exist_ok=True)
    FixtureHandler.dist = dist

    server = ThreadingServer(("127.0.0.1", 0), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    browser = _chrome()
    try:
        for state, filename in (
            ("idle", "01-idle.png"),
            ("degraded", "02-worker-stale.png"),
            ("unavailable", "03-api-unavailable.png"),
        ):
            FixtureHandler.fixture_state = state
            target = output / filename
            subprocess.run(
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--hide-scrollbars",
                    "--window-size=1440,1000",
                    "--virtual-time-budget=3000",
                    f"--screenshot={target}",
                    f"http://127.0.0.1:{port}/#settings",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
            )
            if target.stat().st_size < 1000:
                raise RuntimeError(f"screenshot was not rendered: {target}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    manifest = {
        "states": ["idle", "worker_stale", "api_unavailable"],
        "browser": Path(browser).name,
        "fixture_host": "127.0.0.1",
        "trial_contacted": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
