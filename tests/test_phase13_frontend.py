from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_phase13_workbench_frontend_exposes_research_surfaces():
    source = (FRONTEND / "src" / "views" / "WorkbenchView.tsx").read_text(encoding="utf-8")
    app_source = (FRONTEND / "src" / "App.tsx").read_text(encoding="utf-8")
    for label in ("Global search", "Compare documents", "Monitor health", "Subject page & context"):
        assert label in source
    assert "Research workbench" in app_source or "WorkbenchView" in app_source
