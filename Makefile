.PHONY: help venv install install-prod dev lint fix format test db-up db-down migrate revision downgrade indexer worker

SHELL := bash

VENV_DIR ?= .venv
PORT ?= 8000
MSG ?=
REV ?= -1

ifeq ($(wildcard $(VENV_DIR)/Scripts/python.exe),$(VENV_DIR)/Scripts/python.exe)
PY := $(VENV_DIR)/Scripts/python.exe
else
PY := $(VENV_DIR)/bin/python
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
	"  make test            Pytest" \
	"  make db-up           Start Postgres/Redis (docker compose)" \
	"  make db-down         Stop Postgres/Redis" \
	"  make migrate         Alembic upgrade head" \
	"  make revision MSG=   Create Alembic revision" \
	"  make downgrade REV=  Alembic downgrade (default -1)" \
	"  make indexer         Run indexer module" \
	"  make worker          Run worker module"

venv:
	python -m venv "$(VENV_DIR)"
	$(PIP) install -U pip

install:
	$(PIP) install -e ".[dev]"

install-prod:
	$(PIP) install -e .

dev:
	$(PY) -m uvicorn apps.api.app.main:app --reload --port "$(PORT)"

lint:
	$(PY) -m ruff check .

fix:
	$(PY) -m ruff check . --fix

format:
	$(PY) -m black .

test:
	$(PY) -m pytest

db-up:
	docker compose -f infra/docker-compose.yml up -d

db-down:
	docker compose -f infra/docker-compose.yml down

migrate:
	$(PY) -m alembic upgrade head

revision:
	@if [ -z "$(MSG)" ]; then echo "Missing MSG, example: make revision MSG='create users table'"; exit 2; fi
	$(PY) -m alembic revision -m "$(MSG)"

downgrade:
	$(PY) -m alembic downgrade "$(REV)"

indexer:
	$(PY) -m apps.indexer.main

worker:
	$(PY) -m celery -A apps.worker.celery_app worker -l info

beat:
	$(PY) -m celery -A apps.worker.celery_app beat -l info

test:
	$(PY) -m pytest

test-noti:
	$(PY) -c "from apps.worker.tasks import risk_guard_tick; print(risk_guard_tick())"