from __future__ import annotations

from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "phase16_windows_deploy.ps1"
SMOKE = Path(__file__).resolve().parents[1] / "scripts" / "astra05_windows_smoke.ps1"


def test_windows_deployment_script_keeps_validation_safe_and_api_private():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "Refusing production install: source worktree is not clean" in script
    assert "no install root, runtime root, shortcut, tasks, or Tailscale configuration was changed" in script
    assert "-RestartCount 5" in script
    assert "-RestartInterval (New-TimeSpan -Minutes 1)" in script
    assert 'tailscale.exe serve --bg --https=443 "http://127.0.0.1:$Port"' in script
    assert "0.0.0.0" not in script


def test_windows_install_uses_one_namespaced_sign_in_authority():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "start-newsroom.ps1" in script
    assert "Start Newsroom.lnk" in script
    assert "newsroom.runtime supervisor" in script
    assert "New-ScheduledTaskTrigger -AtLogOn -User $RunAsUser" in script
    assert "New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType Interactive" in script
    assert "-AtStartup" not in script
    assert "Newsroom-$($installationId.Substring(0, 12))-Start" in script
    assert "tasks = @($taskName)" in script
    assert "-NoBrowser" in script
    assert "RunAsUser must match the current Windows user" in script
    assert "Write-Launcher" not in script
    assert "Register-ProcessTask" not in script


def test_start_launcher_reuses_verified_runtime_before_spawning_supervisor():
    script = SCRIPT.read_text(encoding="utf-8")

    identity_probe = "`$identity = Invoke-RestMethod -Uri `$identityUri -Method Get -TimeoutSec 1"
    supervisor_spawn = "`$process = [System.Diagnostics.Process]::Start(`$startInfo)"

    assert script.count(identity_probe) >= 2
    assert script.index(identity_probe) < script.index(supervisor_spawn)
    assert "if (-not `$ready) {" in script


def test_windows_install_requires_explicit_reviewed_legacy_task_migration_before_writes():
    script = SCRIPT.read_text(encoding="utf-8")

    for task_name in ("Newsroom-API", "Newsroom-Worker", "Newsroom-Scheduler"):
        assert task_name in script
    assert "MigrateLegacyTasks" in script
    assert "Get-LegacyTaskRecords" in script
    assert "Remove-ReviewedLegacyTasks" in script
    assert "does not match the known Newsroom launcher contract" in script
    assert "no install files or tasks were changed" in script
    assert "Legacy Newsroom tasks are present" in script
    assert "Unregister-ScheduledTask -TaskName ([string]$record.Name)" in script
    assert "IndexOf($expectedLauncher, [StringComparison]::OrdinalIgnoreCase)" in script
    assert script.index("$legacyTasks = @(Get-LegacyTaskRecords)") < script.index(
        "New-Item -ItemType Directory -Path $RuntimeRoot"
    )


def test_ast05_windows_smoke_is_disposable_and_never_targets_trial_port():
    smoke = SMOKE.read_text(encoding="utf-8")

    assert "RUNNER_TEMP" in smoke
    assert "Get-FreeLoopbackPort" in smoke
    assert "MigrateLegacyTasks" in smoke
    assert "Astra05-Unrelated-" in smoke
    assert "trial_contacted = $false" in smoke
    assert "paid_calls = 0" in smoke
    assert "8127" not in smoke
    assert "physical_reboot_exercised = $false" in smoke
    assert "physical_lock_wake_exercised = $false" in smoke
