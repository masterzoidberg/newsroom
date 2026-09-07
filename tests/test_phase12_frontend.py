from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
PUBLIC = FRONTEND / "public"


def test_frontend_source_contains_pwa_shell_and_product_surfaces():
    index = (FRONTEND / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in index

    manifest_path = PUBLIC / "manifest.webmanifest"
    service_worker_path = PUBLIC / "sw.js"
    assert manifest_path.is_file()
    assert service_worker_path.is_file()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "/"

    app_source = "\n".join(
        (FRONTEND / "src" / name).read_text(encoding="utf-8")
        for name in ("App.tsx", "components/AppShell.tsx")
    )
    for label in ("Home", "Stories", "Documents", "Watches", "Alerts", "Settings"):
        assert label in app_source
