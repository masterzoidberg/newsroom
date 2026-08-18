[CmdletBinding()]
param(
    [ValidateSet('Validate', 'Install')]
    [string]$Mode = 'Validate',
    [string]$SourceRoot = '',
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Newsroom\app\prod'),
    [string]$RuntimeRoot = (Join-Path $env:LOCALAPPDATA 'Newsroom\prod'),
    [string]$PythonExe = 'python',
    [int]$Port = 8127,
    [string]$RunAsUser = $env:USERNAME,
    [switch]$RegisterTasks,
    [switch]$ConfigureTailscale,
    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Join-Path $PSScriptRoot '..'
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

function Write-Launcher([string]$PathValue, [string]$Command, [string]$Install, [string]$Runtime, [int]$ListenPort) {
    $pythonLiteral = Quote-PowerShellLiteral $PythonExe
    $installLiteral = Quote-PowerShellLiteral $Install
    $runtimeLiteral = Quote-PowerShellLiteral $Runtime
    $arguments = "-m newsroom.runtime $Command --environment prod --root $runtimeLiteral"
    if ($Command -eq 'api') {
        $arguments += " --host 127.0.0.1 --port $ListenPort"
    }
    $content = @"
`$ErrorActionPreference = 'Stop'
`$env:PYTHONPATH = $installLiteral
& $pythonLiteral $arguments
exit `$LASTEXITCODE
"@
    Set-Content -LiteralPath $PathValue -Value $content -Encoding utf8
}

function Register-ProcessTask([string]$TaskName, [string]$Launcher, [string]$WorkingDirectory) {
    $actionArguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Launcher`""
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArguments -WorkingDirectory $WorkingDirectory
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet `
        -RestartCount 5 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable `
        -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType S4U -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Registered $TaskName with at-start and five-restart/one-minute bounds."
}

$SourceRoot = Resolve-FullPath $SourceRoot
$InstallRoot = Resolve-FullPath $InstallRoot
$RuntimeRoot = Resolve-FullPath $RuntimeRoot
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
    $launchers = @{
        api = (Join-Path $InstallRoot 'run-api.ps1')
        worker = (Join-Path $InstallRoot 'run-worker.ps1')
        scheduler = (Join-Path $InstallRoot 'run-scheduler.ps1')
    }
    Write-Launcher $launchers.api 'api' $InstallRoot $RuntimeRoot $Port
    Write-Launcher $launchers.worker 'worker' $InstallRoot $RuntimeRoot $Port
    Write-Launcher $launchers.scheduler 'scheduler' $InstallRoot $RuntimeRoot $Port

    $manifest = [ordered]@{
        format_version = 1
        generated_at_utc = [DateTime]::UtcNow.ToString('o')
        source_commit = $identity.source_commit
        worktree_clean = [bool]$identity.worktree_clean
        source_tree_sha256 = $identity.source_tree_sha256
        artifact_sha256 = $identity.artifact_sha256
        artifact_files = @($identity.artifact_files)
        install_root = $InstallRoot
        runtime_root = $RuntimeRoot
        api_bind = "127.0.0.1:$Port"
        tasks = @('Newsroom-API', 'Newsroom-Worker', 'Newsroom-Scheduler')
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

    if ($RegisterTasks) {
        Register-ProcessTask 'Newsroom-API' $launchers.api $InstallRoot
        Register-ProcessTask 'Newsroom-Worker' $launchers.worker $InstallRoot
        Register-ProcessTask 'Newsroom-Scheduler' $launchers.scheduler $InstallRoot
    }
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
}
else {
    Write-Host "Validation only; no install root, runtime root, tasks, or Tailscale configuration was changed."
    if (-not [bool]$identity.worktree_clean) {
        Write-Warning 'Source worktree is dirty; validation results are not eligible for production promotion.'
    }
}
