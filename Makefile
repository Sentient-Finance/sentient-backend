.PHONY: help venv install install-prod api lint fix format type-check test migrate revision downgrade worker worker-execution beat run-all setup-hooks prod-up prod-down prod-logs dev-up dev-down dev-logs

SHELL := bash

-include .env

# --- Variables ---
VENV_DIR ?= .venv
PORT     ?= 8000
MSG      ?=
REV      ?= -1

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
DEV_COMPOSE  := docker compose --env-file .env --project-directory . -f docker-compose.yml
PROD_COMPOSE := docker compose --env-file .env --project-directory . -f docker-compose.yml -f docker-compose.prod.yml

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
	"  run-all            Run all services (API+Workers+Beat) via honcho" \
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
	"  migrate            Alembic upgrade head" \
	"  revision MSG=      Create Alembic revision" \
	"  downgrade REV=     Alembic downgrade (default -1)" \
	"" \
	"Production (Docker):" \
	"  prod-up            Build and start full stack (API + workers on npm_network)" \
	"  prod-down          Stop production stack" \
	"  prod-logs          Tail production logs" \
	"" \
	"Development (Docker):" \
	"  dev-up             Start all dev containers (postgres, redis, api, workers, monitoring)" \
	"  dev-down           Stop dev stack" \
	"  dev-logs           Tail dev logs"

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

run-all:
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
prod-up:
	$(PROD_COMPOSE) up -d --build

prod-down:
	$(PROD_COMPOSE) down

prod-logs:
	$(PROD_COMPOSE) logs -f

# --- Development (Docker) ---
dev-up:
	$(DEV_COMPOSE) up -d

dev-down:
	$(DEV_COMPOSE) down

dev-logs:
	$(DEV_COMPOSE) logs -f
