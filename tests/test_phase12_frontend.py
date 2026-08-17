from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_frontend_production_build_contains_pwa_shell_and_product_surfaces():
    result = subprocess.run(
        ["npm.cmd", "run", "build"],
        cwd=FRONTEND,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    dist = FRONTEND / "dist"
    index = (dist / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in index
    assert (dist / "manifest.webmanifest").is_file()
    assert (dist / "sw.js").is_file()

    manifest = json.loads((dist / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"

    app_source = "\n".join(
        (FRONTEND / "src" / name).read_text(encoding="utf-8")
        for name in ("App.tsx", "components/AppShell.tsx")
    )
    for label in ("Inbox", "Story & evidence", "Documents", "Monitors", "Alerts", "Settings"):
        assert label in app_source
