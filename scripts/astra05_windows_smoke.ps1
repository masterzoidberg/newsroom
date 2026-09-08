[CmdletBinding()]
param(
    [string]$SourceRoot = '',
    [string]$OutputDirectory = '',
    [string]$PythonExe = 'python',
    [ValidateSet('Hosted', 'PhysicalPrepare', 'PhysicalVerifyWake', 'PhysicalVerifySignIn', 'PhysicalCleanup')]
    [string]$LifecycleMode = 'Hosted',
    [string]$PhysicalRoot = '',
    [switch]$ConfirmBrowserOpened,
    [switch]$ConfirmLockWake,
    [switch]$ConfirmSignIn,
    [ValidateSet('Reboot', 'SignOut')]
    [string]$SignInMethod = 'Reboot'
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Join-Path $PSScriptRoot '..'
}
$SourceRoot = [IO.Path]::GetFullPath($SourceRoot)
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $SourceRoot '.artifacts\astra05-windows'
}
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$CurrentUser = $currentIdentity.Name
$CurrentUserSid = $currentIdentity.User.Value
$LegacyNames = @('Newsroom-API', 'Newsroom-Worker', 'Newsroom-Scheduler')
$runId = [Guid]::NewGuid().ToString('N')

if ($LifecycleMode -eq 'Hosted') {
    if ([string]::IsNullOrWhiteSpace($env:RUNNER_TEMP)) {
        throw 'Hosted AST-05 smoke requires RUNNER_TEMP. Use an explicit Physical* lifecycle mode for owner-machine qualification.'
    }
    $tempRoot = Join-Path $env:RUNNER_TEMP "newsroom-astra05-$runId"
}
else {
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw 'Physical AST-05 qualification requires LOCALAPPDATA.'
    }
    $physicalBase = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Newsroom\astra05-physical'))
    if ([string]::IsNullOrWhiteSpace($PhysicalRoot)) {
        $PhysicalRoot = $physicalBase
    }
    $tempRoot = [IO.Path]::GetFullPath($PhysicalRoot)
    $allowed = $tempRoot -eq $physicalBase -or $tempRoot.StartsWith(
        $physicalBase + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    )
    if (-not $allowed) {
        throw "PhysicalRoot must remain under the dedicated Astra qualification root: $physicalBase"
    }
}

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

function Read-JsonShared([string]$Path) {
    $share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::Open,
        [System.IO.FileAccess]::Read,
        $share
    )
    try {
        $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true)
        try {
            $text = $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
    return $text | ConvertFrom-Json
}

function Resolve-AccountSid([string]$Account) {
    if ([string]::IsNullOrWhiteSpace($Account)) {
        return $null
    }
    try {
        if ($Account -match '^S-1-') {
            return ([System.Security.Principal.SecurityIdentifier]$Account).Value
        }
        $ntAccount = New-Object System.Security.Principal.NTAccount($Account)
        return ($ntAccount.Translate([System.Security.Principal.SecurityIdentifier])).Value
    }
    catch {
        return $null
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
    $stdoutPath = Join-Path $tempRoot ('.launcher-' + [Guid]::NewGuid().ToString('N') + '.out.log')
    $stderrPath = Join-Path $tempRoot ('.launcher-' + [Guid]::NewGuid().ToString('N') + '.err.log')
    $arguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Launcher`" -NoBrowser"
    try {
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
        # Windows PowerShell can lose the real ExitCode for redirected Start-Process
        # children unless the native process handle is materialized before waiting.
        $null = $process.Handle
        if (-not $process.WaitForExit(40000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            throw 'Start Newsroom launcher did not exit within the smoke-test deadline.'
        }
        $process.WaitForExit()
        $process.Refresh()
        $exitCode = [int]$process.ExitCode
        $stdout = if (Test-Path -LiteralPath $stdoutPath) { Get-Content -LiteralPath $stdoutPath -Raw } else { '' }
        $stderr = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { '' }
        $captured = @([string]$stdout, [string]$stderr) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        return [pscustomobject]@{
            ExitCode = $exitCode
            Output = ($captured -join "`n")
        }
    }
    finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
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
        $owner = Read-JsonShared $ownerPath
        $process = Get-Process -Id ([int]$owner.pid) -ErrorAction Stop
        if ($null -eq $process) {
            return [pscustomobject]@{ status = 'missing'; pid = $null }
        }
        if (-not (Test-Path -LiteralPath $heartbeatPath -PathType Leaf)) {
            return [pscustomobject]@{ status = 'stale'; pid = [int]$owner.pid }
        }
        $heartbeat = Read-JsonShared $heartbeatPath
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

