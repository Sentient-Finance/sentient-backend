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
  $port = "8000"
}

& $python -m uvicorn apps.api.app.main:app --reload --port $port

