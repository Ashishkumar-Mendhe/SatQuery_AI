[CmdletBinding()]
param(
    [switch]$IncludeDatabase
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
$backend = Join-Path $repositoryRoot 'backend'
$frontend = Join-Path $repositoryRoot 'frontend'

if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing local Python environment: $python"
}
if (-not (Test-Path -LiteralPath (Join-Path $frontend 'node_modules'))) {
    throw 'Missing frontend dependencies. Run npm ci from frontend first.'
}

Push-Location $backend
try {
    & $python -m ruff check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m ruff format --check .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m mypy src tests
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m pytest -p no:cacheprovider -m 'not integration'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Push-Location $frontend
try {
    & npm.cmd run format:check
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm.cmd run typecheck
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm.cmd run test:run -- --testTimeout=15000
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

if ($IncludeDatabase) {
    & (Join-Path $PSScriptRoot 'verify-database.ps1')
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Output 'Non-database repository verification passed.'
