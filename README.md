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

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn apps.api.app.main:app --reload --port 8000
```

## Day 1 Scope

- Project scaffold
- Health endpoints
- Local infra compose
- Python packaging baseline

## Indexer (Issue #3) quick run

Set env:

```bash
export INDEXER_RPC_URL="https://base-sepolia.g.alchemy.com/v2/<key>"
export INDEXER_CHAIN_ID=84532
export INDEXER_CONTRACTS="0xYourVaultFactory,0xYourVault"
export INDEXER_START_BLOCK=0
```

Run once:

```bash
python -m apps.indexer.main --once
```

## GitHub → OpenClaw bridge (optional)

Workflow file: `.github/workflows/openclaw-bridge.yml`

Required repository secrets:

- `OPENCLAW_HOOK_URL` (example: `https://<public-domain>/hooks/agent`)
- `OPENCLAW_HOOK_TOKEN` (matches `hooks.token` in OpenClaw config)
