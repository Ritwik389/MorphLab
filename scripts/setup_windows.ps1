$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.11 from python.org with the Windows launcher.' }
if (-not (Test-Path '.venv/Scripts/python.exe')) { py -3.11 -m venv .venv }
& .venv/Scripts/python.exe -m pip install --upgrade pip wheel setuptools
if ($LASTEXITCODE) { throw 'Python bootstrap failed.' }
& .venv/Scripts/python.exe scripts/install_runtime.py --dev
if ($LASTEXITCODE) { throw 'Python installation failed. InsightFace may require Microsoft C++ Build Tools.' }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'Install FFmpeg (winget install Gyan.FFmpeg), restart PowerShell, then rerun setup.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Install Node.js 22 LTS and rerun setup.' }
& .venv/Scripts/python.exe scripts/download_models.py
if ($LASTEXITCODE) { throw 'Model download failed.' }
Push-Location frontend
try { npm ci; if ($LASTEXITCODE) { throw 'npm ci failed.' }; npm run build; if ($LASTEXITCODE) { throw 'Frontend build failed.' } }
finally { Pop-Location }
Write-Host 'Ready. Run: powershell -File scripts/start_windows.ps1'
