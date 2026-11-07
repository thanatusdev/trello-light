# Project: Kanban Task Manager (Ballast Lane technical exercise)

A Trello-like task management app. Users log in, see a board of status columns,
create/edit/delete tasks, drag tasks between columns, create new columns, assign
tasks to users, and filter tasks. Moving a task into a column flagged `is_done`
marks it completed.

## Monorepo layout
- `backend/`  FastAPI service
- `frontend/` React SPA
- `docker-compose.yml` at the root runs everything
- `docs/AI_USAGE.md` log of prompts, AI output, and corrections (I maintain this)

## Backend stack
- Python 3.12, FastAPI, Pydantic v2, pydantic-settings
- SQLAlchemy 2.0 (async, typed `Mapped[]` style) + asyncpg, Alembic for migrations
- PostgreSQL 16, Redis 7
- Auth: JWT access + refresh tokens (pyjwt), password hashing with pwdlib (bcrypt)
- Rate limiting: slowapi with Redis storage
- Background jobs: Celery + Redis, Celery Beat for scheduled jobs
- Tooling: uv + pyproject.toml, ruff (lint + format), mypy (strict on domain/application), pre-commit
- Tests: pytest, pytest-asyncio, httpx.AsyncClient, pytest-cov (fail under 80%)

## Backend architecture (Clean Architecture + lightweight CQRS)
backend/app/
  domain/          entities, value objects, domain errors, repository interfaces (Protocols)
  application/
    commands/      one module per write use case: Command dataclass + Handler
    queries/       one module per read use case: Query dataclass + Handler returning read DTOs
    ports/         interfaces for external services (notifier, password hasher, token service, unit of work)
  infrastructure/  SQLAlchemy models, repository implementations, unit of work, JWT, Celery tasks, Redis
  api/             FastAPI routers, dependencies (DI wiring), Pydantic request/response schemas, error handlers
  main.py          app factory

Rules:
- Dependencies point inward. `domain` imports nothing from FastAPI, SQLAlchemy, Pydantic, or other layers.
  `application` imports only `domain` and its own `ports`.
- Commands go through domain entities + repositories + unit of work. They return only an id or nothing.
- Queries do NOT use domain entities or repositories; they read directly via SQLAlchemy Core/select into
  read DTOs, optimized for the screen (avoid N+1, select only needed columns).
- Same database for reads and writes. No event sourcing, no message bus. Keep CQRS lightweight.
- Domain errors (e.g. TaskNotFound, StatusNotFound, PermissionDenied) are raised in domain/application
  and mapped to HTTP responses in one place in `api/`.
- Wire handlers via FastAPI dependencies; no global singletons for DB sessions.

## Domain model
- User: id (UUID), email (unique), full_name, hashed_password, is_active, created_at
- Status (board column): id, name (unique, case-insensitive), position (float), is_done (bool), created_at
- Task: id, title (1–200 chars), description (optional), status_id, assignee_id (nullable),
  created_by_id, due_date (nullable date), position (float, ordering within a column),
  completed_at (nullable, set/cleared automatically when moved into/out of an is_done status),
  created_at, updated_at
- Ordering uses fractional indexing: a moved task gets the midpoint between its new neighbours'
  positions; rebalance a column when the gap becomes too small.
- Deleting a status that still has tasks must fail with a clear error (or require a target status
  to move them to). Never cascade-delete tasks silently.

## API conventions
- Prefix `/api/v1`. JSON only. UUIDs as ids. ISO 8601 dates.
- List endpoints are paginated: `?page=&size=` (size max 100), response
  `{items, total, page, size, pages}`.
- Task filters: `status_id`, `assignee_id`, `due_before`, `due_after`, `is_completed`, `search` (title).
- Proper status codes: 201 on create, 204 on delete, 404 not found, 409 conflict, 422 validation,
  401/403 auth, 429 rate limited.
- Every router has tags, summaries, and response models so Swagger docs are clean.

## Frontend stack
- Vite + React 19 + TypeScript 5.9 (strict; pinned below 6.1 for typescript-eslint), npm, Node 22
- react-router v8 (library mode, `createBrowserRouter`)
- TanStack Query for all server state; Zustand only for client UI state (auth token, filters, modals)
- Zod for schemas and API response parsing; react-hook-form + zodResolver for forms
- @dnd-kit for drag and drop; Tailwind CSS (+ shadcn/ui components)
- API types generated from the backend OpenAPI schema (openapi-typescript, committed as
  `src/api/schema.d.ts`, `npm run gen:api`); requests via openapi-fetch
- Vitest + Testing Library + msw for tests (coverage fail under 80%); ESLint + Prettier
- Layout: src/{app (router, providers), api, features/{auth,board,tasks,statuses,filters}, components,
  hooks, stores, lib, test (shared test setup)}
- No console warnings or errors in the browser. Responsive down to mobile width.

## Working rules for the AI
- Use TDD: write failing tests first, then the implementation, then refactor.
- Work only on the phase I ask for. Stop at the end of a phase and summarize what you did,
  what you assumed, and anything you are unsure about.
- Do not add libraries not listed here without asking.
- Never hardcode secrets; read config from environment via pydantic-settings, with `.env.example`.
- Run `ruff`, `mypy`, and `pytest` before declaring a phase done, and report the results.

## E2E testing
- Playwright (TypeScript) in a top-level `e2e/` folder with its own package.json
- Runs against the full docker-compose stack using `docker-compose.e2e.yml` as an override
  (separate DB, seed data loaded, relaxed rate limits via env vars, real Celery worker)
- Locators: prefer getByRole / getByLabel; use data-testid only when no accessible locator exists
- Auth: a setup project logs in once and saves storageState; tests reuse it
- Tests must be independent: each test creates its own data with unique names and never depends
  on another test's state or execution order
- Traces, screenshots, and video kept on failure only

## Frontend linting
- ESLint (typescript-eslint, react-hooks, jsx-a11y) + Prettier; `tsc --noEmit` must pass

## CI (GitHub Actions)
- All checks run on pull requests and pushes to main; main is protected by them
- Actions pinned to a commit SHA, least-privilege `permissions`, concurrency cancels outdated runs
- Never print secrets; use GitHub secrets for anything sensitive

## Developer commands
- The root Makefile is the single entry point. When adding a new command (script, check,
  tool), add a make target with a `## description` comment, and use it from CI.
- Never document a raw command in the README if a make target exists for it.
