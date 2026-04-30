# Sentient Backend

> Backend monorepo for Sentient Finance — hybrid architecture combining The Graph for reads, FastAPI + Celery for writes and CRE execution, and Chainlink for cross-chain infrastructure.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────┐
│  The Graph  │────▶│   FastAPI    │────▶│  Celery Workers │
│  (subgraph) │     │  (REST/WSP)  │     │ (strategy/tasks)│
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                  │
                         ┌────────────────────────┼────────────────────────┐
                         │                        │                        │
               ┌─────────▼─────────┐   ┌─────────▼─────────┐   ┌─────────▼─────────┐
               │   PostgreSQL 16   │   │      Redis 7       │   │   Chainlink CCIP   │
               │   (persistent)    │   │  (broker/cache)    │   │  (cross-chain txs) │
               └───────────────────┘   └───────────────────┘   └───────────────────┘
```

## Tech Stack

| Layer               | Technology                                               |
| ------------------- | -------------------------------------------------------- |
| **Read layer**      | The Graph (subgraph) for event-history queries           |
| **Write layer**     | FastAPI + Celery workers                                 |
| **Blockchain**      | Web3.py, Chainlink CCIP + Feed Registry                  |
| **Database**        | PostgreSQL 16, SQLAlchemy 2 (async), Alembic migrations  |
| **Cache/Broker**    | Redis 7                                                  |
| **Monitoring**      | Prometheus, Loki, Grafana                                |
| **Infrastructure**  | Docker, Docker Compose                                   |

---

## Quickstart

### Prerequisites

- Python 3.12+ · Docker 24+ · Docker Compose 2.20+ · Make

### Linux / macOS

```bash
# 1. Bootstrap (copies .env, starts docker, installs venv)
cp .env.example .env && ./scripts/bootstrap.sh

# 2. Activate venv
source .venv/bin/activate

# 3. Start API
make api   # or: uvicorn apps.api.app.main:app --reload
```

### Windows (PowerShell)

```powershell
# 1. Bootstrap
Copy-Item .env.example .env -ErrorAction SilentlyContinue; .\scripts\bootstrap.ps1

# 2. Activate venv
.\.venv\Scripts\Activate.ps1

# 3. Start API
make api
```

Then open: <http://localhost:8000/api/v1/health>

---

## Makefile Commands

```bash
# Setup
make venv            # Create virtual environment
make install         # Install app + dev dependencies + pre-commit hooks
make db-up           # Start Postgres 16 + Redis 7

# Run services
make api             # FastAPI dev server (uvicorn with reload)
make worker          # Celery worker (queue: celery)
make worker-execution # Execution worker (queue: execution, concurrency=1)
make beat            # Celery beat scheduler
make run-all         # All services via honcho (includes db-up)
make indexer         # On-chain event indexer

# Database migrations (run after dev-up)
make migrate         # Apply all pending migrations
make revision MSG="description"  # Create new migration
make downgrade       # Roll back one step

# Quality
make lint            # ruff check
make fix             # ruff check --fix
make format          # black format
make type-check      # mypy type check
make test            # pytest (or: pytest tests/path/to/test.py -v)

# Docker
make dev-up           # Start dev stack (postgres, redis, api, workers, monitoring)
make dev-down         # Stop dev stack
make dev-logs         # Tail dev logs

# Production
make prod-up          # Build and start full stack (Docker)
make prod-down        # Stop production stack
make prod-logs        # Tail production logs
```

Run `make help` to see all targets.

---

## Repository Layout

```text
apps/
  api/           FastAPI application (apps/api/app/main.py:app)
    v1/routes/   Route modules: vaults.py, ccip.py, main.py
    limiter.py   Rate limiting via slowapi
  worker/        Celery application
    celery_app.py  Celery instance + beat schedule
    tasks.py      Task definitions: strategy, execution, risk_guard, indexer
  indexer/       On-chain event indexer (apps/indexer/main.py)
libs/
  core/config.py  pydantic-settings (Settings singleton via get_settings())
  chain/         Web3 / contract clients: vault_reader, executor, price_feed
  db/            SQLAlchemy: models.py, session.py, base.py
