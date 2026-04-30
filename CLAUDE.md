# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sentient Finance backend — a hybrid architecture combining:
- **The Graph** (subgraph) for read / event-history queries
- **FastAPI + Celery workers** for write / action + CRE execution
- **Chainlink CCIP + Feed Registry** for cross-chain infrastructure

## Bootstrap

```bash
cp .env.example .env && ./scripts/bootstrap.sh   # Linux/macOS
# Copy-Item .env.example .env; .\scripts\bootstrap.ps1  # Windows PowerShell
```

## Common Commands

```bash
# Setup
make venv           # Create virtual environment
make install        # Install app + dev dependencies + pre-commit hooks
make db-up         # Start Postgres 16 + Redis 7 (docker compose)

# Run services
make api           # FastAPI dev server (uvicorn with reload)
make worker        # Celery worker (queue: celery)
make worker-execution  # Execution worker (queue: execution, concurrency=1)
make beat           # Celery beat scheduler
make run-all       # All services via honcho (includes db-up)

# Database migrations (run after db-up)
make migrate        # Apply all pending migrations
make revision MSG="description"  # Create new migration
make downgrade REV=-1  # Roll back one step

# Quality
make lint          # ruff check
make fix           # ruff check --fix
make format        # black format
make type-check    # mypy type check
make test          # pytest (or: pytest tests/path/to/test.py -v)

# Production
make prod-up       # Build and start full stack (Docker)
make prod-down     # Stop production stack
make prod-logs     # Tail production logs
make db-down       # Stop Postgres/Redis (keeps volumes)

# Development (Docker)
make dev-up        # Start local dev stack (postgres, redis, monitoring)
make dev-down      # Stop local dev stack
make dev-logs      # Tail local dev logs
make dev-full      # Full dev stack (infra + honcho services)
```

Single test: `pytest tests/path/to/test.py -v`

**Honcho** (`make run-all`) starts all services (API + workers + beat) via a `Procfile` — requires `honcho` in the venv.

## Architecture

```
apps/
  api/           FastAPI application (apps/api/app/main.py:app)
    v1/routes/   Route modules: vaults.py, ccip.py, main.py
    limiter.py    Rate limiting via slowapi
  worker/        Celery application
    celery_app.py  Celery instance + beat schedule
    tasks.py      Task definitions: strategy, execution, risk_guard, indexer
  indexer/       On-chain event indexer (apps/indexer/main.py)
libs/
  core/config.py  pydantic-settings (Settings singleton via get_settings())
  chain/         Web3/contract clients: vault_reader, executor, price_feed
  db/            SQLAlchemy: models.py, session.py, base.py
alembic/         Database migrations (alembic upgrade head)
infra/           docker-compose.yml (Postgres 16, Redis 7, Prometheus, Loki, Grafana)
scripts/         Bootstrap helpers
```

### Service Interaction

1. **Indexer** (`worker.indexer.tick`) — polls The Graph subgraph every `INDEXER_TICK_SECONDS`, writes vault events to Postgres
2. **Strategy** (`worker.strategy.tick`) — runs on Celery Beat every `STRATEGY_TICK_SECONDS`, evaluates vault events against thresholds, enqueues execution tasks with Redis idempotency locks
3. **Execution** (`worker.execution.enqueue`) — routed to dedicated single-concurrency `execution` queue to prevent nonce collision; calls `performUpkeep` on vaults via `libs/chain/executor.py`
4. **Risk Guard** (`worker.risk_guard.tick`) — enforces `max_notional_per_trade`, `max_daily_notional`, `max_open_positions`

### API Routes

All routes prefixed `/api/v1`:
- `GET /api/v1/health` — liveness
- `GET /api/v1/ready` — readiness (checks DB)
- `GET /api/v1/vaults` — vault list with pagination + chain filter
- `GET /api/v1/vault/{address}` — vault detail (404 if not found, 409 if on multiple chains without chain param)
- `GET /api/v1/vault/{address}/history` — event history with type/from/to filters
- `GET /api/v1/ccip/config` — CCIP configuration
- `POST /api/v1/ccip/estimate-fees` — fee estimation

### Database

- **PostgreSQL 16** via docker compose (infra/docker-compose.yml)
- **SQLAlchemy 2** with async-capable session factory (`libs/db/session.py`)
- **Alembic** for migrations (alembic/env.py wired to `libs/db/base.py`)
- Connection pool keepalive: `_ping_db()` runs every 5 minutes to prevent timeouts

### Chainlink Integration

- `libs/core/config.py` — `chainlink_feed_registry_address` setting
- `apps/api/v1/routes/ccip.py` — CCIP config endpoint + fee estimation
- `libs/chain/price_feed.py` — Chainlink price feed reads via `eth_call`

### Rate Limiting

Slowapi-based, configured via `RATE_LIMIT_PUBLIC` (60/min default) and `RATE_LIMIT_HEAVY` (20/min). Applied per-IP via `apps/api/limiter.py`.

### Celery Beat Schedule

Three periodic tasks managed in `celery_app.py:beat_schedule`:
- `strategy-tick` — `STRATEGY_TICK_SECONDS` (default 60s)
- `risk-guard-tick` — `RISK_TICK_SECONDS` (default 60s)
- `indexer-tick` — `INDEXER_TICK_SECONDS` (default 10s)

### Key Settings

All via environment variables (pydantic-settings). Notable ones:
- `EXECUTOR_PRIVATE_KEY` — executor wallet for signing transactions
- `EXECUTOR_DRY_RUN` — if true, only simulates via `eth_call`
- `BASE_TOKEN_ADDRESS` — USDC on Base Sepolia by default
- `SUBGRAPH_URL`, `SUBGRAPH_API_KEY`, `SUBGRAPH_ID` — The Graph configuration
- `CHAIN_BASE_SEPOLIA_ID` — chain ID for subgraph network filtering (default 84532)
