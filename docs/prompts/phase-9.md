# Phase 9 — Developer experience, documentation and final review

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 9: developer experience, documentation, and final review.

Part 1 — Makefile
Create a Makefile at the repo root as the single entry point for all common tasks.

Requirements:
- `make help` is the default target and prints every target with a one-line description,
  generated from `## description` comments next to each target (self-documenting).
- Group targets with section headers in the help output.
- Declare all targets as .PHONY. Use variables at the top for commands and paths
  (COMPOSE, COMPOSE_E2E, BACKEND_DIR, FRONTEND_DIR, E2E_DIR) so they are easy to override.
- Fail fast with a clear message if a required tool (docker, uv, node/npm) is missing.
- Targets that take arguments use variables, e.g. `make migration name="add due date index"`,
  and print a usage message if the argument is missing.
- Destructive targets (reset-db, clean with volumes) ask for confirmation unless `CONFIRM=yes`.

Targets to include:

Setup
- install: install backend (uv sync), frontend and e2e (npm ci) dependencies, Playwright browsers,
  and pre-commit hooks
- env: create .env from .env.example if it doesn't exist (never overwrite)

Run locally (without Docker for the app; DB and Redis still in Docker)
- dev: start db and redis containers, run migrations, then start the API (uvicorn --reload),
  the Celery worker, and the Vite dev server together, stopping all of them on Ctrl+C
- dev-backend, dev-frontend, dev-worker: run each one individually

Docker
- up: build and start the full stack in the background, wait for the health endpoint,
  then print the frontend URL, API docs URL, and demo credentials
- down, restart, build, ps
- logs: follow all logs; `make logs service=api` for a single service
- shell: open a shell in the api container; db-shell: open psql in the db container

Database
- migrate: run alembic upgrade head
- migration: autogenerate a migration with `name=...`
- downgrade: roll back one migration
- seed: run the idempotent seed script
- reset-db: drop, recreate, migrate, and seed (asks for confirmation)

Testing
- test: run all backend and frontend unit/integration tests
- test-backend, test-frontend
- test-e2e: start the e2e stack, wait for health, run Playwright, tear down even on failure
- test-e2e-ui: run Playwright in UI mode for debugging
- coverage: backend coverage with HTML report, print the path to open it
- e2e-report: open the last Playwright HTML report

Quality and security
- lint: ruff check, ESLint
- format: ruff format and Prettier (write mode); format-check: check only
- typecheck: mypy and tsc --noEmit
- security: pip-audit, npm audit, Bandit, gitleaks
- pre-commit: run all hooks on all files

Aggregate
- check: format-check + lint + typecheck + test (fast pre-push check)
- ci: everything the pipeline runs, in the same order, including security and e2e

Cleanup
- clean: remove caches, coverage files, build outputs, and Playwright reports
- clean-all: clean plus stop containers and delete volumes (asks for confirmation)

Then update `.github/workflows/ci.yml` so each job calls the matching make target instead of
duplicating commands, keeping the job structure, caching, and service containers as they are.

Test the Makefile: run `make help`, `make up`, `make test`, `make lint`, and `make test-e2e`
from a clean clone and report the results. Note that it targets Linux/macOS (and WSL on
Windows) and say so in the README.

Part 2 — README.md
Write README.md with:
- CI status badges
- Overview and the user story
- Architecture diagram (Mermaid) of the Clean Architecture layers and the CQRS split
  (commands through domain + repositories + unit of work, queries reading directly into DTOs)
- Quick start: prerequisites, then `make env && make up` as the one-command setup,
  with the URLs and demo credentials
- Local development without Docker using `make dev`
- A table of the most useful make targets (point to `make help` for the full list)
- Testing: unit, integration, and e2e, how to run each, and how to see coverage
- CI pipeline: what each job checks
- Environment variables table with descriptions and defaults
- Key decisions: CQRS scope, fractional indexing, statuses as a table with is_done,
  async SQLAlchemy, rate limit choices, authorization rule for editing tasks,
  why the Makefile is the shared entry point for local and CI
- Link to docs/AI_USAGE.md

Part 3 — Final review
Review the whole codebase for layer violations, N+1 queries, missing authorization checks,
unhandled errors, and inconsistencies between the README, Makefile, and actual behavior.
List the findings with file and line references before fixing anything, and wait for my
approval before making changes.
```
