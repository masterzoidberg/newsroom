[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$Repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location $Repo
try {
    Write-Host '>>> Python tests'
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "pytest failed with exit $LASTEXITCODE" }

    Write-Host '>>> Hermes runtime dependency check'
    $hits = Get-ChildItem -Path (Join-Path $Repo 'newsroom') -Filter '*.py' -Recurse |
        Select-String -Pattern 'HERMES_HOME|hermes_constants|import hermes|from hermes' -CaseSensitive:$false
    if ($hits) {
        $hits | ForEach-Object { Write-Host $_ }
        throw 'Standalone production package still contains a Hermes runtime dependency.'
    }

    Write-Host '>>> Runtime data guard'
    $forbidden = Get-ChildItem -Path $Repo -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '\.(db|db-wal|db-shm|sqlite|sqlite3)$' }
    if ($forbidden) {
        $forbidden | ForEach-Object { Write-Host $_.FullName }
        throw 'Runtime database artifacts are present in the source tree.'
    }

    Write-Host 'Bootstrap verification passed.'
}
finally {
    Pop-Location
}
