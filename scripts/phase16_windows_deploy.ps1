[CmdletBinding()]
param(
    [ValidateSet('Validate', 'Install')]
    [string]$Mode = 'Validate',
    [string]$SourceRoot = '',
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Newsroom\app\prod'),
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'Newsroom\prod'),
    [string]$ShortcutRoot = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Newsroom'),
    [string]$PythonExe = 'python',
    [int]$Port = 8127,
    [string]$RunAsUser = '',
    [switch]$RegisterTasks,
    [switch]$MigrateLegacyTasks,
    [switch]$ConfigureTailscale,
    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
$LegacyTaskNames = [ordered]@{
    'Newsroom-API' = 'run-api.ps1'
    'Newsroom-Worker' = 'run-worker.ps1'
    'Newsroom-Scheduler' = 'run-scheduler.ps1'
}

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Join-Path $PSScriptRoot '..'
}
if ([string]::IsNullOrWhiteSpace($RunAsUser)) {
    $RunAsUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
}

function Resolve-FullPath([string]$PathValue) {
    return [IO.Path]::GetFullPath($PathValue)
}

function Assert-OutsideSource([string]$Candidate, [string]$Source) {
    $candidatePath = Resolve-FullPath $Candidate
    $sourcePath = Resolve-FullPath $Source
    if ($candidatePath -eq $sourcePath -or $candidatePath.StartsWith($sourcePath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path must be outside the source repository: $candidatePath"
    }
}

function Invoke-Checked([string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory) {
    Write-Host ">>> $FilePath $($Arguments -join ' ')"
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$FilePath failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Quote-PowerShellLiteral([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-ReleaseIdentity([string]$Root) {
    $previous = $env:NEWSROOM_RELEASE_SOURCE
    $env:NEWSROOM_RELEASE_SOURCE = $Root
    Push-Location $Root
    try {
        $json = & $PythonExe -c "import json, os; from newsroom.release import build_release_identity; print(json.dumps(build_release_identity(os.environ['NEWSROOM_RELEASE_SOURCE'])))"
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not calculate release identity.'
        }
        return ($json -join "`n") | ConvertFrom-Json
    }
    finally {
        Pop-Location
        if ($null -eq $previous) {
            Remove-Item Env:NEWSROOM_RELEASE_SOURCE -ErrorAction SilentlyContinue
        }
        else {
            $env:NEWSROOM_RELEASE_SOURCE = $previous
        }
    }
}

function Get-InstallationId([string]$Runtime) {
    $previous = $env:NEWSROOM_RUNTIME_ROOT
    $env:NEWSROOM_RUNTIME_ROOT = $Runtime
    try {
        $value = & $PythonExe -c "import os; from newsroom.config import RuntimeConfig; from newsroom.runtime_identity import ensure_installation_identity; config=RuntimeConfig.for_environment('prod', root=os.environ['NEWSROOM_RUNTIME_ROOT']); print(ensure_installation_identity(config).installation_id)"
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not establish the runtime installation identity.'
        }
        $installationId = ($value -join '').Trim()
        if ($installationId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw 'Runtime installation identity is invalid.'
        }
        return $installationId.ToLowerInvariant()
    }
    finally {
        if ($null -eq $previous) {
            Remove-Item Env:NEWSROOM_RUNTIME_ROOT -ErrorAction SilentlyContinue
        }
        else {
            $env:NEWSROOM_RUNTIME_ROOT = $previous
        }
    }
}

function Write-StartLauncher(
    [string]$PathValue,
    [string]$Install,
    [string]$Runtime,
    [int]$ListenPort,
    [string]$InstallationId
) {
    $pythonLiteral = Quote-PowerShellLiteral $PythonExe
    $installLiteral = Quote-PowerShellLiteral $Install
    $runtimeLiteral = Quote-PowerShellLiteral $Runtime
    $installationLiteral = Quote-PowerShellLiteral $InstallationId
    $content = @"
[CmdletBinding()]
param([switch]`$NoBrowser)
`$ErrorActionPreference = 'Stop'
`$env:PYTHONPATH = $installLiteral
`$expectedInstallationId = $installationLiteral
`$runtimeRoot = $runtimeLiteral
`$startInfo = New-Object System.Diagnostics.ProcessStartInfo
`$startInfo.FileName = $pythonLiteral
`$startInfo.Arguments = '-m newsroom.runtime supervisor --environment prod --root "' + `$runtimeRoot + '" --host 127.0.0.1 --port $ListenPort'
`$startInfo.WorkingDirectory = $installLiteral
`$startInfo.UseShellExecute = `$false
`$startInfo.CreateNoWindow = `$true
`$process = [System.Diagnostics.Process]::Start(`$startInfo)
`$identityUri = 'http://127.0.0.1:$ListenPort/api/v1/runtime/identity'
`$ready = `$false
for (`$attempt = 0; `$attempt -lt 60; `$attempt++) {
    try {
        `$identity = Invoke-RestMethod -Uri `$identityUri -Method Get -TimeoutSec 1
        if (`$identity.service -eq 'newsroom' -and `$identity.managed -eq `$true -and `$identity.installation_id -eq `$expectedInstallationId) {
            `$ready = `$true
            break
        }
    }
    catch {
    }
    if (`$process.HasExited -and `$process.ExitCode -ne 0) {
        throw "Newsroom could not start on its configured endpoint. No process was killed and no alternate port was selected. Review the Newsroom runtime logs, resolve the reported owner or port conflict, then use Start Newsroom again."
    }
    Start-Sleep -Milliseconds 500
}
if (-not `$ready) {
    throw "Newsroom did not become available on its configured endpoint within the startup deadline. No alternate port was selected. Review the Newsroom runtime logs and retry."
}
if (-not `$NoBrowser) {
    Start-Process 'http://127.0.0.1:$ListenPort/' | Out-Null
}
exit 0
"@
    Set-Content -LiteralPath $PathValue -Value $content -Encoding utf8
}

function Write-StartShortcut([string]$ShortcutPath, [string]$Launcher, [string]$WorkingDirectory) {
    $powershell = (Get-Command 'powershell.exe' -ErrorAction Stop).Source
    New-Item -ItemType Directory -Path (Split-Path -Parent $ShortcutPath) -Force | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($ShortcutPath)
    $shortcut.TargetPath = $powershell
    $shortcut.Arguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Launcher`""
    $shortcut.WorkingDirectory = $WorkingDirectory
    $shortcut.Description = 'Start Newsroom'
    $shortcut.Save()
}

function Register-StartTask([string]$TaskName, [string]$Launcher, [string]$WorkingDirectory) {
    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    if (-not [string]::Equals($RunAsUser, $currentUser, [StringComparison]::OrdinalIgnoreCase)) {
        throw "RunAsUser must match the current Windows user for Newsroom sign-in startup. Current user: $currentUser"
    }
    $actionArguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Launcher`" -NoBrowser"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArguments -WorkingDirectory $WorkingDirectory
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $RunAsUser
    $settings = New-ScheduledTaskSettingsSet `
        -RestartCount 5 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Registered $TaskName for interactive user sign-in with bounded restart policy."
}

function Get-LegacyTaskRecords {
    $records = @()
    foreach ($name in $LegacyTaskNames.Keys) {
        $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            continue
        }
        $expectedLauncher = [string]$LegacyTaskNames[$name]
        $actions = @($task.Actions)
        $recognized = $false
        if ($actions.Count -eq 1) {
            $execute = [string]$actions[0].Execute
            $arguments = [string]$actions[0].Arguments
            $recognized = ($execute -match '(?i)(^|\\)powershell(\.exe)?$') -and ($arguments.IndexOf($expectedLauncher, [StringComparison]::OrdinalIgnoreCase) -ge 0)
        }
        $records += [pscustomobject]@{
            Name = $name
            Recognized = $recognized
            ExpectedLauncher = $expectedLauncher
        }
    }
    return @($records)
}

function Remove-ReviewedLegacyTasks([object[]]$Records) {
    foreach ($record in $Records) {
        if (-not [bool]$record.Recognized) {
            throw "Refusing legacy-task migration because $($record.Name) does not match the known Newsroom launcher contract. Review it manually; no task was removed."
        }
    }
    foreach ($record in $Records) {
        Unregister-ScheduledTask -TaskName ([string]$record.Name) -Confirm:$false
        Write-Host "Removed reviewed legacy Newsroom task: $($record.Name)"
    }
}

$SourceRoot = Resolve-FullPath $SourceRoot
$InstallRoot = Resolve-FullPath $InstallRoot
$RuntimeRoot = Resolve-FullPath $RuntimeRoot
$ShortcutRoot = Resolve-FullPath $ShortcutRoot
if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    throw "Source repository does not exist: $SourceRoot"
}
if ($InstallRoot -eq $RuntimeRoot) {
    throw 'InstallRoot and RuntimeRoot must be separate paths.'
}
Assert-OutsideSource $InstallRoot $SourceRoot
Assert-OutsideSource $RuntimeRoot $SourceRoot
if ($RuntimeRoot -notmatch '(?i)[\\/]prod$') {
    throw "RuntimeRoot must end with 'prod': $RuntimeRoot"
}
if ($Port -lt 1 -or $Port -gt 65535) {
    throw 'Port must be between 1 and 65535.'
}
if ($RegisterTasks -and $Mode -ne 'Install') {
    throw '-RegisterTasks requires -Mode Install.'
}
if ($MigrateLegacyTasks -and (-not $RegisterTasks -or $Mode -ne 'Install')) {
    throw '-MigrateLegacyTasks requires -Mode Install -RegisterTasks so a new namespaced authority exists before legacy tasks are removed.'
}
if ($ConfigureTailscale -and $Mode -ne 'Install') {
    throw '-ConfigureTailscale requires -Mode Install.'
}

$pythonCommand = Get-Command $PythonExe -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand -or [string]::IsNullOrWhiteSpace($pythonCommand.Source)) {
    throw "Python executable was not found: $PythonExe"
}
$PythonExe = $pythonCommand.Source

if (-not $SkipChecks) {
    Invoke-Checked $PythonExe @('-m', 'pytest', '-q') $SourceRoot
    Invoke-Checked $PythonExe @('-m', 'compileall', '-q', 'newsroom', 'scripts', 'tests') $SourceRoot
    Invoke-Checked 'npm.cmd' @('run', 'typecheck') (Join-Path $SourceRoot 'frontend')
    Invoke-Checked 'npm.cmd' @('run', 'build') (Join-Path $SourceRoot 'frontend')
    Invoke-Checked 'npm.cmd' @('audit', '--audit-level=high') (Join-Path $SourceRoot 'frontend')
    Invoke-Checked $PythonExe @('-m', 'newsroom.evals', 'validate') $SourceRoot
    Invoke-Checked 'git.exe' @('diff', '--check') $SourceRoot
}

$identity = Get-ReleaseIdentity $SourceRoot
Write-Host ('Release identity:' + ($identity | ConvertTo-Json -Depth 5 -Compress))
if ($Mode -eq 'Install' -and -not [bool]$identity.worktree_clean) {
    throw 'Refusing production install: source worktree is not clean. Create and review the accepted checkpoint first.'
}
if ($Mode -eq 'Install' -and -not (Test-Path -LiteralPath (Join-Path $SourceRoot 'frontend\dist\index.html') -PathType Leaf)) {
    throw 'Refusing production install: frontend/dist/index.html is missing; build the accepted frontend first.'
}

$legacyTasks = @()
if ($Mode -eq 'Install') {
    $legacyTasks = @(Get-LegacyTaskRecords)
    if ($legacyTasks.Count -gt 0) {
        Write-Warning ("Detected legacy Newsroom tasks: " + (($legacyTasks | ForEach-Object { $_.Name }) -join ', '))
        if ($RegisterTasks -and -not $MigrateLegacyTasks) {
            throw 'Legacy Newsroom tasks are present. Review them and rerun with -MigrateLegacyTasks to replace only recognized historical Newsroom tasks; no install files or tasks were changed.'
        }
        if ($MigrateLegacyTasks -and @($legacyTasks | Where-Object { -not $_.Recognized }).Count -gt 0) {
            throw 'At least one legacy task does not match the known Newsroom launcher contract. Review it manually; no install files or tasks were changed.'
        }
    }
}

$runtimeConfigArgs = @('-m', 'newsroom.cli', 'migrate', '--environment', 'prod', '--root', $RuntimeRoot)
if ($Mode -eq 'Install') {
    if (Test-Path -LiteralPath $InstallRoot) {
        $existing = @(Get-ChildItem -LiteralPath $InstallRoot -Force)
        if ($existing.Count -gt 0) {
            throw "InstallRoot must be absent or empty; refusing to overwrite: $InstallRoot"
        }
    }
    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    Invoke-Checked $PythonExe $runtimeConfigArgs $SourceRoot
    Invoke-Checked $PythonExe @('-m', 'newsroom.cli', 'verify', '--environment', 'prod', '--root', $RuntimeRoot) $SourceRoot

    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    foreach ($record in @($identity.artifact_files)) {
        $relative = [string]$record.path
        $sourceFile = Join-Path $SourceRoot $relative
        $destination = Join-Path $InstallRoot $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $sourceFile -Destination $destination
    }

    $installationId = Get-InstallationId $RuntimeRoot
    $taskName = "Newsroom-$($installationId.Substring(0, 12))-Start"
    $launcherPath = Join-Path $InstallRoot 'start-newsroom.ps1'
    $shortcutPath = Join-Path $ShortcutRoot 'Start Newsroom.lnk'
    Write-StartLauncher $launcherPath $InstallRoot $RuntimeRoot $Port $installationId
    Write-StartShortcut $shortcutPath $launcherPath $InstallRoot

    $taskRegistered = $false
    if ($RegisterTasks) {
        Register-StartTask $taskName $launcherPath $InstallRoot
        $taskRegistered = $true
        if ($MigrateLegacyTasks -and $legacyTasks.Count -gt 0) {
            Remove-ReviewedLegacyTasks $legacyTasks
        }
    }

    $manifest = [ordered]@{
        format_version = 2
        generated_at_utc = [DateTime]::UtcNow.ToString('o')
        source_commit = $identity.source_commit
        worktree_clean = [bool]$identity.worktree_clean
        source_tree_sha256 = $identity.source_tree_sha256
        artifact_sha256 = $identity.artifact_sha256
        artifact_files = @($identity.artifact_files)
        install_root = $InstallRoot
        runtime_root = $RuntimeRoot
        installation_id = $installationId
        api_bind = "127.0.0.1:$Port"
        launcher = 'start-newsroom.ps1'
        launcher_sha256 = (Get-FileHash -LiteralPath $launcherPath -Algorithm SHA256).Hash.ToLowerInvariant()
        shortcut = $shortcutPath
        shortcut_sha256 = (Get-FileHash -LiteralPath $shortcutPath -Algorithm SHA256).Hash.ToLowerInvariant()
        tasks = @($taskName)
        task_registered = $taskRegistered
        task_trigger = 'AtLogOn'
        task_logon_type = 'Interactive'
        run_as_user = $RunAsUser
        legacy_tasks_detected = @($legacyTasks | ForEach-Object { $_.Name })
        legacy_tasks_migrated = [bool]($MigrateLegacyTasks -and $legacyTasks.Count -gt 0)
        pre_login_supported = $false
    }
    $manifestPath = Join-Path $InstallRoot 'release-manifest.json'
    $previousInstall = $env:NEWSROOM_INSTALL_ROOT
    $env:NEWSROOM_INSTALL_ROOT = $InstallRoot
    try {
        $installedJson = & $PythonExe -c "import json, os; from newsroom.release import build_artifact_manifest; print(json.dumps(build_artifact_manifest(os.environ['NEWSROOM_INSTALL_ROOT'])))"
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not calculate installed artifact identity.'
        }
        $installed = ($installedJson -join "`n") | ConvertFrom-Json
    }
    finally {
        if ($null -eq $previousInstall) {
            Remove-Item Env:NEWSROOM_INSTALL_ROOT -ErrorAction SilentlyContinue
        }
        else {
            $env:NEWSROOM_INSTALL_ROOT = $previousInstall
        }
    }
    if ([string]$installed.digest -ne [string]$identity.artifact_sha256) {
        throw 'Installed artifact digest does not match the source release digest.'
    }
    $manifest.installed_artifact_sha256 = [string]$installed.digest
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $manifestPath -Encoding utf8

    if ($ConfigureTailscale) {
        if (-not (Get-Command 'tailscale.exe' -ErrorAction SilentlyContinue)) {
            throw 'Tailscale CLI was not found; install/sign in to Tailscale before configuring Serve.'
        }
        Write-Host 'Configuring private HTTPS Tailscale Serve for localhost only.'
        & tailscale.exe serve --bg --https=443 "http://127.0.0.1:$Port"
        if ($LASTEXITCODE -ne 0) {
            throw "Tailscale Serve configuration failed with exit code $LASTEXITCODE"
        }
    }
    Write-Host "Installed release manifest: $manifestPath"
    Write-Host "Start Newsroom shortcut: $shortcutPath"
}
else {
    Write-Host "Validation only; no install root, runtime root, shortcut, tasks, or Tailscale configuration was changed."
    if (-not [bool]$identity.worktree_clean) {
        Write-Warning 'Source worktree is dirty; validation results are not eligible for production promotion.'
    }
}
