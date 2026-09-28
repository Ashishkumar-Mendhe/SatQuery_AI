[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
$backend = Join-Path $repositoryRoot 'backend'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is required for the isolated PostgreSQL/PostGIS integration check.'
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Missing local Python environment: $python"
}
$previousPostgresPassword = $env:POSTGRES_PASSWORD
$previousTestPort = $env:TEST_POSTGRES_PORT
$previousTestPassword = $env:TEST_POSTGRES_PASSWORD
$previousTestDatabaseUrl = $env:SATQUERY_TEST_DATABASE_URL
$previousDatabaseUrl = $env:DATABASE_URL
$testPort = if ($env:TEST_POSTGRES_PORT) { $env:TEST_POSTGRES_PORT } else { '55432' }
$testPassword = if ($env:TEST_POSTGRES_PASSWORD) {
    $env:TEST_POSTGRES_PASSWORD
} else {
    'satquery_test_only'
}
$env:POSTGRES_PASSWORD = if ($env:POSTGRES_PASSWORD) {
    $env:POSTGRES_PASSWORD
} else {
    'unused_test_profile_value'
}
$env:TEST_POSTGRES_PORT = $testPort
$env:TEST_POSTGRES_PASSWORD = $testPassword
$testPasswordEncoded = [System.Uri]::EscapeDataString($testPassword)
$env:SATQUERY_TEST_DATABASE_URL = "postgresql+psycopg://satquery_test:${testPasswordEncoded}@127.0.0.1:${testPort}/satquery_test"

Push-Location $repositoryRoot
try {
    & docker compose --profile test up --wait -d db-test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Push-Location $backend
    try {
        & $python -m pytest -p no:cacheprovider -m integration
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $env:DATABASE_URL = $env:SATQUERY_TEST_DATABASE_URL
        & $python -m alembic current
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & $python -m alembic heads
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        $env:DATABASE_URL = $previousDatabaseUrl
        Pop-Location
    }
} finally {
    & docker compose stop db-test
    & docker compose rm -f db-test
    $env:POSTGRES_PASSWORD = $previousPostgresPassword
    $env:TEST_POSTGRES_PORT = $previousTestPort
    $env:TEST_POSTGRES_PASSWORD = $previousTestPassword
    $env:SATQUERY_TEST_DATABASE_URL = $previousTestDatabaseUrl
    $env:DATABASE_URL = $previousDatabaseUrl
    Pop-Location
}

Write-Output 'Isolated PostgreSQL/PostGIS migration verification passed.'
