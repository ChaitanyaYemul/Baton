$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (!(Test-Path '.venv/Scripts/python.exe')) { throw 'Create .venv and install requirements first; see README.md.' }
if (!(Test-Path 'dist/index.html')) { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } }
$env:BATON_DEMO = '1'
Write-Host 'Baton is opening at http://127.0.0.1:8000. Use BATON_REVIEWER_PASSWORD from .env when configured; otherwise the enabled synthetic demo uses baton-demo-2026.'
& .venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
