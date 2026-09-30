# Explicit local development entry point. Never use this to configure production.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Existing project Python environment was not found.' }
$env:FORTUNE_ENV = 'development'
if (-not $env:FORTUNE_HISTORY_DEV_USER_ID) { $env:FORTUNE_HISTORY_DEV_USER_ID = 'local-dev-user' }
Write-Host 'Local API: http://127.0.0.1:8765 (development history enabled)'
& $pythonPath (Join-Path $PSScriptRoot 'server.py')
