# Single entry point for local development and CI. Run `make` (or `make help`) for the list.
# Targets Linux and macOS (GNU Make 3.81+, the version macOS ships); on Windows use WSL.

SHELL := /bin/sh
.DEFAULT_GOAL := help

# ---- Overridable commands and paths -------------------------------------------------------
COMPOSE      ?= docker compose
E2E_PROJECT  ?= trello-e2e
COMPOSE_E2E  ?= docker compose -p $(E2E_PROJECT) -f docker-compose.yml -f docker-compose.e2e.yml
BACKEND_DIR  ?= backend
FRONTEND_DIR ?= frontend
E2E_DIR      ?= e2e
UV           ?= uv
NPM          ?= npm

# Reads KEY from .env (empty if the file or the key is missing).
env_get = $(shell [ -f .env ] && sed -n 's/^$(1)=//p' .env | tail -n 1)

API_PORT         ?= $(or $(call env_get,API_PORT),8000)
FRONTEND_PORT    ?= $(or $(call env_get,FRONTEND_PORT),8080)
TEST_POSTGRES_DB ?= $(or $(call env_get,TEST_POSTGRES_DB),kanban_test)
E2E_PORT         ?= 8081
API_URL          ?= http://localhost:$(API_PORT)
FRONTEND_URL     ?= http://localhost:$(FRONTEND_PORT)
VITE_PORT        ?= 5173
VITE_URL         ?= http://localhost:$(VITE_PORT)
HEALTH_TIMEOUT   ?= 120

# Extra flags, mostly for CI (e.g. RUFF_ARGS=--output-format=github PYTEST_ARGS=--cov-report=xml).
RUFF_ARGS   ?=
PYTEST_ARGS ?=
NPM_CI_ARGS ?= --no-audit --no-fund
args        ?=

# Pinned tool versions (kept in step with .github/workflows/ci.yml).
PIP_AUDIT_VERSION ?= 2.10.1
BANDIT_VERSION    ?= 1.9.4
GITLEAKS_VERSION  ?= 8.30.1
TRIVY_VERSION     ?= v0.76.2
GITLEAKS          ?= gitleaks
TRIVY             ?= trivy
GITLEAKS_IMAGE    ?= zricethezav/gitleaks:v$(GITLEAKS_VERSION)
TRIVY_IMAGE       ?= aquasec/trivy:$(TRIVY_VERSION:v%=%)
TRIVY_FLAGS       := --severity HIGH,CRITICAL --ignore-unfixed --ignorefile .trivyignore --exit-code 1

# ---- Helpers ------------------------------------------------------------------------------
# $(call require,<binary>,<hint>): fail fast when a tool is missing.
require = command -v $(1) >/dev/null 2>&1 || { echo "Error: '$(1)' is required but was not found. $(2)" >&2; exit 1; }

# $(call confirm,<message>): ask before destructive work unless CONFIRM=yes; never hang without a TTY.
confirm = if [ "$(CONFIRM)" != "yes" ]; then \
	  if [ -t 0 ]; then \
	    printf '%s\nType "yes" to continue: ' "$(1)"; read answer; \
	    [ "$$answer" = "yes" ] || { echo "Aborted."; exit 1; }; \
	  else \
	    echo "$(1)" >&2; echo "No terminal to confirm. Re-run with CONFIRM=yes." >&2; exit 1; \
	  fi; \
	fi

# $(call wait_for,<url>): poll until the URL answers, up to HEALTH_TIMEOUT seconds.
wait_for = echo "Waiting for $(1) ..."; elapsed=0; \
	until curl -fsS "$(1)" >/dev/null 2>&1; do \
	  if [ $$elapsed -ge $(HEALTH_TIMEOUT) ]; then \
	    echo "Error: $(1) did not respond within $(HEALTH_TIMEOUT)s." >&2; \
	    $(COMPOSE) ps >&2; $(COMPOSE) logs --tail=50 api >&2; exit 1; \
	  fi; \
	  sleep 2; elapsed=$$((elapsed + 2)); \
	done

# $(call prefix,<label>): prefix every output line, unbuffered (portable across GNU and BSD awk).
prefix = 2>&1 | awk '{ print "$(1) " $$0; fflush() }'

# Start db + redis locally, except in CI where the job provides service containers.
LOCAL_SERVICES := $(if $(CI),,services)

