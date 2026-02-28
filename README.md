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

## Quickstart (local Python)

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d postgres redis
python -m venv .venv && source .venv/bin/activate
pip install -e .
uvicorn apps.api.app.main:app --reload --port 8000
```

## Quickstart (Docker runtime)

```bash
# API + worker + infra
cd infra
docker compose --profile runtime up -d --build

# Optional: indexer (requires INDEXER_RPC_URL + INDEXER_CONTRACTS in env)
docker compose --profile indexer up -d --build
```

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
