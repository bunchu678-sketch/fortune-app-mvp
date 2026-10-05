# Explicit local development entry point. Never use this to configure production.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Existing project Python environment was not found.' }
$env:FORTUNE_ENV = 'development'
# Authentication is the default. A fixed development owner must be explicitly set by the operator.
if (-not $env:FORTUNE_PUBLIC_ORIGIN) { $env:FORTUNE_PUBLIC_ORIGIN = 'http://127.0.0.1:3000' }
Write-Host 'Local API: http://127.0.0.1:8765 (development authentication)'
& $pythonPath (Join-Path $PSScriptRoot 'server.py')
