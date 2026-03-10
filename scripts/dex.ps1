<#
.SYNOPSIS
  Chạy API + Indexer cùng lúc (dev flow).
  API chạy foreground, Indexer chạy background.
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

# Start indexer in background
$indexerJob = Start-Job -ScriptBlock {
  Set-Location $using:repoRoot
  & $using:python -m apps.indexer.main --loop
}

Write-Host "Indexer started (Job $($indexerJob.Id)). Starting API on port $port..."

try {
  # Run API in foreground (blocking)
  & $python -m uvicorn apps.api.app.main:app --reload --reload-dir apps --reload-dir libs --port $port
} finally {
  Write-Host "`nStopping indexer..."
  Stop-Job $indexerJob -ErrorAction SilentlyContinue
  Remove-Job $indexerJob -Force -ErrorAction SilentlyContinue
}