alembic/         Database migrations (alembic upgrade head)
infra/           docker-compose.yml (Postgres 16, Redis 7, Prometheus, Loki, Grafana, monitoring)
scripts/         Bootstrap helpers
```

---

## Services

| Service | Command | Description |
| ------- | ------- | ----------- |
| API | `make api` | FastAPI dev server (uvicorn with reload) |
| Worker | `make worker` | Celery worker (queue: celery) |
| Execution worker | `make worker-execution` | Single-concurrency execution queue |
| Beat scheduler | `make beat` | Celery beat (runs periodic tasks) |
| Indexer | `make indexer` | On-chain event indexer |
| All services | `make run-all` | Via honcho + Procfile |

---

## API Endpoints

All routes are prefixed with `/api/v1`.

| Endpoint | Description |
| -------- | ----------- |
| `GET /api/v1/health` | Liveness probe — returns `200` if the process is running |
| `GET /api/v1/ready` | Readiness probe — returns `200` if DB is reachable, `503` otherwise |
| `GET /api/v1/vaults` | Vault list (pagination + chain filter) |
| `GET /api/v1/vault/{address}` | Vault detail |
| `GET /api/v1/vault/{address}/history` | Vault event history (type/from/to filters) |
| `GET /api/v1/ccip/config` | CCIP configuration |
| `POST /api/v1/ccip/estimate-fees` | Fee estimation |

### API Behavior Notes

- `GET /api/v1/vault/{address}`
  - `404` when vault is not found
  - `409` when address exists on multiple chains and `chain` query param is not provided
- `GET /api/v1/vault/{address}/history`
  - `404` when vault is not found
  - `422` when invalid date range (`from > to`) or invalid params are provided

---

## Chainlink Integration

| File | Purpose |
| ---- | ------- |
| `libs/core/config.py` | `chainlink_feed_registry_address` config |
| `apps/api/v1/routes/ccip.py` | CCIP config endpoint, fee estimation |
| `libs/chain/price_feed.py` | Price feed reads via `eth_call` |

---

## Strategy Engine

Celery beat runs `worker.strategy.tick` every `STRATEGY_TICK_SECONDS` (default `60`).

For each vault, the strategy worker evaluates latest DB events:

- `TokenRuleSet` payload: `buy_threshold`, `sell_threshold`, `cooldown_seconds`, `last_executed_at`
- `PriceObserved` payload: `price`

If threshold + cooldown checks pass, it enqueues `worker.execution.enqueue` with Redis idempotency lock:

- key format: `strategy:{vault}:{action}:{YYYYMMDDHHMM}`
- lock TTL: 90 seconds

### Celery Beat Schedule

| Task | Interval | Env var |
| ---- | -------- | ------- |
| `strategy-tick` | 60s default | `STRATEGY_TICK_SECONDS` |
| `risk-guard-tick` | 60s default | `RISK_TICK_SECONDS` |
| `indexer-tick` | 10s default | `INDEXER_TICK_SECONDS` |

---

## Risk Guard

`worker.risk_guard.tick` enforces:

- `max_notional_per_trade`
- `max_daily_notional`
- `max_open_positions`

---

## Rate Limiting

Slowapi-based, applied per-IP:

- `RATE_LIMIT_PUBLIC` — 60/min default
- `RATE_LIMIT_HEAVY` — 20/min

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `APP_ENV` | `dev` | Environment name |
| `APP_PORT` | `8000` | API port |
| `POSTGRES_HOST` | `127.0.0.1` | Postgres host |
| `POSTGRES_DB` | `sentient` | Database name |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis DSN (broker + backend) |
| `ETH_RPC_URL` | — | Ethereum JSON-RPC endpoint |
| `DATABASE_URL` | — | Full DSN override (optional) |
| `CHAINLINK_FEED_REGISTRY_ADDRESS` | — | Chainlink Feed Registry (optional) |
| `EXECUTOR_PRIVATE_KEY` | — | Executor wallet private key |
| `EXECUTOR_DRY_RUN` | `false` | If true, simulates via `eth_call` only |
| `BASE_TOKEN_ADDRESS` | — | USDC on Base Sepolia by default |
| `SUBGRAPH_URL` | — | The Graph subgraph URL |
| `SUBGRAPH_API_KEY` | — | The Graph API key |
| `SUBGRAPH_ID` | — | The Graph subgraph ID |
| `CHAIN_BASE_SEPOLIA_ID` | `84532` | Chain ID for subgraph network filtering |

---

## Database Management

```bash
# Connect to database
psql -d sentient

# List tables
sentient=# \dt

# Check active connections
sentient=# SELECT numbackends, datname, usename, state FROM pg_stat_activity;

# Check database size
sentient=# SELECT pg_size_pretty(pg_database_size('sentient'));
```

---

## Troubleshooting

| Symptom | Fix |
| ------- | ---|
| Postgres not reachable | Ensure `make dev-up` ran; check `docker compose ps` |
| Migration fails | Wait ~5s for Postgres to become healthy after `db-up` |
| Redis connection error | Verify `REDIS_URL` in `.env` is correct |
| Strategy tick not running | Check Celery beat is active (`make beat`) and workers are connected |
