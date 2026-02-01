# Makefile - DTC DE Module 01 (Docker + Postgres + Ingestion CLI)
# Reads defaults from .env (if present), but can still be overridden via CLI:
#   make docker.exec.ingest TAXI=green YEAR=2021 MONTH=03

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ------------------------------------------------------------------------------
# Load .env (if exists)
# ------------------------------------------------------------------------------
ENV_FILE ?= .env
ifneq (,$(wildcard $(ENV_FILE)))
  include $(ENV_FILE)
endif

# ------------------------------------------------------------------------------
# Config (override via: make VAR=value <target>)
# ------------------------------------------------------------------------------
PYTHON ?= python
UV ?= uv

COMPOSE ?= docker compose
APP_SERVICE ?= app
DB_SERVICE ?= db

# Default ingest params (pulled from .env when available)
TAXI ?= yellow
YEAR ?= 2024
MONTH ?= 01
FILE_FORMAT ?= parquet
IF_EXISTS ?= replace
KEEP_LOCAL ?= true

# For ingest-url
DATA_URL ?=

# ------------------------------------------------------------------------------
# Help
# ------------------------------------------------------------------------------
.PHONY: help
help: ## Show available commands
	@awk 'BEGIN {FS=":.*##"; printf "\n\033[1mDTC Module 01 - Makefile Commands\033[0m\n\n"} \
	/^[a-zA-Z0-9_.-]+:.*##/ {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2} \
	END {printf "\nExamples:\n" \
	"  make local.sync\n" \
	"  make local.ingest TAXI=yellow YEAR=2024 MONTH=01 FILE_FORMAT=parquet\n" \
	"  make docker.up\n" \
	"  make docker.exec.ingest TAXI=green YEAR=2021 MONTH=03\n" \
	"  make docker.run.ingest TAXI=yellow YEAR=2021 MONTH=04\n\n"}' $(MAKEFILE_LIST)

# ------------------------------------------------------------------------------
# Local (outside Docker) - run main.py on host using uv
# ------------------------------------------------------------------------------
.PHONY: local.sync
local.sync: ## Install deps locally using uv
	$(UV) sync

.PHONY: local.help
local.help: ## Show CLI help (local)
	$(UV) run $(PYTHON) main.py --help

.PHONY: local.ingest
local.ingest: ## Run ingestion locally (outside Docker)
	@echo "LOCAL ingest: TAXI=$(TAXI) YEAR=$(YEAR) MONTH=$(MONTH) FORMAT=$(FILE_FORMAT) IF_EXISTS=$(IF_EXISTS) KEEP_LOCAL=$(KEEP_LOCAL)"
	$(UV) run $(PYTHON) main.py ingest \
		--taxi $(TAXI) \
		--year $(YEAR) \
		--month $(MONTH) \
		--file-format $(FILE_FORMAT) \
		--if-exists $(IF_EXISTS) \
		--keep-local=$(KEEP_LOCAL)

.PHONY: local.ingest-url
local.ingest-url: ## Run ingestion locally from arbitrary URL (DATA_URL required)
	@if [ -z "$(DATA_URL)" ]; then echo "ERROR: DATA_URL is required. Example: make local.ingest-url DATA_URL=https://..."; exit 1; fi
	@echo "LOCAL ingest-url: DATA_URL=$(DATA_URL) IF_EXISTS=$(IF_EXISTS) KEEP_LOCAL=$(KEEP_LOCAL)"
	$(UV) run $(PYTHON) main.py ingest-url \
		--url "$(DATA_URL)" \
		--if-exists $(IF_EXISTS) \
		--keep-local=$(KEEP_LOCAL)

# ------------------------------------------------------------------------------
# Docker Compose lifecycle
# ------------------------------------------------------------------------------
.PHONY: docker.build
docker.build: ## Build docker images
	$(COMPOSE) build

.PHONY: docker.up
docker.up: ## Start services (db + app) in background
	$(COMPOSE) up -d

.PHONY: docker.down
docker.down: ## Stop services
	$(COMPOSE) down

.PHONY: docker.ps
docker.ps: ## Show container status
	$(COMPOSE) ps

.PHONY: docker.logs
docker.logs: ## Tail logs
	$(COMPOSE) logs -f

# ------------------------------------------------------------------------------
# DB only
# ------------------------------------------------------------------------------
.PHONY: docker.db.up
docker.db.up: ## Start Postgres only (db service)
	$(COMPOSE) up -d $(DB_SERVICE)

.PHONY: docker.db.down
docker.db.down: ## Stop Postgres only (db service)
	$(COMPOSE) stop $(DB_SERVICE)

.PHONY: docker.db.restart
docker.db.restart: ## Restart Postgres only (db service)
	$(COMPOSE) restart $(DB_SERVICE)

# ------------------------------------------------------------------------------
# Inside Docker - run main.py
# ------------------------------------------------------------------------------
.PHONY: docker.run.ingest
docker.run.ingest: ## One-off run in a new container (no need docker.up)
	@echo "DOCKER run ingest: TAXI=$(TAXI) YEAR=$(YEAR) MONTH=$(MONTH) FORMAT=$(FILE_FORMAT) IF_EXISTS=$(IF_EXISTS) KEEP_LOCAL=$(KEEP_LOCAL)"
	$(COMPOSE) run --rm $(APP_SERVICE) $(PYTHON) main.py ingest \
		--taxi $(TAXI) \
		--year $(YEAR) \
		--month $(MONTH) \
		--file-format $(FILE_FORMAT) \
		--if-exists $(IF_EXISTS) \
		--keep-local=$(KEEP_LOCAL)

