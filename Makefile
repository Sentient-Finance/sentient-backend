.PHONY: help venv install install-prod api lint fix format type-check test db-up db-down migrate revision downgrade indexer worker worker-execution beat run-all setup-hooks prod-up prod-down prod-logs

SHELL := bash

# --- Variables ---
VENV_DIR ?= .venv
PORT     ?= 8001
MSG      ?=
REV      ?= -1
DOCKER_PROXY_NETWORK ?= sentient-proxy
PORTTAINER_PASSWORD   ?= admin

# Detect python executable
ifneq ($(wildcard $(VENV_DIR)/Scripts/python.exe),)
    PY := $(VENV_DIR)/Scripts/python.exe
else ifneq ($(wildcard $(VENV_DIR)/bin/python),)
    PY := $(VENV_DIR)/bin/python
else
    PY := python3
endif

PIP := $(PY) -m pip

# Detect honcho executable
ifneq ($(wildcard $(VENV_DIR)/Scripts/honcho.exe),)
    HONCHO := $(VENV_DIR)/Scripts/honcho.exe
else ifneq ($(wildcard $(VENV_DIR)/bin/honcho),)
    HONCHO := $(VENV_DIR)/bin/honcho
else
    HONCHO := honcho
endif

# Docker Compose commands
INFRA_COMPOSE := docker compose --project-directory . -f infra/docker-compose.yml
PROD_COMPOSE  := docker compose --project-directory . -f infra/docker-compose.yml -f docker-compose.prod.yml

# --- Help ---
help:
	@printf "%s\n" \
	"Usage: make <target>" \
	"" \
	"Project Setup:" \
	"  venv               Create venv at $(VENV_DIR)" \
	"  install            Install app + dev dependencies" \
	"  install-prod       Install runtime dependencies only" \
	"  setup-hooks        Install pre-commit hooks" \
	"" \
	"Celery Workers (Manual):" \
	"  worker             Run general worker (queue: celery)" \
	"  worker-execution   Run execution worker (queue: execution, concurrency=1)" \
	"  beat               Run celery beat" \
	"" \
	"Local Execution:" \
	"  api                Run FastAPI (PORT=$(PORT))" \
	"  run-all            Run all services (API+Workers+Beat) via honcho (includes db-up)" \
	"  indexer            Run indexer (one-shot, -v for verbose)" \
	"" \
	"Quality & Testing:" \
	"  lint               Ruff check" \
	"  fix                Ruff check --fix" \
	"  format             Black format" \
	"  type-check         Mypy type check" \
	"  test               Pytest" \
	"" \
	"Database & Migrations:" \
	"  db-up              Start Postgres/Redis (docker compose)" \
	"  db-down            Stop Postgres/Redis" \
	"  migrate            Alembic upgrade head" \
	"  revision MSG=      Create Alembic revision" \
	"  downgrade REV=     Alembic downgrade (default -1)" \
	"" \
	"Production (Docker):" \
	"  prod-up            Build and start full stack in production mode" \
	"  prod-down          Stop production stack" \
	"  prod-logs          Tail production logs"

# --- Project Setup ---
venv:
	python -m venv "$(VENV_DIR)"
	$(PIP) install -U pip

install:
	$(PIP) install -e ".[dev]"
	$(PY) -m pre_commit install

install-prod:
	$(PIP) install -e .

setup-hooks:
	$(PY) -m pre_commit install

# --- Database & Migrations ---
db-up:
	$(INFRA_COMPOSE) up -d

db-down:
	$(INFRA_COMPOSE) down

migrate:
	$(PY) -m alembic upgrade head

revision:
	@if [ -z "$(MSG)" ]; then echo "Missing MSG, example: make revision MSG='create users table'"; exit 2; fi
	$(PY) -m alembic revision -m "$(MSG)"

downgrade:
	$(PY) -m alembic downgrade "$(REV)"

# --- Celery Workers (Manual) ---
worker:
	$(PY) -m celery -A apps.worker.celery_app worker -l info -Q celery

worker-execution:
	$(PY) -m celery -A apps.worker.celery_app worker -l info -Q execution --concurrency=1

beat:
	$(PY) -m celery -A apps.worker.celery_app beat -l info

# --- Local Execution ---
api:
	$(PY) -m uvicorn apps.api.app.main:app --reload --reload-dir apps --reload-dir libs --port "$(PORT)"

run-all: db-up
	@if ! command -v $(HONCHO) >/dev/null 2>&1; then \
		echo "Error: '$(HONCHO)' not found. Install it with: $(PIP) install honcho"; \
		exit 1; \
	fi
	@export PATH="$(PWD)/$(VENV_DIR)/bin:$$PATH"; $(HONCHO) start

indexer:
	$(PY) -m apps.indexer.main -v

# --- Quality & Testing ---
lint:
	$(PY) -m ruff check .

fix:
	$(PY) -m ruff check . --fix

format:
	$(PY) -m black .

check-format:
	$(PY) -m black --check .

type-check:
	$(PY) -m mypy apps libs

test:
	$(PY) -m pytest


# --- Production (Docker) ---
setup-proxy:
	@docker network inspect $(DOCKER_PROXY_NETWORK) >/dev/null 2>&1 || docker network create $(DOCKER_PROXY_NETWORK)
	@mkdir -p infra/letsencrypt
	@touch infra/letsencrypt/acme.json
	@chmod 600 infra/letsencrypt/acme.json
	@if [ ! -f infra/letsencrypt/htpasswd ]; then \
		echo "admin:$$(openssl passwd -apr1 $(PORTTAINER_PASSWORD))" > infra/letsencrypt/htpasswd; \
		chmod 600 infra/letsencrypt/htpasswd; \
		echo "Created htpasswd for Portainer auth"; \
	fi

prod-up: setup-proxy
	$(PROD_COMPOSE) up -d --build

prod-down:
	$(PROD_COMPOSE) down

prod-logs:
	$(PROD_COMPOSE) logs -f
