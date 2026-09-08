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
    assert "function Build-PhysicalFrontendArtifact" in smoke
    assert "npm.cmd" in smoke
    assert "npm ci failed" in smoke
    assert "npm run build failed" in smoke

    prepare = smoke[smoke.index("function Invoke-PhysicalPrepare"): smoke.index("function Invoke-PhysicalVerifyWake")]
    assert "-RegisterTasks" in prepare
    assert "-MigrateLegacyTasks" not in prepare
    assert "8127" not in prepare
    assert prepare.index("Build-PhysicalFrontendArtifact") < prepare.index("& powershell.exe")
    assert prepare.index("Write-PhysicalState $state") < prepare.index("$launch = Invoke-StartLauncher")

    cleanup = smoke[smoke.index("function Invoke-PhysicalCleanup"): smoke.index("if ($LifecycleMode -ne 'Hosted')")]
    assert "Read-PhysicalState" in cleanup
    assert "Remove-TaskIfPresent $taskName" in cleanup
    assert "Request-SupervisorStop" in cleanup
    assert "Stop-Process" not in cleanup


def test_physical_smoke_defaults_are_windows_powershell_safe_and_reads_do_not_block_replace() -> None:
    smoke = SMOKE.read_text(encoding="utf-8")
    param_block = smoke[: smoke.index(")\n\n$ErrorActionPreference")]

    assert "[string]$SourceRoot = ''" in param_block
    assert "[string]$OutputDirectory = ''" in param_block
    assert "$PSScriptRoot" not in param_block
    assert "if ([string]::IsNullOrWhiteSpace($SourceRoot))" in smoke
    assert "$SourceRoot = Join-Path $PSScriptRoot '..'" in smoke
    assert "function Read-JsonShared" in smoke
    assert "[System.IO.FileShare]::Delete" in smoke

    snapshot = smoke[smoke.index("function Get-RoleSnapshot"): smoke.index("function Get-ManagedSnapshot")]
    assert "$owner = Read-JsonShared $ownerPath" in snapshot
    assert "$heartbeat = Read-JsonShared $heartbeatPath" in snapshot
    assert "Snapshot=$snapshotJson" in smoke
