from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_shell_uses_runtime_status_not_health_or_browser_network_as_service_truth():
    app = (FRONTEND / "App.tsx").read_text(encoding="utf-8")
    shell = (FRONTEND / "components" / "AppShell.tsx").read_text(encoding="utf-8")

    assert '"/runtime/status"' in app
    assert '"/health"' not in app
    assert "Browser network available" in app
    assert "Browser network offline" in app
    assert "Newsroom service is unavailable" in app
    assert "installed Newsroom launcher" in app
    assert "Synced" not in shell
    assert "Ready · idle" in shell
    assert "Needs attention" in shell
    assert "Service unavailable" in shell


def test_shell_exposes_named_bounded_recovery_controls():
    shell = (FRONTEND / "components" / "AppShell.tsx").read_text(encoding="utf-8")
    runtime_types = (FRONTEND / "lib" / "runtime.ts").read_text(encoding="utf-8")

    assert "Status &amp; recovery" in shell
    for label in ("Restart API", "Restart worker", "Restart scheduler", "Stop Newsroom"):
        assert label in shell
    for action in ("restart_api", "restart_worker", "restart_scheduler", "stop_newsroom"):
        assert action in runtime_types
    assert "arbitrary" not in runtime_types.casefold()


def test_ast04_browser_smoke_is_isolated_and_covers_required_failure_states():
    script = (ROOT / "scripts" / "astra04_browser_smoke.py").read_text(encoding="utf-8")
    assert "127.0.0.1" in script
    assert "8127" not in script
    assert "worker_stale" in script
    assert "api_unavailable" in script
    assert "01-idle.png" in script
    assert "02-worker-stale.png" in script
    assert "03-api-unavailable.png" in script
