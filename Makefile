.PHONY: help venv install install-prod dev lint fix format test db-up db-down migrate revision autogen downgrade indexer indexer-once worker

SHELL := bash

VENV_DIR ?= .venv
PORT ?= 8000
m ?=
REV ?= -1

PY := $(VENV_DIR)/bin/python3

PIP := $(PY) -m pip

help:
	@printf "%s\n" \
	"Targets:" \
	"  make venv              Create venv at $(VENV_DIR)" \
	"  make install           Install app + dev dependencies" \
	"  make install-prod      Install runtime dependencies only" \
	"  make dev               Run FastAPI (PORT=$(PORT))" \
	"  make lint              Ruff check" \
	"  make fix               Ruff check --fix" \
	"  make format            Black format" \
	"  make test              Pytest" \
	"  make db-up             Start Postgres/Redis (docker compose)" \
	"  make db-down           Stop Postgres/Redis" \
	"  make migrate           Alembic upgrade head" \
	"  make revision m=       Create Alembic revision" \
	"  make autogen [m=]      Autogenerate Alembic revision (m optional)" \
	"  make downgrade REV=    Alembic downgrade (default -1)" \
	"  make indexer           Run indexer (poll loop)" \
	"  make indexer-once      Run indexer (single pass, then exit)" \
	"  make worker            Run Celery worker"

venv:
	python3 -m venv "$(VENV_DIR)"
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
	@if [ -z "$(m)" ]; then echo "Missing m, example: make revision m='create users table'"; exit 2; fi
	$(PY) -m alembic revision -m "$(m)"

autogen:
	$(eval _m := $(if $(m),$(m),auto_$(shell date +%Y%m%d_%H%M%S)))
	$(PY) -m alembic revision --autogenerate -m "$(_m)"

downgrade:
	$(PY) -m alembic downgrade "$(REV)"

indexer:
	$(PY) -m apps.indexer.main

indexer-once:
	$(PY) -m apps.indexer.main --once

worker:
	$(PY) -m celery -A apps.worker.celery_app.celery_app worker --loglevel=info
