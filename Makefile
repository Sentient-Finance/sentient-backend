.PHONY: help venv install install-prod dev lint fix format type-check test db-up db-down migrate revision downgrade indexer indexer-cron worker prod-up prod-down prod-logs setup-hooks

SHELL := bash

VENV_DIR ?= .venv
PORT ?= 8001
MSG ?=
REV ?= -1

# Detect python executable
ifneq ($(wildcard $(VENV_DIR)/Scripts/python.exe),)
    PY := $(VENV_DIR)/Scripts/python.exe
else ifneq ($(wildcard $(VENV_DIR)/bin/python),)
    PY := $(VENV_DIR)/bin/python
else
    PY := python3
endif

PIP := $(PY) -m pip

help:
	@printf "%s\n" \
	"Targets:" \
	"  make venv            Create venv at $(VENV_DIR)" \
	"  make install         Install app + dev dependencies" \
	"  make install-prod    Install runtime dependencies only" \
	"  make dev             Run FastAPI (PORT=$(PORT))" \
	"  make lint            Ruff check" \
	"  make fix             Ruff check --fix" \
	"  make format          Black format" \
	"  make type-check      Mypy type check" \
	"  make test            Pytest" \
	"  make db-up           Start Postgres/Redis (docker compose)" \
	"  make db-down         Stop Postgres/Redis" \
	"  make migrate         Alembic upgrade head" \
	"  make revision MSG=   Create Alembic revision" \
	"  make downgrade REV=  Alembic downgrade (default -1)" \
	"  make indexer         Run indexer (one-shot)" \
	"  make indexer-cron   Run indexer via docker (for system cron)" \
	"  make worker          Run worker module" \
	"  make worker-execution Run execution worker module" \
	"  make beat            Run celery beat" \
	"  make setup-hooks     Install pre-commit hooks"

venv:
	python -m venv "$(VENV_DIR)"
	$(PIP) install -U pip

install:
	$(PIP) install -e ".[dev]"

install-prod:
	$(PIP) install -e .

dev:
	$(PY) -m uvicorn apps.api.app.main:app --reload --reload-dir apps --reload-dir libs --port "$(PORT)"

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

PROD_COMPOSE := docker compose --project-directory . -f infra/docker-compose.yml -f docker-compose.prod.yml
INFRA_COMPOSE := docker compose --project-directory . -f infra/docker-compose.yml

db-up:
	$(INFRA_COMPOSE) up -d

db-down:
	$(INFRA_COMPOSE) down

prod-up:
	$(PROD_COMPOSE) up -d --build

prod-down:
	$(PROD_COMPOSE) down

prod-logs:
	$(PROD_COMPOSE) logs -f

migrate:
	$(PY) -m alembic upgrade head

revision:
	@if [ -z "$(MSG)" ]; then echo "Missing MSG, example: make revision MSG='create users table'"; exit 2; fi
	$(PY) -m alembic revision -m "$(MSG)"

downgrade:
	$(PY) -m alembic downgrade "$(REV)"

indexer:
	$(PY) -m apps.indexer.main -v

# Run indexer as a one-shot via docker (for system cron)
indexer-cron:
	docker compose --project-directory . -f infra/docker-compose.yml -f docker-compose.prod.yml run --rm api python -m apps.indexer.main -v

worker:
	$(PY) -m celery -A apps.worker.celery_app worker -l info -Q celery

worker-execution:
	$(PY) -m celery -A apps.worker.celery_app worker -l info -Q execution --concurrency=1

beat:
	$(PY) -m celery -A apps.worker.celery_app beat -l info

setup-hooks:
	$(PY) -m pre_commit install