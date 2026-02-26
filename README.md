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
