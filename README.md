# sentient-backend

Backend monorepo for Sentient Finance — hybrid architecture:

- **The Graph** for read / event-history queries
- **FastAPI + Celery worker** for write / action + CRE execution

## Repository layout

```
apps/
  api/          FastAPI public + internal API
  indexer/      On-chain event indexer (poll loop)
  worker/       Celery strategy + execution workers
libs/
  core/         Settings, shared utilities
  chain/        Web3 / contract clients
  db/           SQLAlchemy models, session factory
infra/
  docker-compose.yml   Local Postgres 16 + Redis 7
alembic/        Database migrations
scripts/        Bootstrap helpers (Windows only)
```

## Quickstart

### Linux / macOS

```bash
# 1. Create venv + install deps
make venv
make install

# 2. Copy env and start infra
cp .env.example .env
make db-up

# 3. Migrate database
make migrate

# 4. Run each service (one terminal per service)
make dev        # API  →  http://localhost:8000
make worker     # Celery worker
make indexer    # On-chain event indexer
```

### Windows (PowerShell)

```powershell
# 1. Bootstrap: copy .env, docker, venv, install, migrate (one-time)
.\scripts\bootstrap.ps1

# 2. Activate venv
.\.venv\Scripts\Activate.ps1

# 3. API server
.\scripts\dev.ps1

# 4. Celery worker (new terminal)
.\.venv\Scripts\python.exe -m celery -A apps.worker.celery_app.celery_app worker --loglevel=info

# 5. Indexer (new terminal, requires INDEXER_RPC_URL + INDEXER_CONTRACTS in .env)
.\.venv\Scripts\python.exe -m apps.indexer.main
```

## Local runbook

### Infrastructure

```bash
# Start Postgres 16 + Redis 7
make db-up

# Stop (keep volumes)
make db-down

# Destroy including data
docker compose -f infra/docker-compose.yml down -v
```

### Database migrations

```bash
# Apply all pending migrations
make migrate

# Create empty migration
make revision m="add users table"

# Autogenerate migration from model changes (m optional, defaults to timestamp)
make autogen
make autogen m="add block_timestamp to chain_events"

# Rollback 1 step
make downgrade
```

### Running services

| Service        | Makefile            | Direct command                                                                 |
| -------------- | ------------------- | ------------------------------------------------------------------------------ |
| API            | `make dev`          | `python -m uvicorn apps.api.app.main:app --reload`                             |
| Worker         | `make worker`       | `python -m celery -A apps.worker.celery_app.celery_app worker --loglevel=info` |
| Indexer (loop) | `make indexer`      | `python -m apps.indexer.main`                                                  |
| Indexer (once) | `make indexer-once` | `python -m apps.indexer.main --once`                                           |

> Run `make help` to see all targets.

### Health endpoints

| Endpoint         | Description                          |
| ---------------- | ------------------------------------ |
| `GET /health`    | Root health (load-balancer friendly) |
| `GET /v1/health` | API v1 health                        |
| `GET /v1/ready`  | Readiness probe                      |

### Tests

```bash
make test         # or: pytest
```

### Lint / format

```bash
make lint         # ruff check
make fix          # ruff check --fix
make format       # black .
```

## Environment variables

Copy `.env.example` → `.env` and fill in the necessary values.

| Variable            | Default                    | Description                                |
| ------------------- | -------------------------- | ------------------------------------------ |
| `APP_ENV`           | `dev`                      | Environment name                           |
| `APP_PORT`          | `8000`                     | API port                                   |
| `POSTGRES_HOST`     | `127.0.0.1`                | Postgres host                              |
| `POSTGRES_DB`       | `sentient`                 | Database name                              |
| `REDIS_URL`         | `redis://127.0.0.1:6379/0` | Redis DSN (broker + backend)               |
| `ETH_RPC_URL`       | —                          | Ethereum JSON-RPC endpoint                 |
| `DATABASE_URL`      | —                          | Full DSN override (optional)               |
| `INDEXER_RPC_URL`   | —                          | RPC for indexer (fallback: `BASE_RPC_URL`) |
| `INDEXER_CONTRACTS` | —                          | Comma-separated contract addresses         |
| `INDEXER_CHAIN_ID`  | `84532`                    | Chain ID (default: Base Sepolia)           |

## CI

Workflow: `.github/workflows/openclaw-bridge.yml`

Required secrets: `OPENCLAW_HOOK_URL`, `OPENCLAW_HOOK_TOKEN`
