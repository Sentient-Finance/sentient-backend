<#
.SYNOPSIS
  Chạy API + Celery Beat cùng lúc (dev flow).
  API chạy foreground, Beat scheduler chạy background.
  Beat scheduler chạy strategy-tick, risk-guard-tick, và indexer-tick.
  Ctrl+C sẽ dừng cả hai.
#>
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing .venv. Run .\scripts\bootstrap.ps1 first."
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

$port = $env:PORT
if ([string]::IsNullOrWhiteSpace($port)) {
  $port = "8001"
}

# Start Celery Beat (scheduler) in background
$beatJob = Start-Job -ScriptBlock {
  Set-Location $using:repoRoot
  & $using:python -m celery -A apps.worker.celery_app beat -l info
}

Write-Host "Beat scheduler started (Job $($beatJob.Id)). Starting API on port $port..."

try {
  # Run API in foreground (blocking)
  & $python -m uvicorn apps.api.app.main:app --reload --reload-dir apps --reload-dir libs --port $port
} finally {
  Write-Host "`nStopping beat..."
  Stop-Job $beatJob -ErrorAction SilentlyContinue
  Remove-Job $beatJob -Force -ErrorAction SilentlyContinue
}
