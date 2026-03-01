$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
  Write-Host "`n==> $Message"
}

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Step "Ensure .env exists"
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

Write-Step "Start local infra (Postgres/Redis)"
docker compose -f "infra/docker-compose.yml" up -d

Write-Step "Create venv"
if (-not (Test-Path ".venv")) {
  python -m venv .venv
}

Write-Step "Install dependencies (editable + dev)"
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Write-Step "Run database migrations"
& .\.venv\Scripts\python.exe -m alembic upgrade head

Write-Step "Done"
Write-Host ""
Write-Host "Next — open separate terminals for each service:"
Write-Host ""
Write-Host "  # API server"
Write-Host "  .\scripts\dev.ps1"
Write-Host ""
Write-Host "  # Celery worker"
Write-Host "  .\.venv\Scripts\python.exe -m celery -A apps.worker.celery_app.celery_app worker --loglevel=info"
Write-Host ""
Write-Host "  # Indexer (requires INDEXER_RPC_URL + INDEXER_CONTRACTS in .env)"
Write-Host "  .\.venv\Scripts\python.exe -m apps.indexer.main"
