[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()

function Require-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $failures.Add("Missing required command: $Name")
        return $null
    }
    return $command
}

$node = Require-Command 'node'
$npm = Require-Command 'npm.cmd'
$python = Require-Command 'py'
$docker = Require-Command 'docker'

if ($null -ne $node) {
    $nodeVersion = (& node --version).TrimStart('v')
    $nodeMajor = [int]($nodeVersion.Split('.')[0])
    Write-Output "Node.js $nodeVersion"
    if ($nodeMajor -ne 24) {
        $failures.Add('SatQuery Phase 1 supports Node.js 24.x LTS.')
    }
}

if ($null -ne $npm) {
    $npmVersion = (& npm.cmd --version).Trim()
    Write-Output "npm $npmVersion"
    if ([int]($npmVersion.Split('.')[0]) -ne 11) {
        $failures.Add('SatQuery Phase 1 supports npm 11.x.')
    }
}

if ($null -ne $python) {
    $pythonVersion = (& py -c "import platform; print(platform.python_version())").Trim()
    $parts = $pythonVersion.Split('.')
    Write-Output "Python $pythonVersion"
    if ([int]$parts[0] -ne 3 -or [int]$parts[1] -notin @(13, 14)) {
        $failures.Add('SatQuery Phase 1 supports Python 3.13 or 3.14.')
    }
}

if ($null -ne $docker) {
    Write-Output (& docker --version)
    & docker compose version
    if ($LASTEXITCODE -ne 0) {
        $failures.Add('Docker Compose v2 is required for the local PostGIS workflow.')
    }
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Output 'All Phase 1 prerequisites are available.'

