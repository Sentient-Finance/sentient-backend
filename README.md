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
scripts/        Bootstrap + dev helpers
```

## Quickstart — 3 steps

### Git Bash / Linux / macOS

```bash
# 1. Bootstrap (copies .env, starts docker, installs venv)
cp .env.example .env && ./scripts/bootstrap.sh

# 2. Activate venv
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # Linux / macOS

# 3. Start API
uvicorn apps.api.app.main:app --reload
```

Then open: <http://localhost:8000/health>

### Windows (PowerShell)

```powershell
# 1. Bootstrap
Copy-Item .env.example .env -ErrorAction SilentlyContinue; .\scripts\bootstrap.ps1

# 2. Activate venv
.\.venv\Scripts\Activate.ps1

# 3. Start API
uvicorn apps.api.app.main:app --reload
```

### Makefile shorthand (requires `make`)

```bash
make db-up    # step 1 — start infra only
make install  # install deps into venv
make dev      # step 3 — uvicorn with reload
```

Run `make help` to see all targets.

## Local runbook

### Infrastructure

```bash
# Start Postgres 16 + Redis 7
docker compose -f infra/docker-compose.yml up -d

# Stop (keeps volumes)
docker compose -f infra/docker-compose.yml down

# Destroy including data
docker compose -f infra/docker-compose.yml down -v
```

Wait ~5 s for Postgres to become healthy before running migrations.

### Database migrations

```bash
# Apply all pending migrations
make migrate           # or: python -m alembic upgrade head

# Create a new migration (autogenerate from models)
make revision MSG="add users table"

# Roll back one step
make downgrade
```

### Running services

| Service | Command |
|---------|---------|
| API | `uvicorn apps.api.app.main:app --reload` |
| Worker | `celery -A apps.worker.celery_app.celery_app worker --loglevel=info` |
| Indexer | `python -m apps.indexer.main` |

Or via Makefile: `make dev`, `make worker`, `make indexer`.

### Health endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Root health (load-balancer friendly) |
| `GET /v1/health` | API v1 health |
| `GET /v1/ready` | Readiness probe |
| `GET /v1/vaults` | Vault list (pagination + chain filter) |
| `GET /v1/vault/{address}` | Vault detail |
| `GET /v1/vault/{address}/history` | Vault event history (type/from/to filters) |

#### API behavior notes
- `GET /v1/vault/{address}`
  - `404` when vault is not found
  - `409` when address exists on multiple chains and `chain` query param is not provided
- `GET /v1/vault/{address}/history`
  - `404` when vault is not found
  - `422` when invalid date range (`from > to`) or invalid params are provided

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

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `dev` | Environment name |
| `APP_PORT` | `8000` | API port |
| `POSTGRES_HOST` | `127.0.0.1` | Postgres host |
| `POSTGRES_DB` | `sentient` | Database name |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis DSN (broker + backend) |
| `ETH_RPC_URL` | — | Ethereum JSON-RPC endpoint |
| `DATABASE_URL` | — | Full DSN override (optional) |

## CI

Workflow: `.github/workflows/openclaw-bridge.yml`

Required secrets: `OPENCLAW_HOOK_URL`, `OPENCLAW_HOOK_TOKEN`
