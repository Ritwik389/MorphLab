param([int]$Port = 7860)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw 'Run scripts/setup_windows.ps1 first.' }
if (-not (Test-Path 'frontend/dist/index.html')) { throw 'Frontend missing. Run scripts/setup_windows.ps1.' }
& .venv/Scripts/python.exe app.py --port $Port
exit $LASTEXITCODE