function Get-RuntimeLogSummary {
    $logsRoot = Join-Path $RuntimeRoot 'logs'
    $summary = [ordered]@{}
    foreach ($name in @('supervisor.log', 'api.log', 'worker.log', 'scheduler.log')) {
        $path = Join-Path $logsRoot $name
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $summary[$name] = ((Get-Content -LiteralPath $path -Tail 20) -join "`n")
        }
    }
    return [pscustomobject]$summary
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
    $snapshotJson = $snapshot | ConvertTo-Json -Depth 4 -Compress
    throw "Managed runtime did not reach four healthy roles within the smoke-test deadline. Snapshot=$snapshotJson"
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
        $json = $payload | ConvertTo-Json -Compress
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($temporary, $json, $utf8NoBom)
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

function Build-PhysicalFrontendArtifact {
    $git = Get-Command 'git.exe' -ErrorAction SilentlyContinue
    if ($null -eq $git -or [string]::IsNullOrWhiteSpace($git.Source)) {
        throw 'Physical AST-05 qualification requires Git so the isolated source checkout can be verified clean before building.'
    }
    $dirty = @(& $git.Source -C $SourceRoot status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0) {
        throw 'Physical AST-05 qualification could not verify the isolated source checkout with Git.'
    }
    if ($dirty.Count -ne 0) {
        throw "Physical AST-05 qualification requires a clean isolated source checkout. Dirty entries: $($dirty -join '; ')"
    }

    $npm = Get-Command 'npm.cmd' -ErrorAction SilentlyContinue
    if ($null -eq $npm -or [string]::IsNullOrWhiteSpace($npm.Source)) {
        throw 'Physical AST-05 qualification requires Node/npm to build the current ignored frontend/dist artifact in the isolated checkout.'
    }
    $frontendRoot = Join-Path $SourceRoot 'frontend'
    Push-Location $frontendRoot
    try {
        & $npm.Source ci
        if ($LASTEXITCODE -ne 0) {
            throw "Physical AST-05 npm ci failed with exit code $LASTEXITCODE"
        }
        & $npm.Source run build
        if ($LASTEXITCODE -ne 0) {
            throw "Physical AST-05 npm run build failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
    Assert-True (Test-Path -LiteralPath (Join-Path $frontendRoot 'dist\index.html') -PathType Leaf) 'Physical AST-05 frontend build did not produce dist/index.html.'
}

function Read-PhysicalState {
    $statePath = Join-Path $tempRoot 'physical-state.json'
    if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        throw "Physical qualification state is missing: $statePath. Refusing to infer cleanup or verification targets."
    }
    return Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
}

function Write-PhysicalState([object]$State) {
    $statePath = Join-Path $tempRoot 'physical-state.json'
    $State | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $statePath -Encoding utf8
}

function Set-PhysicalContext([object]$State) {
    Assert-True ([string]$State.current_user_sid -eq $CurrentUserSid) 'Physical qualification state belongs to a different Windows user SID.'
    Assert-True ([string]$State.physical_root -eq $tempRoot) 'Physical qualification state root does not match the requested PhysicalRoot.'

    $script:InstallRoot = [IO.Path]::GetFullPath([string]$State.install_root)
    $script:RuntimeRoot = [IO.Path]::GetFullPath([string]$State.runtime_root)
    $script:ShortcutRoot = [IO.Path]::GetFullPath([string]$State.shortcut_root)
    $script:Port = [int]$State.port
    $script:taskName = [string]$State.task_name

    foreach ($path in @($InstallRoot, $RuntimeRoot, $ShortcutRoot)) {
        Assert-True (
            $path.StartsWith($tempRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
        ) "Recorded physical qualification path escaped its dedicated root: $path"
    }
    Assert-True ($taskName -match '^Newsroom-[0-9a-fA-F-]{12}-Start$') 'Recorded physical qualification task name is not a Newsroom installation-namespaced Start task.'

    $manifestPath = Join-Path $InstallRoot 'release-manifest.json'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Physical qualification release manifest is missing.'
    $script:manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Assert-True ([string]$manifest.installation_id -eq [string]$State.installation_id) 'Physical qualification installation identity changed.'
    Assert-True (@($manifest.tasks).Count -eq 1 -and [string]@($manifest.tasks)[0] -eq $taskName) 'Physical qualification manifest task does not match recorded state.'
}

function Invoke-PhysicalPrepare {
    if (Test-Path -LiteralPath $tempRoot) {
        $existing = @(Get-ChildItem -LiteralPath $tempRoot -Force -ErrorAction SilentlyContinue)
        if ($existing.Count -gt 0) {
            throw "Physical qualification root must be absent or empty before prepare: $tempRoot. Use PhysicalCleanup for a recorded prior run."
        }
    }

    $preexisting = @($LegacyNames | Where-Object { $null -ne (Get-ScheduledTask -TaskName $_ -ErrorAction SilentlyContinue) })
    if ($preexisting.Count -gt 0) {
        throw "Physical qualification refuses to alter legacy Newsroom task name(s): $($preexisting -join ', '). Review the real installation separately before qualification."
    }

    Build-PhysicalFrontendArtifact
    New-Item -ItemType Directory -Path $tempRoot, $OutputDirectory -Force | Out-Null
    $script:Port = Get-FreeLoopbackPort
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
        -SkipChecks
    if ($LASTEXITCODE -ne 0) {
        throw "AST-05 physical qualification install failed with exit code $LASTEXITCODE"
    }

    $manifestPath = Join-Path $InstallRoot 'release-manifest.json'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Physical qualification release manifest is missing after install.'
    $script:manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    Assert-True (@($manifest.tasks).Count -eq 1) 'Physical qualification install did not create exactly one Start task authority.'
    $script:taskName = [string]@($manifest.tasks)[0]
    Assert-True ($taskName -match '^Newsroom-[0-9a-fA-F-]{12}-Start$') 'Physical qualification task is not installation-namespaced.'
    Assert-True ($null -ne (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue)) 'Physical qualification Start task is not registered.'

    # Persist the exact cleanup authority before launching anything persistent.
    # If startup or browser opening fails, PhysicalCleanup can still target only
    # this recorded isolated installation and its namespaced task.
    $state = [ordered]@{
        format_version = 1
        physical_root = $tempRoot
        source_commit = [string]$manifest.source_commit
        artifact_sha256 = [string]$manifest.artifact_sha256
        installation_id = [string]$manifest.installation_id
        install_root = $InstallRoot
        runtime_root = $RuntimeRoot
        shortcut_root = $ShortcutRoot
        task_name = $taskName
        port = $Port
        current_user = $CurrentUser
        current_user_sid = $CurrentUserSid
        prepared_at = [DateTime]::UtcNow.ToString('o')
        prepare_status = 'installed'
        initial_pids = $null
        browser_opened_confirmed = $false
        lock_wake_exercised = $false
        wake_verified_at = $null
        wake_pids = $null
        sign_in_exercised = $false
        sign_in_method = $null
        sign_in_verified_at = $null
        sign_in_auto_reached_healthy = $false
        sign_in_launcher_reused_exact_pids = $false
        physical_reboot_exercised = $false
        sign_out_sign_in_exercised = $false
        trial_contacted = $false
        paid_calls = 0
    }
    Write-PhysicalState $state

    $launcherPath = Join-Path $InstallRoot 'start-newsroom.ps1'
    $launch = Invoke-StartLauncher $launcherPath
    Assert-True ($launch.ExitCode -eq 0) "Physical qualification first launch failed: $($launch.Output)"
    $initial = Wait-Healthy 60
    $state.prepare_status = 'healthy'
    $state.initial_pids = [ordered]@{
        supervisor = $initial.supervisor.pid
        api = $initial.api.pid
        worker = $initial.worker.pid
        scheduler = $initial.scheduler.pid
    }
    Write-PhysicalState $state

    $shortcutPath = Join-Path $ShortcutRoot 'Start Newsroom.lnk'
    Assert-True (Test-Path -LiteralPath $shortcutPath -PathType Leaf) 'Physical qualification Start Newsroom shortcut is missing.'
    Start-Process -FilePath $shortcutPath | Out-Null
    $state.prepare_status = 'awaiting_wake'
    Write-PhysicalState $state

    Write-Host "AST-05 physical qualification prepared at: $tempRoot"
    Write-Host 'The isolated Start Newsroom shortcut was opened. Confirm the product opened, then close the browser.'
    Write-Host 'Lock or sleep Windows, return to the same user session, then run:'
    Write-Host "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -SourceRoot `"$SourceRoot`" -OutputDirectory `"$OutputDirectory`" -LifecycleMode PhysicalVerifyWake -PhysicalRoot `"$tempRoot`" -ConfirmBrowserOpened -ConfirmLockWake"
}

function Invoke-PhysicalVerifyWake {
    Assert-True ([bool]$ConfirmBrowserOpened) 'PhysicalVerifyWake requires -ConfirmBrowserOpened after visually confirming the isolated Start Newsroom shortcut opened the product.'
    Assert-True ([bool]$ConfirmLockWake) 'PhysicalVerifyWake requires -ConfirmLockWake after an actual lock/sleep and return to the same Windows session.'

    $state = Read-PhysicalState
    Set-PhysicalContext $state
    $beforeLauncher = Wait-Healthy 90
    $launcherPath = Join-Path $InstallRoot 'start-newsroom.ps1'
    $launch = Invoke-StartLauncher $launcherPath
    Assert-True ($launch.ExitCode -eq 0) "Physical wake verification launcher failed: $($launch.Output)"
    $afterLauncher = Wait-Healthy 30
    foreach ($role in @('supervisor', 'api', 'worker', 'scheduler')) {
        Assert-True ($beforeLauncher.$role.pid -eq $afterLauncher.$role.pid) "Post-wake Start Newsroom changed the verified $role PID instead of reusing the healthy runtime."
    }

    $state.browser_opened_confirmed = $true
    $state.lock_wake_exercised = $true
    $state.wake_verified_at = [DateTime]::UtcNow.ToString('o')
    $state.wake_pids = [ordered]@{
        supervisor = $afterLauncher.supervisor.pid
        api = $afterLauncher.api.pid
        worker = $afterLauncher.worker.pid
        scheduler = $afterLauncher.scheduler.pid
    }
    Write-PhysicalState $state

    Write-Host 'AST-05 physical lock/wake checkpoint PASS.'
    Write-Host 'Now reboot Windows or sign out and back in. Do not manually start Newsroom after sign-in.'
    Write-Host 'After the same user session is ready, run one of:'
    Write-Host "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -SourceRoot `"$SourceRoot`" -OutputDirectory `"$OutputDirectory`" -LifecycleMode PhysicalVerifySignIn -PhysicalRoot `"$tempRoot`" -ConfirmSignIn -SignInMethod Reboot"
    Write-Host "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -SourceRoot `"$SourceRoot`" -OutputDirectory `"$OutputDirectory`" -LifecycleMode PhysicalVerifySignIn -PhysicalRoot `"$tempRoot`" -ConfirmSignIn -SignInMethod SignOut"
}

function Invoke-PhysicalVerifySignIn {
    Assert-True ([bool]$ConfirmSignIn) 'PhysicalVerifySignIn requires -ConfirmSignIn after an actual reboot/sign-in or sign-out/sign-in cycle.'

    $state = Read-PhysicalState
    Set-PhysicalContext $state
    Assert-True ([bool]$state.lock_wake_exercised) 'Complete PhysicalVerifyWake before the physical sign-in checkpoint.'

    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    Assert-True ([string]$task.Principal.LogonType -match 'Interactive') 'Physical qualification Start task no longer uses an interactive logon token.'
    Assert-True (@($task.Triggers | Where-Object { $_.CimClass.CimClassName -match 'LogonTrigger' }).Count -eq 1) 'Physical qualification Start task no longer has exactly one logon trigger.'
    Assert-True ([string]$task.Actions[0].Arguments -like '*start-newsroom.ps1*') 'Physical qualification Start task no longer uses the installed launcher.'

    # Do not invoke the launcher first: reaching healthy here is the proof that
    # the actual Windows sign-in action restored the managed runtime.
    $afterSignIn = Wait-Healthy 120
    $launcherPath = Join-Path $InstallRoot 'start-newsroom.ps1'
    $launch = Invoke-StartLauncher $launcherPath
    Assert-True ($launch.ExitCode -eq 0) "Physical sign-in verification launcher failed: $($launch.Output)"
    $afterLauncher = Wait-Healthy 30
    foreach ($role in @('supervisor', 'api', 'worker', 'scheduler')) {
        Assert-True ($afterSignIn.$role.pid -eq $afterLauncher.$role.pid) "Post-sign-in Start Newsroom changed the verified $role PID instead of reusing the AtLogOn-restored runtime."
    }

    $state.sign_in_exercised = $true
    $state.sign_in_method = $SignInMethod
    $state.sign_in_verified_at = [DateTime]::UtcNow.ToString('o')
    $state.sign_in_auto_reached_healthy = $true
    $state.sign_in_launcher_reused_exact_pids = $true
    $state.physical_reboot_exercised = ($SignInMethod -eq 'Reboot')
    $state.sign_out_sign_in_exercised = ($SignInMethod -eq 'SignOut')
    Write-PhysicalState $state

    New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
    $evidence = [ordered]@{
        platform = [Environment]::OSVersion.VersionString
        current_user = $CurrentUser
        current_user_sid = $CurrentUserSid
        source_commit = [string]$state.source_commit
        artifact_sha256 = [string]$state.artifact_sha256
        installation_id = [string]$state.installation_id
        port = [int]$state.port
        task = [ordered]@{
            name = [string]$state.task_name
            trigger = 'AtLogOn'
            logon_type = 'Interactive'
            actual_sign_in_exercised = $true
            sign_in_method = $SignInMethod
            auto_reached_four_roles_healthy = $true
        }
        runtime = [ordered]@{
            browser_opened_confirmed = [bool]$state.browser_opened_confirmed
            browser_closed_runtime_remained_healthy = $true
            physical_lock_wake_exercised = [bool]$state.lock_wake_exercised
            physical_sign_in_exercised = $true
            physical_reboot_exercised = [bool]$state.physical_reboot_exercised
            sign_out_sign_in_exercised = [bool]$state.sign_out_sign_in_exercised
            post_sign_in_launcher_reused_exact_role_pids = $true
        }
        trial_contacted = $false
        paid_calls = 0
        verified_at = [DateTime]::UtcNow.ToString('o')
    }
    $physicalEvidencePath = Join-Path $OutputDirectory 'physical-qualification.json'
    $evidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $physicalEvidencePath -Encoding utf8

    Write-Host "AST-05 physical lifecycle qualification PASS. Evidence: $physicalEvidencePath"
    Write-Host 'Cleanup is explicit so evidence remains available. Run:'
    Write-Host "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -SourceRoot `"$SourceRoot`" -OutputDirectory `"$OutputDirectory`" -LifecycleMode PhysicalCleanup -PhysicalRoot `"$tempRoot`""
}

function Invoke-PhysicalCleanup {
    $state = Read-PhysicalState
    Set-PhysicalContext $state

    # Remove only the recorded installation-namespaced task first so cleanup
    # cannot accidentally respawn the isolated runtime during cooperative stop.
    Remove-TaskIfPresent $taskName
    Request-SupervisorStop
    try {
        Wait-Stopped 30
    }
    catch {
        throw "Physical qualification task was removed, but the recorded managed runtime did not stop cooperatively. The isolated root was retained for diagnosis: $tempRoot"
    }

    Remove-Item -LiteralPath $tempRoot -Recurse -Force
    Write-Host "AST-05 physical qualification cleanup complete. Preserved evidence directory: $OutputDirectory"
}

if ($LifecycleMode -ne 'Hosted') {
    switch ($LifecycleMode) {
        'PhysicalPrepare' { Invoke-PhysicalPrepare }
        'PhysicalVerifyWake' { Invoke-PhysicalVerifyWake }
        'PhysicalVerifySignIn' { Invoke-PhysicalVerifySignIn }
        'PhysicalCleanup' { Invoke-PhysicalCleanup }
    }
    exit 0
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
    current_user_sid = $CurrentUserSid
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
    $taskPrincipalSid = Resolve-AccountSid ([string]$task.Principal.UserId)
    Assert-True ($taskPrincipalSid -eq $CurrentUserSid) 'Namespaced task principal does not resolve to the current Windows user SID.'
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
    if ($firstLaunch.ExitCode -ne 0) {
        $snapshotJson = Get-ManagedSnapshot | ConvertTo-Json -Depth 4 -Compress
        $logsJson = Get-RuntimeLogSummary | ConvertTo-Json -Depth 4 -Compress
        throw "First installed launcher failed: $($firstLaunch.Output) Snapshot=$snapshotJson Logs=$logsJson"
    }
    $initial = Wait-Healthy

    $launcherArgs = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$launcherPath`" -NoBrowser"
    $duplicateA = Start-Process -FilePath 'powershell.exe' -ArgumentList $launcherArgs -PassThru -WindowStyle Hidden
    $duplicateB = Start-Process -FilePath 'powershell.exe' -ArgumentList $launcherArgs -PassThru -WindowStyle Hidden
    Assert-True ($duplicateA.WaitForExit(30000)) 'First duplicate launcher did not exit within bounds.'
    Assert-True ($duplicateB.WaitForExit(30000)) 'Second duplicate launcher did not exit within bounds.'
    $duplicateA.WaitForExit()
    $duplicateB.WaitForExit()
    $duplicateA.Refresh()
    $duplicateB.Refresh()
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
    $listener.Server.ExclusiveAddressUse = $true
    $listener.Start()
    $foreignAttempt = Invoke-StartLauncher $launcherPath
    $foreignSnapshotJson = Get-ManagedSnapshot | ConvertTo-Json -Depth 4 -Compress
    $foreignLogsJson = Get-RuntimeLogSummary | ConvertTo-Json -Depth 4 -Compress
    Write-Host "Foreign-port diagnostic: exit_code=$($foreignAttempt.ExitCode) listener_bound=$($listener.Server.IsBound) output=$($foreignAttempt.Output) snapshot=$foreignSnapshotJson logs=$foreignLogsJson"
    Assert-True ($foreignAttempt.ExitCode -ne 0) "Launcher unexpectedly succeeded while a foreign listener owned the configured port. ExitCode=$($foreignAttempt.ExitCode) Output=$($foreignAttempt.Output) Snapshot=$foreignSnapshotJson Logs=$foreignLogsJson"
    Assert-True ($foreignAttempt.Output -match '(?s)No process was killed and no alternate port\s+was selected') 'Foreign-port launcher failure did not preserve the fixed-port/no-kill contract.'
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
        same_user_sid = $true
        principal_sid = $taskPrincipalSid
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
