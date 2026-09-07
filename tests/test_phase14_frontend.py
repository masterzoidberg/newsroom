from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_phase14_frontend_exposes_evidence_safe_rendering():
    view = (FRONTEND / "src" / "views" / "AskView.tsx").read_text(encoding="utf-8")
    assert "Ask Newsroom" in view
    assert "resolvable" in view
    assert "dangerouslySetInnerHTML" not in view