.PHONY: help require-docker require-uv require-node require-env \
	install install-backend install-frontend install-e2e env \
	dev dev-backend dev-frontend dev-worker services \
	up down restart build ps logs shell db-shell \
	migrate migration downgrade seed reset-db migrations-check \
	test test-backend test-frontend test-e2e test-e2e-ui coverage coverage-frontend e2e-report \
	lint lint-backend lint-frontend lint-e2e \
	format format-backend format-frontend format-e2e \
	format-check format-check-backend format-check-frontend format-check-e2e \
	typecheck typecheck-backend typecheck-frontend typecheck-e2e \
	build-frontend gen-api api-drift \
	security audit-python audit-node bandit secrets scan-images scan-image pre-commit \
	check ci clean clean-all

##@ Help

help: ## Show this help
	@awk 'BEGIN { FS = ":.*## "; print "Usage: make <target> [VAR=value]" } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
		/^[a-zA-Z0-9_-]+:.*## / { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

require-docker:
	@$(call require,docker,Install Docker: https://docs.docker.com/get-docker/)
	@docker info >/dev/null 2>&1 || { echo "Error: Docker is installed but the daemon is not running." >&2; exit 1; }

require-uv:
	@$(call require,$(UV),Install uv: https://docs.astral.sh/uv/getting-started/installation/)

require-node:
	@$(call require,node,Install Node 22: https://nodejs.org/ (see frontend/.nvmrc))
	@$(call require,$(NPM),npm ships with Node.)

require-env:
	@[ -f .env ] || { echo "Error: .env not found. Run 'make env' first." >&2; exit 1; }

##@ Setup

install: install-backend install-frontend install-e2e ## Install all dependencies, Playwright browsers and pre-commit hooks
	cd $(E2E_DIR) && npx playwright install chromium
	$(UV) run --project $(BACKEND_DIR) pre-commit install

install-backend: require-uv ## Install backend dependencies (uv sync)
	cd $(BACKEND_DIR) && $(UV) sync --frozen

install-frontend: require-node ## Install frontend dependencies (npm ci)
	cd $(FRONTEND_DIR) && $(NPM) ci $(NPM_CI_ARGS)

install-e2e: require-node ## Install e2e dependencies (npm ci)
	cd $(E2E_DIR) && $(NPM) ci $(NPM_CI_ARGS)

env: ## Create .env from .env.example (never overwrites)
	@if [ -f .env ]; then echo ".env already exists; left unchanged."; \
	else cp .env.example .env && echo "Created .env from .env.example. Review JWT_SECRET and POSTGRES_PASSWORD."; fi

##@ Run locally (app on the host, db and redis in Docker)

dev: require-uv require-node services migrate ## Run the API, Celery worker and Vite together (Ctrl+C stops all)
	@echo "API: $(API_URL)/api/v1/docs   Web: $(VITE_URL)   (Ctrl+C stops everything)"
	@trap 'trap - INT TERM EXIT; kill 0 2>/dev/null' INT TERM EXIT; \
	( cd $(BACKEND_DIR) && $(UV) run uvicorn app.main:app --reload --port $(API_PORT) $(call prefix,[api]); kill 0 ) & \
	( cd $(BACKEND_DIR) && $(UV) run celery -A app.infrastructure.celery_app worker --loglevel=INFO $(call prefix,[worker]); kill 0 ) & \
	( cd $(FRONTEND_DIR) && VITE_PROXY_TARGET=$(API_URL) $(NPM) run dev -- --port $(VITE_PORT) --strictPort $(call prefix,[web]); kill 0 ) & \
	wait

dev-backend: require-uv services migrate ## Run only the API with auto-reload
	cd $(BACKEND_DIR) && $(UV) run uvicorn app.main:app --reload --port $(API_PORT)

dev-worker: require-uv services ## Run only the Celery worker (beat runs only in the Docker stack)
	cd $(BACKEND_DIR) && $(UV) run celery -A app.infrastructure.celery_app worker --loglevel=INFO

dev-frontend: require-node ## Run only the Vite dev server (proxies /api to API_URL)
	cd $(FRONTEND_DIR) && VITE_PROXY_TARGET=$(API_URL) $(NPM) run dev -- --port $(VITE_PORT) --strictPort

services: require-docker require-env ## Start only the db and redis containers and wait until healthy
	$(COMPOSE) up -d --wait db redis

##@ Docker (full stack)

up: require-docker require-env ## Build and start the stack (or one: service=frontend), wait for health, print URLs
	$(COMPOSE) up -d --build $(if $(service),--no-deps $(service))
	@$(call wait_for,$(FRONTEND_URL)/api/v1/health)
	@echo ""
	@echo "Stack is up."
	@echo "  Web app:  $(FRONTEND_URL)"
	@echo "  API docs: $(API_URL)/api/v1/docs"
	@if [ "$(call env_get,SEED_DEMO_DATA)" = "true" ]; then \
	  echo "  Demo logins: alice@example.com, bob@example.com, carol@example.com"; \
	  echo "  Password:    $(call env_get,DEMO_USER_PASSWORD)"; \
	else echo "  No demo users: SEED_DEMO_DATA is not 'true' in .env."; fi

down: require-docker ## Stop and remove the stack's containers (keeps volumes)
	$(COMPOSE) down

restart: down up ## Restart the full stack

build: require-docker require-env ## Build the Docker images (or one: service=api)
	$(COMPOSE) build $(service)

ps: require-docker ## List the stack's containers
	$(COMPOSE) ps

logs: require-docker ## Follow logs (all services, or service=api)
	$(COMPOSE) logs -f --tail=100 $(service)

shell: require-docker ## Open a shell in the api container
	$(COMPOSE) exec api sh

db-shell: require-docker ## Open psql in the db container
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

##@ Database (runs on the host against the db container)

migrate: require-uv $(LOCAL_SERVICES) ## Apply all migrations (alembic upgrade head)
	cd $(BACKEND_DIR) && $(UV) run alembic upgrade head

migration: require-uv ## Autogenerate a migration: make migration name="add due date index"
	@[ -n "$(name)" ] || { echo 'Usage: make migration name="short description"' >&2; exit 1; }
	@$(MAKE) --no-print-directory $(LOCAL_SERVICES) migrate
	cd $(BACKEND_DIR) && $(UV) run alembic revision --autogenerate -m "$(name)"

downgrade: require-uv $(LOCAL_SERVICES) ## Roll back the last migration
	cd $(BACKEND_DIR) && $(UV) run alembic downgrade -1

seed: require-uv $(LOCAL_SERVICES) ## Load demo data (idempotent; needs SEED_DEMO_DATA=true)
	cd $(BACKEND_DIR) && $(UV) run python -m app.infrastructure.seed

reset-db: require-docker require-uv services ## Drop and recreate the dev database, migrate and seed (asks first)
	@$(call confirm,This deletes ALL data in the dev database.)
	$(COMPOSE) exec -T db sh -c 'dropdb --force --if-exists -U "$$POSTGRES_USER" "$$POSTGRES_DB" && createdb -U "$$POSTGRES_USER" "$$POSTGRES_DB"'
	@$(MAKE) --no-print-directory migrate seed

migrations-check: require-uv $(LOCAL_SERVICES) ## On the test DB: upgrade, check for drift, downgrade to base, upgrade
	cd $(BACKEND_DIR) && export POSTGRES_DB=$(TEST_POSTGRES_DB) && \
	  $(UV) run alembic upgrade head && \
	  $(UV) run alembic check && \
	  $(UV) run alembic downgrade base && \
	  $(UV) run alembic upgrade head

##@ Testing

test: test-backend test-frontend ## Run backend and frontend unit/integration tests

test-backend: require-uv $(LOCAL_SERVICES) ## Run backend tests (pytest, fails under 80% coverage)
	cd $(BACKEND_DIR) && $(UV) run pytest $(PYTEST_ARGS)

test-frontend: require-node ## Run frontend tests (Vitest)
	cd $(FRONTEND_DIR) && $(NPM) run test

test-e2e: require-docker require-node ## Run Playwright against an isolated stack, torn down afterwards (args="...")
	E2E_PROJECT=$(E2E_PROJECT) E2E_PORT=$(E2E_PORT) HEALTH_TIMEOUT=$(HEALTH_TIMEOUT) ./$(E2E_DIR)/run.sh $(args)

test-e2e-ui: require-docker require-node ## Run Playwright in UI mode against the e2e stack
	E2E_PROJECT=$(E2E_PROJECT) E2E_PORT=$(E2E_PORT) HEALTH_TIMEOUT=$(HEALTH_TIMEOUT) ./$(E2E_DIR)/run.sh --ui $(args)

coverage: require-uv $(LOCAL_SERVICES) ## Backend coverage with an HTML report
	cd $(BACKEND_DIR) && $(UV) run pytest --cov-report=html $(PYTEST_ARGS)
	@echo "Coverage report: file://$(CURDIR)/$(BACKEND_DIR)/htmlcov/index.html"

coverage-frontend: require-node ## Frontend coverage (fails under 80%) with an HTML report
	cd $(FRONTEND_DIR) && $(NPM) run coverage
	@echo "Coverage report: file://$(CURDIR)/$(FRONTEND_DIR)/coverage/index.html"

e2e-report: require-node ## Open the last Playwright HTML report
	cd $(E2E_DIR) && npx playwright show-report

##@ Quality and security

lint: lint-backend lint-frontend lint-e2e ## Lint everything (ruff check, ESLint)

lint-backend: require-uv ## ruff check
	cd $(BACKEND_DIR) && $(UV) run ruff check $(RUFF_ARGS)

lint-frontend: require-node ## ESLint (frontend)
	cd $(FRONTEND_DIR) && $(NPM) run lint

lint-e2e: require-node ## ESLint (e2e)
	cd $(E2E_DIR) && $(NPM) run lint

format: format-backend format-frontend format-e2e ## Format everything (ruff format, Prettier --write)

format-backend: require-uv ## ruff format
	cd $(BACKEND_DIR) && $(UV) run ruff format

format-frontend: require-node ## Prettier --write (frontend)
	cd $(FRONTEND_DIR) && $(NPM) run format

format-e2e: require-node ## Prettier --write (e2e)
	cd $(E2E_DIR) && $(NPM) run format

format-check: format-check-backend format-check-frontend format-check-e2e ## Check formatting without writing

format-check-backend: require-uv ## ruff format --check
	cd $(BACKEND_DIR) && $(UV) run ruff format --check

format-check-frontend: require-node ## Prettier --check (frontend)
	cd $(FRONTEND_DIR) && $(NPM) run format:check

format-check-e2e: require-node ## Prettier --check (e2e)
	cd $(E2E_DIR) && $(NPM) run format:check

typecheck: typecheck-backend typecheck-frontend typecheck-e2e ## Type-check everything (mypy, tsc --noEmit)

typecheck-backend: require-uv ## mypy
	cd $(BACKEND_DIR) && $(UV) run mypy

typecheck-frontend: require-node ## tsc --noEmit (frontend)
	cd $(FRONTEND_DIR) && $(NPM) run typecheck

typecheck-e2e: require-node ## tsc --noEmit (e2e)
	cd $(E2E_DIR) && $(NPM) run typecheck

build-frontend: require-node ## Production build of the SPA (vite build)
	cd $(FRONTEND_DIR) && $(NPM) run build

gen-api: require-uv require-node ## Regenerate frontend API types from the app's OpenAPI schema (no server needed)
	@tmp=$$(mktemp -d) && trap 'rm -rf "$$tmp"' EXIT && \
	( cd $(BACKEND_DIR) && $(UV) run python -c 'import json; from app.main import app; print(json.dumps(app.openapi()))' > "$$tmp/openapi.json" ) && \
	( cd $(FRONTEND_DIR) && OPENAPI_URL="$$tmp/openapi.json" $(NPM) run gen:api )

api-drift: gen-api ## Fail if the committed frontend API types are out of date
	@git diff --exit-code -- $(FRONTEND_DIR)/src/api/schema.d.ts || { \
	  echo "$(if $(GITHUB_ACTIONS),::error file=$(FRONTEND_DIR)/src/api/schema.d.ts::)API types are out of date. Run 'make gen-api' and commit the result." >&2; \
	  exit 1; }

security: audit-python audit-node bandit secrets ## Dependency audits, Bandit and gitleaks

audit-python: require-uv ## pip-audit the backend lockfile (all groups)
	@tmp=$$(mktemp -d) && trap 'rm -rf "$$tmp"' EXIT && \
	cd $(BACKEND_DIR) && \
	$(UV) export --frozen --all-groups --no-emit-project --format requirements-txt -o "$$tmp/requirements.txt" >/dev/null && \
	$(UV) tool run "pip-audit==$(PIP_AUDIT_VERSION)" --strict --disable-pip --require-hashes -r "$$tmp/requirements.txt"

audit-node: require-node ## npm audit (high and above) for the frontend and e2e packages
	cd $(FRONTEND_DIR) && $(NPM) audit --audit-level=high
	cd $(E2E_DIR) && $(NPM) audit --audit-level=high

bandit: require-uv ## Bandit static analysis of backend/app (medium severity and above)
	cd $(BACKEND_DIR) && $(UV) tool run "bandit==$(BANDIT_VERSION)" -r app --severity-level medium -q

secrets: ## Scan the git history for secrets with gitleaks (local binary, else Docker)
	@if command -v $(GITLEAKS) >/dev/null 2>&1; then \
	  $(GITLEAKS) git --config .gitleaks.toml --redact --verbose --no-banner .; \
	else \
	  $(call require,docker,Install gitleaks or Docker.); \
	  echo "gitleaks not found; using $(GITLEAKS_IMAGE)"; \
	  docker run --rm -v "$(CURDIR):/repo" $(GITLEAKS_IMAGE) \
	    git --config /repo/.gitleaks.toml --redact --verbose --no-banner /repo; \
	fi

scan-images: require-docker ## Build the backend and frontend images and scan them with Trivy
	@status=0; for image in backend frontend; do \
	  docker build -q -t kanban-$$image:local $$image >/dev/null || exit 1; \
	  $(MAKE) --no-print-directory scan-image IMAGE=kanban-$$image:local || status=1; \
	done; exit $$status

scan-image: ## Scan one image with Trivy: make scan-image IMAGE=name:tag
	@[ -n "$(IMAGE)" ] || { echo "Usage: make scan-image IMAGE=name:tag" >&2; exit 1; }
	@if command -v $(TRIVY) >/dev/null 2>&1; then \
	  $(TRIVY) image $(TRIVY_FLAGS) $(IMAGE); \
	else \
	  echo "trivy not found; using $(TRIVY_IMAGE)"; \
	  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
	    -v "$(CURDIR)/.trivyignore:/.trivyignore:ro" -v trello-light-trivy-cache:/root/.cache \
	    $(TRIVY_IMAGE) image $(subst .trivyignore,/.trivyignore,$(TRIVY_FLAGS)) $(IMAGE); \
	fi

pre-commit: require-uv ## Run every pre-commit hook on all files
	$(UV) run --project $(BACKEND_DIR) --frozen pre-commit run --all-files --show-diff-on-failure

##@ Aggregate

check: format-check lint typecheck test ## Fast pre-push check: formatting, lint, types, tests

ci: ## Everything CI runs, in the same order (quality, tests, security, e2e)
	@$(MAKE) --no-print-directory lint-backend format-check-backend typecheck-backend
	@$(MAKE) --no-print-directory test-backend
	@$(MAKE) --no-print-directory migrations-check
	@$(MAKE) --no-print-directory lint-frontend format-check-frontend typecheck-frontend \
	  lint-e2e format-check-e2e typecheck-e2e coverage-frontend build-frontend
	@$(MAKE) --no-print-directory api-drift
	@$(MAKE) --no-print-directory security
	@$(MAKE) --no-print-directory scan-images
	@$(MAKE) --no-print-directory pre-commit
	@$(MAKE) --no-print-directory test-e2e

##@ Cleanup

clean: ## Remove caches, coverage files, build output and Playwright reports
	rm -rf .ruff_cache $(BACKEND_DIR)/.pytest_cache $(BACKEND_DIR)/.ruff_cache $(BACKEND_DIR)/.mypy_cache \
	  $(BACKEND_DIR)/htmlcov $(BACKEND_DIR)/.coverage $(BACKEND_DIR)/.coverage.* $(BACKEND_DIR)/coverage.xml
	find $(BACKEND_DIR) -path '*/.venv' -prune -o -type d -name __pycache__ -exec rm -rf {} +
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/coverage
	rm -rf $(E2E_DIR)/playwright-report $(E2E_DIR)/test-results $(E2E_DIR)/blob-report $(E2E_DIR)/stack-logs

clean-all: require-docker ## clean, plus stop all stacks and delete their volumes (asks first)
	@$(call confirm,This stops all containers and deletes the database volumes.)
	@$(MAKE) --no-print-directory clean
	$(COMPOSE) down -v --remove-orphans
	$(COMPOSE_E2E) down -v --remove-orphans
	@docker volume rm trello-light-trivy-cache >/dev/null 2>&1 || true
