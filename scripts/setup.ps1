# Vayu-X — first-time setup (Windows / PowerShell)
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "=== Vayu-X setup - Team 152 ===" -ForegroundColor Cyan

# ---------- .env ----------
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created .env from template - fill in your credentials before ingesting data"
} else {
    Write-Host "  .env already exists, leaving it alone"
}

# ---------- Python services ----------
foreach ($service in @("backend", "ai-model", "alert-system", "data-pipeline")) {
    Write-Host ""
    Write-Host "--- $service ---" -ForegroundColor Yellow
    Push-Location $service
    try {
        python -m venv .venv
        & ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
        & ".venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
        Write-Host "  dependencies installed"
    } finally {
        Pop-Location
    }
}

# ---------- Frontend ----------
Write-Host ""
Write-Host "--- frontend ---" -ForegroundColor Yellow
Push-Location "frontend"
try {
    npm install --silent
    Write-Host "  dependencies installed"
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host @"

Next steps:
  1. Fill credentials in .env  (MOSDAC, Earthdata, CDS - see docs/data-sources.md)
  2. Start the stack:          docker compose up
  3. Or run services individually - see each service's README

  Dashboard      http://localhost:5173
  Backend docs   http://localhost:8000/docs
  Model docs     http://localhost:8001/docs
  Alert docs     http://localhost:8002/docs

Note: ALERT_DRY_RUN defaults to true - alerts are logged, not sent.
"@