.PHONY: docker.run.ingest-url
docker.run.ingest-url: ## One-off ingest-url in a new container (DATA_URL required)
	@if [ -z "$(DATA_URL)" ]; then echo "ERROR: DATA_URL is required. Example: make docker.run.ingest-url DATA_URL=https://..."; exit 1; fi
	@echo "DOCKER run ingest-url: DATA_URL=$(DATA_URL) IF_EXISTS=$(IF_EXISTS) KEEP_LOCAL=$(KEEP_LOCAL)"
	$(COMPOSE) run --rm $(APP_SERVICE) $(PYTHON) main.py ingest-url \
		--url "$(DATA_URL)" \
		--if-exists $(IF_EXISTS) \
		--keep-local=$(KEEP_LOCAL)

.PHONY: docker.exec.ingest
docker.exec.ingest: ## Run ingestion inside the already-running app container (requires docker.up)
	@echo "DOCKER exec ingest: TAXI=$(TAXI) YEAR=$(YEAR) MONTH=$(MONTH) FORMAT=$(FILE_FORMAT) IF_EXISTS=$(IF_EXISTS) KEEP_LOCAL=$(KEEP_LOCAL)"
	$(COMPOSE) exec $(APP_SERVICE) $(PYTHON) main.py ingest \
		--taxi $(TAXI) \
		--year $(YEAR) \
		--month $(MONTH) \
		--file-format $(FILE_FORMAT) \
		--if-exists $(IF_EXISTS) \
		--keep-local=$(KEEP_LOCAL)

.PHONY: docker.exec.ingest-url
docker.exec.ingest-url: ## Run ingest-url inside the running app container (DATA_URL required)
	@if [ -z "$(DATA_URL)" ]; then echo "ERROR: DATA_URL is required. Example: make docker.exec.ingest-url DATA_URL=https://..."; exit 1; fi
	@echo "DOCKER exec ingest-url: DATA_URL=$(DATA_URL) IF_EXISTS=$(IF_EXISTS) KEEP_LOCAL=$(KEEP_LOCAL)"
	$(COMPOSE) exec $(APP_SERVICE) $(PYTHON) main.py ingest-url \
		--url "$(DATA_URL)" \
		--if-exists $(IF_EXISTS) \
		--keep-local=$(KEEP_LOCAL)

# ------------------------------------------------------------------------------
# Convenience shells
# ------------------------------------------------------------------------------
.PHONY: app.shell
app.shell: ## Shell into running app container
	$(COMPOSE) exec $(APP_SERVICE) bash

.PHONY: db.shell
db.shell: ## Shell into db container
	$(COMPOSE) exec $(DB_SERVICE) bash

.PHONY: db.psql
db.psql: ## Open psql inside db container (uses env from container)
	$(COMPOSE) exec $(DB_SERVICE) psql -U $$POSTGRES_USER -d $$POSTGRES_DB

# ------------------------------------------------------------------------------
# Quality (local)
# ------------------------------------------------------------------------------
.PHONY: lint
lint: ## Lint (ruff)
	$(UV) run ruff check .

.PHONY: format
format: ## Format (ruff format)
	$(UV) run ruff format .

.PHONY: typecheck
typecheck: ## Type check (mypy)
	$(UV) run mypy .

.PHONY: test
test: ## Run tests (pytest)
	$(UV) run pytest

# ------------------------------------------------------------------------------
# Dangerous cleanup (reset everything)
# ------------------------------------------------------------------------------
.PHONY: clean.data
clean.data: ## Delete ALL downloaded files in ./data (local folder)
	@echo "Deleting ./data contents..."
	@rm -rf ./data/*
	@echo "OK"

.PHONY: clean.logs
clean.logs: ## Delete ALL logs in ./logs (local folder)
	@echo "Deleting ./logs contents..."
	@rm -rf ./logs/*
	@echo "OK"

clean.py: ## Delete local python artifacts (caches, bytecode, coverage, etc.)
	@echo "Cleaning python artifacts..."
	@rm -rf \
		__pycache__ \
		.pytest_cache \
		.mypy_cache \
		.ruff_cache \
		.coverage \
		coverage.xml \
		htmlcov
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) -delete 2>/dev/null || true
	@ echo "DONE!"

.PHONY: clean.all
clean.all: clean.data clean.logs clean.py ## Delete ./data/* and ./logs/*
	@echo "Local folders cleaned: data/, logs/, and python artifacts"

.PHONY: docker.nuke
docker.nuke: ## Stop stack and REMOVE volumes (DANGEROUS: wipes Postgres data)
	@echo "Stopping stack and removing volumes..."
	$(COMPOSE) down -v --remove-orphans
	@echo "Docker volumes removed (Postgres data wiped)."

.PHONY: reset.all
reset.all: ## Full reset: remove volumes + delete ./data/* + ./logs/* (DANGEROUS)
	@echo "============================================================"
	@echo "⚠️  WARNING: FULL RESET will permanently delete:"
	@echo "   - Docker volumes (Postgres data will be wiped)"
	@echo "   - ./data/*  (downloaded files)"
	@echo "   - ./logs/*  (application logs)"
	@echo "------------------------------------------------------------"
	@echo "To proceed, run:"
	@echo "  make reset.all CONFIRM=YES"
	@echo "============================================================"
	@if [ "$(CONFIRM)" != "YES" ]; then \
		echo "Aborted. (Set CONFIRM=YES to continue)"; \
		exit 1; \
	fi
	@$(MAKE) docker.nuke
	@$(MAKE) clean.all
	@echo "✅ FULL RESET completed."
