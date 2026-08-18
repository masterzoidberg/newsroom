from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_phase14_frontend_build_and_evidence_safe_rendering():
    completed = subprocess.run(
        ["npm.cmd", "run", "build"],
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    view = (FRONTEND / "src" / "views" / "AskView.tsx").read_text(encoding="utf-8")
    assert "Ask Newsroom" in view
    assert "resolvable" in view
    assert "dangerouslySetInnerHTML" not in view
