[CmdletBinding()]
param(
    [string]$SourceRoot = (Join-Path $PSScriptRoot '..'),
    [string]$OutputDirectory = (Join-Path $SourceRoot '.artifacts\astra05-windows'),
    [string]$PythonExe = 'python'
)

$ErrorActionPreference = 'Stop'
$SourceRoot = [IO.Path]::GetFullPath($SourceRoot)
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$LegacyNames = @('Newsroom-API', 'Newsroom-Worker', 'Newsroom-Scheduler')
$runId = [Guid]::NewGuid().ToString('N')
$tempRoot = Join-Path $env:RUNNER_TEMP "newsroom-astra05-$runId"
$InstallRoot = Join-Path $tempRoot 'app\prod'
$RuntimeRoot = Join-Path $tempRoot 'runtime\prod'
$ShortcutRoot = Join-Path $tempRoot 'shortcuts'
$legacyRoot = Join-Path $tempRoot 'legacy'
$unrelatedTask = "Astra05-Unrelated-$($runId.Substring(0, 12))"
$manifest = $null
$taskName = $null
$listener = $null

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw $Message
    }
}

function Get-FreeLoopbackPort {
    $probe = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
    $probe.Start()
    try {
        return ([System.Net.IPEndPoint]$probe.LocalEndpoint).Port
    }
    finally {
        $probe.Stop()
    }
}

function Register-ProbeTask([string]$Name, [string]$Launcher) {
    $arguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Launcher`""
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory (Split-Path -Parent $Launcher)
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
    $principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
}

function Invoke-StartLauncher([string]$Launcher) {
    $output = & powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $Launcher -NoBrowser 2>&1
    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = (($output | ForEach-Object { [string]$_ }) -join "`n")
    }
}

function Get-RoleSnapshot([string]$Role) {
    $runtimeDir = Join-Path $RuntimeRoot 'runtime'
    $ownerPath = Join-Path $runtimeDir "$Role-managed-owner.json"
    $heartbeatPath = Join-Path $runtimeDir "$Role-heartbeat.json"
    if (-not (Test-Path -LiteralPath $ownerPath -PathType Leaf)) {
        return [pscustomobject]@{ status = 'missing'; pid = $null }
    }

    try {
        $owner = Get-Content -LiteralPath $ownerPath -Raw | ConvertFrom-Json
        $process = Get-Process -Id ([int]$owner.pid) -ErrorAction Stop
        if ($null -eq $process) {
            return [pscustomobject]@{ status = 'missing'; pid = $null }
        }
        if (-not (Test-Path -LiteralPath $heartbeatPath -PathType Leaf)) {
            return [pscustomobject]@{ status = 'stale'; pid = [int]$owner.pid }
        }
        $heartbeat = Get-Content -LiteralPath $heartbeatPath -Raw | ConvertFrom-Json
        if ([int]$heartbeat.pid -ne [int]$owner.pid -or [string]$heartbeat.process_creation_token -ne [string]$owner.process_creation_token) {
            return [pscustomobject]@{ status = 'stale'; pid = [int]$owner.pid }
        }
        $updated = [DateTimeOffset]::Parse([string]$heartbeat.updated_at).UtcDateTime
        if (([DateTime]::UtcNow - $updated).TotalSeconds -gt 5) {
            return [pscustomobject]@{ status = 'stale'; pid = [int]$owner.pid }
        }
        return [pscustomobject]@{ status = 'healthy'; pid = [int]$owner.pid }
    }
    catch {
        return [pscustomobject]@{ status = 'missing'; pid = $null }
    }
}

function Get-ManagedSnapshot {
    $snapshot = [ordered]@{}
    foreach ($role in @('supervisor', 'api', 'worker', 'scheduler')) {
        $snapshot[$role] = Get-RoleSnapshot $role
    }
    if ($snapshot.api.status -eq 'healthy') {
        try {
            $identity = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/runtime/identity" -Method Get -TimeoutSec 1
            if ($identity.service -ne 'newsroom' -or $identity.managed -ne $true -or [string]$identity.installation_id -ne [string]$manifest.installation_id) {
                $snapshot.api = [pscustomobject]@{ status = 'stale'; pid = $snapshot.api.pid }
            }
        }
        catch {
            $snapshot.api = [pscustomobject]@{ status = 'stale'; pid = $snapshot.api.pid }
        }
    }
    return [pscustomobject]$snapshot
}

