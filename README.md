# sentient-backend

Backend monorepo for Sentient Finance.

## Structure

- `apps/api` - FastAPI public/internal API
- `apps/indexer` - On-chain event indexer
- `apps/worker` - Strategy + execution workers
- `libs/core` - Domain logic
- `libs/chain` - Web3/contract clients
- `libs/db` - DB models and persistence
- `infra` - Local infra (Postgres/Redis)

## Quickstart

### Windows (PowerShell)

```powershell
Copy-Item .env.example .env -ErrorAction SilentlyContinue
.\scripts\bootstrap.ps1
.\.venv\Scripts\activate
.\scripts\dev.ps1
```

### Git Bash / Linux / macOS

```bash
cp .env.example .env
./scripts/bootstrap.sh
source .venv/Scripts/activate  # Windows Git Bash
./scripts/dev.sh
```

### Optional: Makefile (if you have `make`)

```bash
make help
```

## CI

![CI](https://github.com/sentient-finance/sentient-backend/actions/workflows/openclaw-bridge.yml/badge.svg)

## Day 1 Scope

- Project scaffold
- Health endpoints
- Local infra compose
- Python packaging baseline

## GitHub → OpenClaw bridge (optional)

Workflow file: `.github/workflows/openclaw-bridge.yml`

Required repository secrets:

- `OPENCLAW_HOOK_URL` (example: `https://<public-domain>/hooks/agent`)
- `OPENCLAW_HOOK_TOKEN` (matches `hooks.token` in OpenClaw config)
