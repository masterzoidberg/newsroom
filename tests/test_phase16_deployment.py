from __future__ import annotations

from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase16_windows_deploy.ps1"


def test_windows_deployment_script_keeps_validation_safe_and_api_private():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "Refusing production install: source worktree is not clean" in script
    assert "no install root, runtime root, tasks, or Tailscale configuration was changed" in script
    assert "-RestartCount 5" in script
    assert "-RestartInterval (New-TimeSpan -Minutes 1)" in script
    assert "tailscale.exe serve --bg --https=443 \"http://127.0.0.1:$Port\"" in script
    assert "0.0.0.0" not in script