function Wait-Healthy([int]$TimeoutSeconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $snapshot = Get-ManagedSnapshot
        $statuses = @($snapshot.supervisor.status, $snapshot.api.status, $snapshot.worker.status, $snapshot.scheduler.status)
        if (@($statuses | Where-Object { $_ -ne 'healthy' }).Count -eq 0) {
            return $snapshot
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Managed runtime did not reach four healthy roles within the smoke-test deadline.'
}

function Request-SupervisorStop {
    $runtimeDir = Join-Path $RuntimeRoot 'runtime'
    $ownerPath = Join-Path $runtimeDir 'supervisor-managed-owner.json'
    if (-not (Test-Path -LiteralPath $ownerPath -PathType Leaf)) {
        return
    }
    $owner = Get-Content -LiteralPath $ownerPath -Raw | ConvertFrom-Json
    $controlPath = Join-Path $runtimeDir 'supervisor-control.json'
    $temporary = Join-Path $runtimeDir ('.supervisor-control.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    $payload = [ordered]@{
        format_version = 1
        action = 'stop'
        pid = [int]$owner.pid
        process_creation_token = [string]$owner.process_creation_token
        requested_at = [DateTime]::UtcNow.ToString('o')
    }
    try {
        $payload | ConvertTo-Json -Compress | Set-Content -LiteralPath $temporary -Encoding utf8
        Move-Item -LiteralPath $temporary -Destination $controlPath -Force
    }
    finally {
        Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
    }
}

function Wait-Stopped([int]$TimeoutSeconds = 20) {
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $snapshot = Get-ManagedSnapshot
        $statuses = @($snapshot.supervisor.status, $snapshot.api.status, $snapshot.worker.status, $snapshot.scheduler.status)
        if (@($statuses | Where-Object { $_ -ne 'missing' }).Count -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'Managed runtime did not stop within the smoke-test deadline.'
}

function Remove-TaskIfPresent([string]$Name) {
    $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($null -ne $task) {
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false
    }
}

New-Item -ItemType Directory -Path $tempRoot, $legacyRoot, $OutputDirectory -Force | Out-Null
$preexisting = @($LegacyNames | Where-Object { $null -ne (Get-ScheduledTask -TaskName $_ -ErrorAction SilentlyContinue) })
if ($preexisting.Count -gt 0) {
    throw "Hosted Windows runner already contains legacy Newsroom task name(s): $($preexisting -join ', '). Refusing to alter them."
}

$Port = Get-FreeLoopbackPort
$evidence = [ordered]@{
    platform = [Environment]::OSVersion.VersionString
    current_user = $CurrentUser
    port = $Port
    trial_contacted = $false
    paid_calls = 0
}

try {
    foreach ($pair in @(
        @('Newsroom-API', 'run-api.ps1'),
        @('Newsroom-Worker', 'run-worker.ps1'),
        @('Newsroom-Scheduler', 'run-scheduler.ps1')
    )) {
        $launcher = Join-Path $legacyRoot $pair[1]
        Set-Content -LiteralPath $launcher -Value 'exit 0' -Encoding utf8
        Register-ProbeTask $pair[0] $launcher
    }
    $unrelatedLauncher = Join-Path $legacyRoot 'unrelated.ps1'
    Set-Content -LiteralPath $unrelatedLauncher -Value 'exit 0' -Encoding utf8
    Register-ProbeTask $unrelatedTask $unrelatedLauncher

    $deploy = Join-Path $SourceRoot 'scripts\phase16_windows_deploy.ps1'
    & powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $deploy `
        -Mode Install `
        -SourceRoot $SourceRoot `
        -InstallRoot $InstallRoot `
        -RuntimeRoot $RuntimeRoot `
        -ShortcutRoot $ShortcutRoot `
        -PythonExe $PythonExe `
        -Port $Port `
        -RunAsUser $CurrentUser `
        -RegisterTasks `
        -MigrateLegacyTasks `
        -SkipChecks
    if ($LASTEXITCODE -ne 0) {
        throw "AST-05 disposable install failed with exit code $LASTEXITCODE"
    }

    $manifestPath = Join-Path $InstallRoot 'release-manifest.json'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Installed release-manifest.json is missing.'
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Assert-True ($manifest.format_version -eq 2) 'Installed manifest format was not advanced to the single-launch authority contract.'
    Assert-True (@($manifest.tasks).Count -eq 1) 'Installed manifest must name exactly one scheduled task authority.'
    $taskName = [string]@($manifest.tasks)[0]
    $expectedTaskName = "Newsroom-$(([string]$manifest.installation_id).Substring(0, 12))-Start"
    Assert-True ($taskName -eq $expectedTaskName) 'Scheduled task name does not match this installation identity prefix.'
    Assert-True ([bool]$manifest.task_registered) 'Installed manifest did not record the namespaced task as registered.'
    Assert-True ($manifest.task_trigger -eq 'AtLogOn') 'Installed manifest did not record AtLogOn startup.'
    Assert-True ($manifest.task_logon_type -eq 'Interactive') 'Installed manifest did not record interactive same-user startup.'
    Assert-True ($manifest.run_as_user -eq $CurrentUser) 'Installed manifest run-as user differs from the current Windows user.'
    Assert-True (@($manifest.legacy_tasks_detected).Count -eq 3) 'Disposable legacy task set was not detected completely.'
    Assert-True ([bool]$manifest.legacy_tasks_migrated) 'Disposable legacy task set was not recorded as migrated.'
    foreach ($legacyName in $LegacyNames) {
        Assert-True ($null -eq (Get-ScheduledTask -TaskName $legacyName -ErrorAction SilentlyContinue)) "Legacy task $legacyName still exists after explicit migration."
    }
    Assert-True ($null -ne (Get-ScheduledTask -TaskName $unrelatedTask -ErrorAction SilentlyContinue)) 'Unrelated scheduled task was altered during legacy migration.'

    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    Assert-True (@($task.Actions).Count -eq 1) 'Namespaced task has more than one action.'
    Assert-True ([string]$task.Actions[0].Arguments -like '*start-newsroom.ps1*') 'Namespaced task does not invoke the Start Newsroom launcher.'
    Assert-True ([string]$task.Actions[0].Arguments -like '*-NoBrowser*') 'Sign-in task must reuse the launcher without opening a browser.'
    Assert-True ([string]$task.Principal.UserId -eq $CurrentUser) 'Namespaced task principal is not the current Windows user.'
    Assert-True ([string]$task.Principal.LogonType -match 'Interactive') 'Namespaced task does not use an interactive logon token.'
    Assert-True (@($task.Triggers | Where-Object { $_.CimClass.CimClassName -match 'LogonTrigger' }).Count -eq 1) 'Namespaced task does not have exactly one logon trigger.'

    $shortcutPath = Join-Path $ShortcutRoot 'Start Newsroom.lnk'
    Assert-True (Test-Path -LiteralPath $shortcutPath -PathType Leaf) 'Start Newsroom shortcut is missing.'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    Assert-True ($shortcut.Arguments -like '*start-newsroom.ps1*') 'Shortcut does not invoke the Start Newsroom launcher.'
    Assert-True ($shortcut.Arguments -like '*-WindowStyle Hidden*') 'Shortcut does not hide the launcher console.'
    Assert-True ($shortcut.Arguments -notlike '*-NoBrowser*') 'Interactive shortcut must open the product after startup.'

    $launcherPath = Join-Path $InstallRoot 'start-newsroom.ps1'
    $firstLaunch = Invoke-StartLauncher $launcherPath
    Assert-True ($firstLaunch.ExitCode -eq 0) "First installed launcher failed: $($firstLaunch.Output)"
    $initial = Wait-Healthy

    $launcherArgs = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcherPath`" -NoBrowser"
    $duplicateA = Start-Process -FilePath 'powershell.exe' -ArgumentList $launcherArgs -PassThru -WindowStyle Hidden
    $duplicateB = Start-Process -FilePath 'powershell.exe' -ArgumentList $launcherArgs -PassThru -WindowStyle Hidden
    Assert-True ($duplicateA.WaitForExit(30000)) 'First duplicate launcher did not exit within bounds.'
    Assert-True ($duplicateB.WaitForExit(30000)) 'Second duplicate launcher did not exit within bounds.'
    Assert-True ($duplicateA.ExitCode -eq 0 -and $duplicateB.ExitCode -eq 0) 'Concurrent duplicate launch returned a failure.'
    $afterDuplicate = Wait-Healthy
    foreach ($role in @('supervisor', 'api', 'worker', 'scheduler')) {
        Assert-True ($initial.$role.pid -eq $afterDuplicate.$role.pid) "Duplicate launch changed the verified $role owner PID."
    }

    Request-SupervisorStop
    Wait-Stopped
    Start-ScheduledTask -TaskName $taskName
    $afterTask = Wait-Healthy

    Request-SupervisorStop
    Wait-Stopped
    $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
    $listener.Start()
    $foreignAttempt = Invoke-StartLauncher $launcherPath
    Assert-True ($foreignAttempt.ExitCode -ne 0) 'Launcher unexpectedly succeeded while a foreign listener owned the configured port.'
    Assert-True ($foreignAttempt.Output -like '*No process was killed and no alternate port was selected*') 'Foreign-port launcher failure did not preserve the fixed-port/no-kill contract.'
    Assert-True ($listener.Server.IsBound) 'Foreign listener was stopped or displaced by the launcher.'
    $listener.Stop()
    $listener = $null

    $evidence.source_commit = [string]$manifest.source_commit
    $evidence.artifact_sha256 = [string]$manifest.artifact_sha256
    $evidence.installed_artifact_sha256 = [string]$manifest.installed_artifact_sha256
    $evidence.installation_id = [string]$manifest.installation_id
    $evidence.task = [ordered]@{
        count = 1
        name = $taskName
        trigger = 'AtLogOn'
        logon_type = 'Interactive'
        same_user = $true
        action_uses_single_launcher = $true
        manual_trigger_reached_healthy = $true
    }
    $evidence.shortcut = [ordered]@{
        name = 'Start Newsroom.lnk'
        hidden_console = $true
        opens_browser = $true
    }
    $evidence.runtime = [ordered]@{
        first_launch_four_roles_healthy = $true
        launcher_returned_while_runtime_remained_healthy = $true
        duplicate_launch_reused_exact_role_pids = $true
        background_independent_of_launcher_process = $true
    }
    $evidence.foreign_port = [ordered]@{
        failed_closed = $true
        configured_listener_survived = $true
        alternate_port_selected = $false
        process_killed = $false
    }
    $evidence.legacy_migration = [ordered]@{
        detected = 3
        migrated = 3
        unrelated_task_preserved = $true
    }
    $evidence.reboot_sign_in = [ordered]@{
        physical_reboot_exercised = $false
        sign_in_action_manually_triggered = $true
        note = 'Hosted GitHub runner cannot survive an OS reboot; the exact registered AtLogOn action was invoked manually and reached four healthy managed roles.'
    }
    $evidence.lock_wake = [ordered]@{
        physical_lock_wake_exercised = $false
        note = 'Hosted GitHub runner does not provide a supported interactive lock/sleep/wake lifecycle. This remains a physical Windows qualification item.'
    }
    $evidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'qualification.json') -Encoding utf8
    Write-Host "AST-05 Windows smoke PASS. Evidence: $(Join-Path $OutputDirectory 'qualification.json')"
}
finally {
    if ($null -ne $listener) {
        try { $listener.Stop() } catch { }
    }
    try {
        Request-SupervisorStop
        Wait-Stopped 10
    }
    catch {
        $escapedRoot = [regex]::Escape($RuntimeRoot)
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match $escapedRoot -and $_.ProcessId -ne $PID } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    if ($null -ne $taskName) {
        Remove-TaskIfPresent $taskName
    }
    foreach ($legacyName in $LegacyNames) {
        Remove-TaskIfPresent $legacyName
    }
    Remove-TaskIfPresent $unrelatedTask
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
