from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_phase13_workbench_frontend_builds_and_exposes_research_surfaces():
    result = subprocess.run(
        ["npm.cmd", "run", "build"],
        cwd=FRONTEND,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    source = (FRONTEND / "src" / "views" / "WorkbenchView.tsx").read_text(encoding="utf-8")
    app_source = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    for label in ("Global search", "Compare documents", "Monitor coverage", "Subject page & context"):
        assert label in source
    assert "Research workbench" in app_source or "WorkbenchView" in app_source
