from pathlib import Path


DEPLOY = Path("scripts/phase16_windows_deploy.ps1")
SMOKE = Path("scripts/astra05_windows_smoke.ps1")


def test_installed_launcher_has_explicit_success_exit() -> None:
    source = DEPLOY.read_text(encoding="utf-8")
    browser_block = "if (-not `$NoBrowser) {\n    Start-Process 'http://127.0.0.1:$ListenPort/' | Out-Null\n}\nexit 0\n\"@"
    assert browser_block in source


def test_physical_lifecycle_qualification_is_explicit_and_isolated() -> None:
    smoke = SMOKE.read_text(encoding="utf-8")

    for mode in (
        "PhysicalPrepare",
        "PhysicalVerifyWake",
        "PhysicalVerifySignIn",
        "PhysicalCleanup",
    ):
        assert mode in smoke

    assert "Newsroom\\astra05-physical" in smoke
    assert "physical-state.json" in smoke
    assert "physical-qualification.json" in smoke
    assert "ConfirmBrowserOpened" in smoke
    assert "ConfirmLockWake" in smoke
    assert "ConfirmSignIn" in smoke
    assert "Physical qualification refuses to alter legacy Newsroom task name(s)" in smoke
    assert "Refusing to infer cleanup or verification targets" in smoke
    assert "Do not manually start Newsroom after sign-in" in smoke
    assert "the actual Windows sign-in action restored the managed runtime" in smoke

    prepare = smoke[smoke.index("function Invoke-PhysicalPrepare"): smoke.index("function Invoke-PhysicalVerifyWake")]
    assert "-RegisterTasks" in prepare
    assert "-MigrateLegacyTasks" not in prepare
    assert "8127" not in prepare

    cleanup = smoke[smoke.index("function Invoke-PhysicalCleanup"): smoke.index("if ($LifecycleMode -ne 'Hosted')")]
    assert "Read-PhysicalState" in cleanup
    assert "Remove-TaskIfPresent $taskName" in cleanup
    assert "Request-SupervisorStop" in cleanup
    assert "Stop-Process" not in cleanup
