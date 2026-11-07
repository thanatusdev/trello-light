# AI usage log

How AI assistance was used to build this project: what was asked, what came back, and what was
corrected or rejected. Maintained by hand; one section per phase.

## How to read this log

- **Prompt:** what was asked (summarised, with a link to the full prompt).
- **Output:** what the AI produced.
- **Corrections:** what was wrong, changed, or rejected, and why.
- **Verification:** how the result was checked (tests, manual runs, review).

Full prompts are stored verbatim in [`docs/prompts/`](prompts/), one file per phase, and the
standing project context lives in [`.claude/CLAUDE.md`](../.claude/CLAUDE.md). The numbers in
this log (test counts, coverage, scan results) come from the tool output recorded in the Claude
Code session transcripts, not from memory.

## Tools

| Tool | Used for |
| --- | --- |
| Claude (claude.ai chat) | Planning: reviewing the brief, choosing the stack, designing the schema and architecture, and writing `CLAUDE.md` and the phase prompts. |
| Claude Code (Claude Opus) | Implementation: one session per phase, running each phase prompt against the repository, writing tests and code, running the tooling. |
| `grilling` / `grill-me` skills | A design-interview step before each phase: the AI asks numbered questions with a recommended answer and does nothing until the plan is approved (see [Workflow](#workflow)). Installed under `.agents/skills/` and `.claude/skills/`. |
| Claude Code subagents | Read-only "Explore" agents that surveyed the code before a phase (Phases 3–9), two independent reviewers in Phase 9 (backend; frontend and docs), and two fix agents that applied the approved review findings. |


## Workflow

1. **Context first.** `CLAUDE.md` holds everything that stays true across sessions: stack,
   architecture rules, domain model, API conventions, and working rules for the AI. Each phase
   prompt then only describes the work for that phase. `CLAUDE.md` was updated when a phase
   showed it was wrong (React 18 → 19, react-router v7 → v8, TypeScript pinned below 6.1, the
   frontend folder layout).
2. **Small, reviewable phases.** Instead of one prompt for the whole application, the work was
   split into nine phases, each in a fresh Claude Code session (`/clear` between phases) and
   each ending with an explicit stop and a summary of what the AI assumed or was unsure about.
3. **Interview before code.** Every phase prompt was sent through `/grill-me`. The AI first
   read the code (often with an Explore subagent), then asked 8–20 design questions, each with
   a recommended answer, and wrote a plan that I approved before any file changed. In almost
   every phase the AI's first round was free-text questions and I had to ask for multiple
   choice ("Please give me options", "Continue, you didn't give any options"), which made the
   decisions faster to review and easier to record.
4. **Tests first.** The AI was instructed to write failing tests before the implementation.
   The transcripts show red-then-green steps in Phases 2–4 and 7. It was not followed
   everywhere: in Phase 1 no failing-test step ran (uv was not installed yet), and in Phase 6
   most UI tests were written after the components. Both are disclosed in the AI's summaries.
   Also, manually tested every flow through Swagger and the UI, then automated them with Playwright.
5. **Quality gate.** ruff, mypy and pytest (backend) and ESLint, Prettier, `tsc` and Vitest
   (frontend) were run at the end of every phase; since Phase 9 they are `make check`.


### Timeline

All work happened on 2026-11-07 (UTC). Session ids are the Claude Code transcript names.

| Phase | Session | Time (UTC) | Notes |
| --- | --- | --- | --- |
| 1 | `499712ee` | 00:06–00:15 | Four false starts before it (see Phase 1). |
| 2 | `63657887` | 00:16–00:55 | One aborted plain-prompt attempt (`df7b162e`). |
| 3 | `ae06fb24` | 00:55–01:20 | |
| 4 | `10d66033` | 01:20–01:45 | |
| 5 | `c0e9a4b5` | 01:45–02:12 | |
| 6 | `3d1ef8d9` | 02:12–02:42 | |
| 7 | `c7bca7c7`, `fa8c91cf` | 02:42–03:38 | First session grilled the E2E/lint/CI sections of `CLAUDE.md` and was interrupted. |
| 8 | `66fdbede` | 03:38–03:51 | |
| 9 | `ad8af05d` | 03:51–04:41 | Ended mid-fix (see Phase 9). |

---

## Phase 0 — Planning (claude.ai)

- **Prompt:** Shared the exercise PDF and my intended stack (FastAPI, PostgreSQL, SQLAlchemy,
  Pydantic, Vite + React, TanStack Query, Zod, Zustand, CQRS, a Trello-like board) and asked
  for suggestions.
- **Output:** A gap analysis against the brief (JWT, pagination, rate limiting, Celery, seed
  data, coverage), a proposed layered folder structure, a schema, and frontend library
  suggestions. Later: `CLAUDE.md`, the phase prompts, and the Makefile and CI phases.
- **Corrections and decisions:**
  - Kept CQRS deliberately lightweight (same database, separate code paths, no event
    sourcing) to fit the scope of the exercise.
  - Accepted the point that user-created statuses can't be an enum: statuses became a table,
    with an `is_done` flag so "mark as completed" maps to moving a card into a done column.
  - Accepted fractional indexing for card ordering, so a move updates one row.
  - Used `@dnd-kit` instead of `react-beautiful-dnd`, which is deprecated.
  - Rejected generating the whole app from one prompt in favour of phased prompts.
  - Extended the AI's plan with my own requirements: Playwright end-to-end tests, a CI
    pipeline with security scanning, and a Makefile as the shared entry point for local
    development and CI.
- **Verification:** Checked the plan against every bullet in the brief and the evaluation
  criteria.

## Phase 1 — Scaffold and infrastructure

- **Prompt:** [`docs/prompts/phase-1.md`](prompts/phase-1.md). uv project, folder structure,
  config, async engine, health endpoint, Alembic, Dockerfile, docker-compose, pre-commit,
  test fixtures.
- **Getting started:** it took four attempts. `/grill-me` was first an unknown command
  (the skill was only in `.agents/skills/`); then it loaded but forwarded to a `grilling` skill
  that wasn't installed, and Claude improvised its own four questions, which I rejected. I
  installed `grilling` and re-ran the prompt.
- **Grilling (16 questions, two rounds, all recommendations accepted):** a separate
  `kanban_test` database created by an init script in the compose Postgres; each test runs in a
  transaction that is rolled back (savepoint mode); Redis tests use database 15; health returns
  200 or 503 "degraded" with a 2-second timeout per check; worker and beat wait for a healthy
  api so migrations run first; mypy strict on `domain` and `application`; rate limiting, auth
  and CORS deferred. Four libraries not listed in `CLAUDE.md` were approved:
  `uvicorn[standard]`, `redis`, `celery[redis]`, `pre-commit`.
- **Output:** `backend/` with `pyproject.toml` (ruff, mypy, pytest with an 80% coverage gate),
  the Clean Architecture package skeleton, pydantic-settings config, async engine and session
  dependency, `/api/v1/health` (DB + Redis), async Alembic `env.py`, Celery app, a multi-stage
  Dockerfile running as a non-root `app` user, `docker-compose.yml` (api, worker, beat, db,
  redis with healthchecks and `depends_on` conditions), `.env.example`, pre-commit hooks.
- **Corrections:**
  - uv resolved SQLAlchemy 2.1.8; the AI pinned it below 2.1 to match `CLAUDE.md`.
  - First lint run: 3 ruff errors (including ASYNC109, an async function with a `timeout`
    parameter, fixed with `asyncio.wait_for`) and 2 mypy errors; an Alembic `path_separator`
    deprecation; a renamed pre-commit hook id (`ruff-check`); an outdated uv image tag.
  - I said uv was already installed; the AI couldn't find it and installed it with Homebrew.
  - Port 6379 was taken by another project, so the local `.env` uses 6380.
  - The AI's summary called the Celery output after stopping Redis harmless, but the logs also
    show `Error on restarting Gossip: AttributeError`, which it didn't mention.
- **Verification:** ruff and mypy clean (18 files); pytest 4 passed, 99.23% coverage.
  `docker compose up --build --wait` brought every service up healthy. Health returned 200,
  then 503 with Redis stopped, then 200 again; `whoami` in the api container returned `app`;
  all five pre-commit hooks passed. **Not done:** the failing-test-first step (the AI admitted
  it in its summary).

## Phase 2 — Users and authentication

- **Prompt:** [`docs/prompts/phase-2.md`](prompts/phase-2.md). Test-first: registration,
  login, refresh, current user, user listing.
- **Grilling:** 13 free-text questions; after "Continue, you didn't give any options" they were
  re-asked as 8 multiple-choice questions, all answered with the recommendation: email
  validated by a domain `Email` value object (no extra library); `Authenticate` and
  `RefreshTokens` live in `commands/` as a documented exception to "commands return only an
  id"; stateless refresh (no denylist); register returns 201 with the user; one generic error
  message per category; `GET /users` needs a token and returns only active users.
- **Output:** User entity and repository protocol, SQLAlchemy model and repository, migration
  `0001`, pwdlib bcrypt hasher (12 rounds, 4 in tests), JWT service (HS256, claims `sub`,
  `type`, `iat`, `exp`, `jti`; 15-minute access, 7-day refresh; expiry checked against an
  injectable clock so tests need no sleeps), `/auth/register|login|refresh|me` and `/users`.
- **Corrections:**
  - **Architecture rule caught by the AI:** queries implemented with SQLAlchemy inside
    `application/` would break "application imports only domain and ports". It asked, and I
    chose to split them: query interfaces in `application/queries/`, SQLAlchemy code in
    `infrastructure/queries/`. Every later phase follows this.
  - **Library not in the stack:** `OAuth2PasswordRequestForm` needs `python-multipart`. The AI
    stopped and asked instead of adding it, as `CLAUDE.md` requires; I approved it.
  - First lint/type pass: 33 ruff and 4 mypy errors, fixed (N818 off project-wide,
    hardcoded-password rules off in tests, coverage `concurrency = ["greenlet", "thread"]`).
  - A constraint-naming convention was added to the SQLAlchemy `Base` and the migration
    regenerated.
- **Verification:** each layer went red then green; API tests started at 25 failed / 4 passed.
  Final: ruff clean, mypy clean (49 files), **89 passed, 99% coverage**; `alembic check` showed
  no drift after an upgrade/downgrade/upgrade cycle. A curl run against the rebuilt container
  covered register, duplicate (409), login, `/auth/me`, a refresh token rejected as an access
  token, wrong password, `/users` and refresh.
- **Security checks from the review list:** unknown email and wrong password return the same
  401 "Incorrect email or password", and a dummy bcrypt check makes unknown emails take as
  long as real ones; every token failure is 401 "Could not validate credentials"; the `type`
  claim stops refresh tokens being used as access tokens; inactive users can't log in; the
  JWT secret has no default.
- **Left open:** refresh tokens couldn't be revoked; login wasn't rate limited yet.

## Phase 3 — Statuses and tasks (CQRS)

- **Prompt:** [`docs/prompts/phase-3.md`](prompts/phase-3.md). Commands and queries for
  statuses and tasks, pagination, filters, fractional ordering.
- **Grilling:** twelve questions first posted as prose; after "Give me the options" they were
  re-asked as three multiple-choice batches. All recommendations accepted. The decisions are
  recorded in [`DECISIONS.md`](DECISIONS.md), mainly:
  - one shared board where every active user can edit everything (no 403s);
  - the client sends neighbour ids (`after_id`/`before_id`) and the server computes the
    position (first item 1024, rebalance below a gap of `1e-6`, row locks);
  - `PATCH /tasks/{id}` changes only title, description and due date; column and assignee
    change through dedicated endpoints;
  - unknown id in the path is 404, in the body 422;
  - `is_done` can't change after creation;
  - the three default columns are seeded by the migration;
  - GetBoard runs two queries with the assignee name joined in.
  The AI spotted that two answers conflicted for an unknown neighbour id; I chose 409 for every
  neighbour problem.
- **Output:** nine commands (Create/Rename/Reorder/DeleteStatus, Create/Update/Delete/Move/
  AssignTask), queries GetTask, ListTasks, GetBoard and GetStatus, migration `0002` (unique
  index on `lower(name)`, index on `tasks(status_id, position)`, `ON DELETE RESTRICT` on every
  foreign key from `tasks`), routers for statuses, tasks and the board, and `DECISIONS.md`.
  Creating or moving a task locks the target column row (`SELECT … FOR UPDATE`).
- **Corrections:**
  - During TDD the case-insensitive unique-index test failed with `PendingRollbackError`:
    `session.add` was called before `begin_nested`. The AI fixed it in the status repository
    and flagged that the Phase 2 user repository had the same bug. When I said "Please fix the
    bugs", it wrote a failing test (`test_session_stays_usable_after_duplicate_email`) and then
    the fix.
  - Two coverage gaps closed with extra tests; the running container was serving an old image
    and was rebuilt.
- **Verification:** final run ruff clean, mypy clean (79 files), **297 passed, 99.94%
  coverage**; migration upgrade/downgrade/upgrade clean. A test captures the SQL and asserts
  that GetBoard runs **exactly two statements** whatever the board size (the SQL is in
  `DECISIONS.md`). A smoke test confirmed the seeded columns, that moving a task into Done set
  `completed_at`, and that delete returned 204.
- **Left open:** locking was only tested with fakes, not two real transactions (Phase 9 found
  real races, B2/B4/B5).

## Phase 4 — Rate limiting, background jobs, seed data

- **Prompt:** [`docs/prompts/phase-4.md`](prompts/phase-4.md). slowapi with Redis, Celery
  assignment notifications and daily due-date reminders, idempotent seed script.
- **Grilling:** an Explore subagent scanned the code while the AI asked its first questions;
  when the scan returned, the AI corrected three of its own recommendations (login takes form
  data, not JSON; `AssignTask` needs to know who assigned and whether the assignee changed;
  the domain rejects past due dates, so the seed can't contain overdue tasks). After "Please
  give me options", 12 multiple-choice questions, all recommendations accepted.
- **Output:**
  - Limits: 100/min by default (per user with a valid JWT, else per IP), login 5/min per IP,
    register 3/min per IP, health exempt; all configurable. 429 responses carry `Retry-After`.
    If Redis is down the limiter lets requests through. `X-Forwarded-For` is not trusted.
  - A `Notifier` port; `CeleryNotifier` enqueues only ids, and the handler calls it on the line
    **after** `uow.commit()`, only when the assignee really changed and isn't the person
    assigning. Enqueue errors are logged, not raised.
  - Celery tasks are thin sync wrappers around async job functions (tested directly), each with
    its own NullPool engine, retrying `OSError`/`OperationalError` up to 3 times.
  - Beat runs a daily digest at 08:00 UTC: one email per assignee for open tasks due today or
    tomorrow, written to the worker log by `ConsoleEmailSender`.
  - The seed goes through the real command handlers, is idempotent (by email, status name and
    task title), and runs only with `SEED_DEMO_DATA=true`: users alice, bob and carol
    @example.com and 15 tasks.
- **Corrections:**
  - **slowapi's middleware silently enforced nothing.** On FastAPI 0.162 it couldn't match
    routes inside included routers, so every request passed. The failing tests caught it; the
    AI confirmed it with a debug script and rewrote enforcement as FastAPI dependencies on top
    of slowapi's limiter and Redis storage. This is a workaround, not standard slowapi usage.
  - Smaller self-fixes: a regex edit that broke a test file, a grammar bug in the digest
    ("These task are due"), an edit that silently didn't apply (caught with
    `pytest --collect-only`), a mypy union error, the seed's log line missing in Docker.
- **Verification:** ruff and mypy clean (89 files), **349 passed, 99.75% coverage**;
  rate-limit tests ran against both in-memory storage and real Redis. On the live stack: six
  bad logins gave `401 ×5, 429` with `retry-after: 59`; assigning a task logged the email in
  the worker; a manual `celery call` of the digest produced emails for all three users; running
  the seed again created nothing.
- **Left open:** no "already reminded" flag, so a task can be reminded twice; Beat firing on
  schedule and the autoretry were not tested live. The AI also changed my dev environment
  (rebuilt containers, reassigned a demo task, flushed dev Redis db 0).

## Phase 5 — Frontend foundation

- **Prompt:** [`docs/prompts/phase-5.md`](prompts/phase-5.md). Vite + React + TypeScript
  setup, generated API types, API client with token refresh, login and protected routes.
- **Grilling:** an Explore subagent checked the backend first and found that the prompt's
  OpenAPI URL was wrong (`/api/v1/openapi.json`), that there was no CORS, and that login takes
  form data while refresh takes JSON. After "Please give me options", all recommendations were
  accepted: a same-origin proxy instead of CORS, access token in memory and refresh token in
  `localStorage`, nginx multi-stage image, msw for tests, the generated `schema.d.ts`
  committed, an 80% coverage gate.
- **Output:** the Vite app, openapi-fetch client with one auth middleware, Zustand store that
  persists only the refresh token, login page with inline errors for 401, 429 (with the wait
  time) and network failures, protected and public-only routes, a post-login redirect that
  can't leave the app, the frontend Dockerfile and nginx config, and a frontend service in
  compose (port 8080).
- **Corrections:**
  - **Versions.** `CLAUDE.md` said React 18, but current tooling targets 19; I approved React
    19 with react-router v8. The Vite template shipped TypeScript 7 with oxlint, while
    typescript-eslint supports TypeScript below 6.1; TypeScript was pinned to ~5.9.3 and ESLint
    used instead. `CLAUDE.md` was updated.
  - **msw v3 renamed `onUnhandledRequest` to `onUnhandledFrame`.** With the old name, requests
    without a mock didn't fail tests. `tsc` caught it.
  - jsdom fixes (`matchMedia` missing, 8 route tests failing), one flawed open-redirect test and
    one wrong sign-out assertion, a 562 kB chunk split, two `Cache-Control` headers merged.
  - shadcn added a `cn` package: checked and kept; `next-themes` removed from the toast.
- **Verification:** the AI broke the code on purpose to prove the tests work: removing the
  shared refresh made 3 tests fail; removing the cache clear on sign-out made 1 fail. Final:
  43 tests, statements 94.51% / branches 93.68%; lint, Prettier, `tsc`, build clean; 0
  production `npm audit` findings. Login, `/me` and refresh worked through nginx in Docker.
  **Not done:** a browser check for console warnings (I declined the Chrome extension).
- **Left open:** behind nginx every user shares one IP for the login limit; the refresh token in
  `localStorage` is exposed to XSS; logout only clears the browser.

## Phase 6 — Board

- **Prompt:** [`docs/prompts/phase-6.md`](prompts/phase-6.md). Board with drag and drop,
  optimistic updates, column management, task modal, filters synced to the URL, list view.
- **Grilling:** seven free-text questions, then "give me options" and four rounds (16
  questions). **I overrode the recommendation twice:** a shadcn Calendar instead of a native
  date input (adds `react-day-picker` and `date-fns`), and a searchable combobox for the
  assignee instead of a select (adds `cmdk`).
- **Output:** `/board` and `/tasks` (list view) routes; `lib/ordering.ts` mirroring the
  backend rules; optimistic task move, column move and task delete (cancel queries, snapshot,
  update the cache, roll back with a toast; a 409 shows "board changed, refreshed"); stable
  query keys (`['board', filters]`, `['tasks', 'list'|'detail', …]`); pointer, touch and
  keyboard sensors with screen-reader announcements; the task modal open state in the URL
  (`?task=`); filters parsed from the URL with Zod.
- **Corrections:**
  - **The AI changed a planned rule on its own:** with filters active, a drag sends only one
    neighbour, because the server returns 409 for neighbours that aren't adjacent in the full
    column. It disclosed this in the summary.
  - All 5 optimistic-move tests failed at first (`onMutate` awaits `cancelQueries`); fixed with
    a helper that holds the mocked request.
  - ESLint errors (reading refs during render, fast-refresh exports), accessible names for the
    column section and "Add task to X", a debounce recreated every render, Enter followed by
    blur renaming a column twice.
- **Verification:** **143 tests, 93.29% lines / 83.3% branches**; lint, `tsc`, Prettier and
  build clean; 0 warnings in the test output; backend unchanged (349 passed). **The app was
  not opened in a real browser** in this phase; the AI said so and recommended a manual pass.
  Phase 7's e2e tests are where drag and drop, mobile and the console were first checked.
- **Left open:** an edit saved through several endpoints can partly succeed; the assignee
  picker loaded only the first 100 users (fixed in Phase 9, F6); column names came from the
  unfiltered board (fixed in Phase 9, F2, backend half).

## Phase 7 — End-to-end tests

- **Prompt:** [`docs/prompts/phase-7.md`](prompts/phase-7.md). Playwright with page objects,
  stored auth state, a dedicated docker-compose override, a console-error fixture. A first
  session grilled the E2E, frontend-linting and CI sections of `CLAUDE.md` (20 questions); it
  found that `eslint-plugin-jsx-a11y` didn't support ESLint 10, and I interrupted it there.
- **Grilling:** after "give me options", all recommendations accepted: a 5-second access token
  in the e2e stack (a new `ACCESS_TOKEN_EXPIRE_SECONDS`, added test-first) so token refresh is
  exercised for real; drags through dnd-kit's keyboard sensor plus one mouse test; rate limits
  raised (not disabled); a self-contained `docker-compose.e2e.yml` with clearly labelled
  throwaway secrets; Celery worker only.
- **Output:** `e2e/` with 9 spec files and 21 tests, page objects (`LoginPage`, `BoardPage`,
  `TaskModal`, `FilterBar`), a shared fixture with an automatic console-error check, a per-test
  allowlist, unique ids and API cleanup, and `run.sh`, which tears the stack down on exit.
- **Conflict the AI raised itself:** a 5-second token plus a strict console check would fail
  at random, because browsers log the 401 that triggers the refresh. The fix is one narrow
  rule: an API 401 is ignored only if a successful `/auth/refresh` follows.
- **Real application bugs found by e2e:**
  - React error #185 (infinite update loop) during keyboard drags across columns: failed 2 of
    20 runs before the fix, 0 of 40 after (dnd-kit's documented guard).
  - The first ArrowRight moved the card down its own column (new `dnd-keyboard.ts`).
  - Wrong screen-reader position when reordering within a column.
  - The page scrolled sideways on mobile (852 px wide on a 412 px screen).
  - On WebKit, deleting a task logged a 404 console error.
- **Test bugs the AI made and fixed:** an ambiguous "Alice Johnson" locator, `storageState`
  outside `use`, a card locator rooted at the wrong element, keyboard-drag timing.
- **Verification:** three runs in a row with retries off, 21/21 each time, done twice (before
  and after the WebKit fix); all browsers 57 passed, 4 skipped (the mobile spec is
  Chromium-only); a full `run.sh` cycle from scratch passed in about 40 s and left nothing
  behind. Frontend 149 tests, backend 351.
- **Left open:** the mobile overflow fix is covered only by e2e; 10 moderate `npm audit`
  findings in e2e dev dependencies.

## Phase 8 — CI pipeline

- **Prompt:** [`docs/prompts/phase-8.md`](prompts/phase-8.md). GitHub Actions: lint, type
  checks, tests with coverage, migration drift, security scans, e2e, Dependabot.
- **Grilling:** 12 questions, all recommendations accepted: ruff's `S` rules instead of Bandit
  (reversed in Phase 9); CodeQL as the only non-blocking check; Trivy fails on fixable
  HIGH/CRITICAL; audits block at high and above; gitleaks as a pinned CLI with a verified
  checksum; e2e reuses `run.sh`; an extra `api-drift` job to fail when the committed frontend
  types are out of date.
- **Output:** `ci.yml` with 9 jobs (parallel except e2e), `codeql.yml`, `dependabot.yml`
  (weekly, minor/patch grouped, `typescript >=6.1` ignored), `.gitleaks.toml`, `.trivyignore`.
  Every action is pinned to a commit SHA looked up with `git ls-remote`; top-level permissions
  are `contents: read`; only CodeQL gets `security-events: write`; concurrency cancels
  superseded runs; checkouts use `persist-credentials: false`.
- **Corrections:**
  - **Trivy failed** on the frontend image (about a dozen fixable HIGH/CRITICAL CVEs in
    `nginx:1.27-alpine`). The AI upgraded to `nginx:1.30-alpine` instead of ignoring them;
    `.trivyignore` has no entries.
  - The gitleaks allowlist covers only the labelled CI/e2e throwaway values, the `change-me`
    placeholders and the documented demo password.
  - The plan said `docker buildx bake` for e2e; the AI used `build-push-action` because bake
    needs a `.env`, and said so.
- **Verification:** run locally only. **CI has never run on GitHub**: the repo has no commits
  and no remote yet. actionlint and zizmor found nothing; pip-audit clean; npm audit passes at
  high; Trivy clean on both images; backend 351 passed (99.75%); frontend 149 passed; e2e
  21/21. The 8–15 minute pipeline duration is an estimate, not a measurement.
- **Left open:** branch protection needs a remote; the README badges still say `OWNER/REPO`.

## Phase 9 — Developer experience, documentation and final review

- **Prompt:** [`docs/prompts/phase-9.md`](prompts/phase-9.md). Self-documenting Makefile used
  by CI, README, and an AI-assisted review of the whole codebase.
- **Grilling:** about 20 questions; after "give me options", all recommendations accepted:
  `make dev` in plain shell with `trap`; the clean-clone test in an isolated copy with its own
  compose project and ports; Bandit added through a pinned `uvx`; extra targets
  (`migrations-check`, `api-drift`, `scan-images`, `build-frontend`); `make test-e2e` wraps
  `run.sh`.
- **Output:** a root `Makefile` with 64 documented targets (`make help`), `ci.yml` rewired to
  call make targets, a rewritten `README.md` and `e2e/README.md`, the first version of this
  file.
- **Review:** two read-only reviewer subagents (backend; frontend and docs consistency)
  produced 28 findings. The AI recommended fixing 7 now and deferring the rest; **I answered
  "all of them"**, so nothing was deferred. Two fix agents applied them. The docs reviewer
  also found 7 mistakes in the AI's own new Makefile and README (targets missing from
  `make help`, wrong env defaults, "GET /board runs two statements" when auth adds a third),
  which were fixed before the report.

  | ID | Finding | Outcome |
  | --- | --- | --- |
  | B1 | A login password over 72 bytes raised bcrypt's `ValueError` → **500**. Reviewer said Medium; the AI reproduced it with curl and raised it to High. | Fixed: `verify` never raises; 72-byte limit on register; tests for 73-byte ASCII and multi-byte input. |
  | B2 | Lost update: `save()` writes every column from an unlocked read, so a concurrent PATCH can undo a move and its `completed_at`. | Code added (`get_for_update` in update/assign/move/delete); **not fully verified**. |
  | B3 | `JWT_SECRET` had no minimum length (`change-me` accepted). | Fixed: at least 32 characters. |
  | B4 | Concurrent column creates/reorders could get the same position on an empty board. | Code added (advisory board lock); not fully verified. |
  | B5 | A rebalance could overwrite a task that just left the column; two rebalances could deadlock. | Code added (`WHERE status_id`, locks in id order); not fully verified. |
  | B6 | Refresh tokens reusable and never revoked. | **Incomplete**, see below. |
  | B7 | Domain 422s returned a string `detail`; FastAPI returns a list. | Fixed: same shape as FastAPI. |
  | B8 | The health router used SQLAlchemy directly. | Fixed: `HealthProbe` port. |
  | B9 | 429 documented only on login/register in OpenAPI. | Fixed: on every limited route, with `Retry-After`. |
  | B10 | No index for the `GET /tasks` sort or due-date filter. | Fixed: migration `0003` (`ix_tasks_created_at_desc_id`, `ix_tasks_due_date`). |
  | F1 | Any refresh failure (network, 5xx, 429) logged the user out. | Fixed: only 400/401 ends the session; retry screen otherwise. |
  | F2 | Column names were read from the whole board. | Backend `GET /statuses` added; **frontend switch not done**. |
  | F3 | No sign-up page. | Fixed: `/register` page and an e2e spec (spec not yet run). |
  | F4 | `jsx-a11y` required by `CLAUDE.md` but not installed. | Fixed via npm `overrides`; 6 violations fixed. |
  | F5 | Overlapping moves: one rollback discarded the other's optimistic state. | Fixed with mutation keys. |
  | F6 | Assignee list cut at 100 users; a load error looked like "No one matches". | Fixed: all pages, error state. |
  | F7 | No tests for the column components. | Fixed: 4 test files. |
  | F8 | Rename button and add-column input lacked accessible names/error links. | Fixed. |
  | F9 | `CLAUDE.md` frontend layout out of date. | Fixed in `CLAUDE.md`. |
  | F10 | Only login used `Retry-After` in messages. | Fixed everywhere. |
  | D1 | `docs/AI_USAGE.md` missing. | Fixed (this file). |
  | D2–D3 | `e2e/README.md` used raw commands and described CI wrongly. | Fixed. |
  | D4–D7 | Unused `frontend/.env.example`; Node engines allowed 24; stale `.gitignore` line; missing `HEALTH_CHECK_TIMEOUT_SECONDS`. | Fixed. |
  | D8 | Shared-board authorization vs. `PermissionDenied` in `CLAUDE.md`. | Kept by decision; `DECISIONS.md` not yet updated. |

- **Interventions:** I asked to run the project mid-review; the AI declined to rebuild while
  agents were editing. I then pointed out that the frontend was out of date ("the front is not
  up to date"): the clean-clone `make up` had built under another compose project name. The AI
  added `make up service=frontend` and rebuilt. I then stopped the backend fix agent, and the
  session ended without a phase summary.
- **Verification:** in the clean copy, `make help`, `env`, `up`, `lint`, the DB targets,
  `make dev` and `clean-all` worked; `make test` failed until `make install` was run and the
  Node version set, then passed (backend 351 at 99.75%, frontend 149); `make test-e2e` 21/21.
  After the frontend fixes: 210 frontend tests, about 93% coverage, lint (including jsx-a11y),
  `tsc` and build clean. In the real repo: lint, format-check, typecheck, security,
  scan-images and pre-commit passed.
- **State at the end of the phase (still to do):**
  - **B6 is half done and the backend suite doesn't run:**
    `tests/unit/application/test_refresh_tokens.py` imports `app.application.commands.logout`,
    `TokenStoreUnavailable` and `FakeRefreshTokenStore`, which don't exist, so
    `pytest --collect-only` stops with 1 error (391 tests collected). Finish (Redis-backed
    rotation and `POST /auth/logout`) or revert.
  - B2, B4, B5 and `GET /statuses` need a full backend run; the last one before the stop was
    1 failed / 387 passed, and that test was edited but not re-run.
  - Frontend: switch `useColumns` to `GET /statuses`, run `make gen-api`, wire logout.
  - Run `e2e/tests/register.spec.ts`; update `DECISIONS.md` (D8, B4 locking); final
    `make check` and `make test-e2e`.

---

## Answers to the exercise questions

### The prompt used

The prompt is two parts: [`CLAUDE.md`](../.claude/CLAUDE.md) as standing context, and nine
phase prompts in [`docs/prompts/`](prompts/). Each phase prompt was run through `/grill-me`,
so the AI asked about the open design questions and I approved a plan before any code
changed. The design choices behind them:

- **Specific constraints instead of open requests.** The prompts name the libraries, layer
  rules, status codes, pagination format, and edge cases to test, so the AI isn't choosing
  them silently.
- **Rules stated as rules.** For example, "`domain` imports nothing from FastAPI, SQLAlchemy,
  or Pydantic" is something I can check with a search or a linter; "use clean architecture"
  is not.
- **Explicit stop points.** Each phase ends with a summary of assumptions and uncertainties,
  which tells me where to focus my review.
- **A rule against new libraries without asking.** It worked: the AI stopped for
  `python-multipart` (Phase 2) and listed the extra packages for approval in Phases 1 and 6.

### Representative output

**Command handler** ([`move_task.py`](../backend/app/application/commands/move_task.py)): a
command goes through the unit of work and domain objects, locks rows in a fixed order, and
returns nothing. The lock ordering came from the Phase 9 review (B5).

```python
async def handle(self, command: MoveTask) -> None:
    current = await self._uow.tasks.get(command.task_id)
    if current is None:
        raise TaskNotFound()
    # Lock order: column rows in id order, then the task row.
    status = await self._lock_columns(current.status_id, command.status_id)
    task = await self._uow.tasks.get_for_update(command.task_id)
    ...
    placement = place(await self._uow.tasks.list_positions(status.id), task.id,
                      after_id=command.after_id, before_id=command.before_id)
    if placement.rebalanced:
        await self._uow.tasks.set_positions(status.id, placement.rebalanced)
    task.move_to(status, position=placement.position, now=self._clock())
    await self._uow.tasks.save(task)
    await self._uow.commit()
```

**Query side:** GetBoard reads straight into DTOs with two SQL statements, asserted by a test
([`DECISIONS.md`](DECISIONS.md#getboard-runs-exactly-two-sql-statements)).

**Frontend client** ([`client.ts`](../frontend/src/api/client.ts)): concurrent 401s share one
refresh, and each request is retried at most once.

```ts
let inflightRefresh: Promise<string> | null = null

export function refreshSession(): Promise<string> {
  inflightRefresh ??= doRefresh().finally(() => {
    inflightRefresh = null
  })
  return inflightRefresh
}
```

**End-to-end test** ([`drag-drop.spec.ts`](../e2e/tests/drag-drop.spec.ts)): each test
creates its own columns, drags with the keyboard sensor, and checks the result survives a
reload.

```ts
test('moves a task to another column and keeps it after a reload', async ({ board, api, uid }) => {
  const from = await api.createColumn(`${uid} backlog`)
  const to = await api.createColumn(`${uid} doing`)
  const task = await api.createTask({ title: `${uid} ship it`, statusId: from.id })

  await board.goto()
  await board.keyboardMoveToColumn(task.title, to.name)
  await board.expectTaskIn(to.name, task.title)

  await board.page.reload()
  await board.expectLoaded()
  await board.expectTaskIn(to.name, task.title)
})
```

### How I validated the AI's suggestions

- **Design before code.** Every phase started with the grill-me interview and a plan I
  approved, so the decisions are explicit and recorded (`DECISIONS.md`).
- **Tests and tools after every phase.** Manually tested every flow through Swagger and the UI,
  then automated them with Playwright. Addionationally, we used ruff, mypy, pytest with an 80% gate,
  ESLint, Prettier, `tsc` and Vitest; since Phase 9, `make check`. Backend coverage stayed at about
  99.75% and frontend at about 92–94%.
- **Proving tests can fail.** In Phase 5 the AI removed the shared token refresh and the cache
  clear on sign-out to confirm that 3 and 1 tests failed.
- **Running the real stack.** Every backend phase ended with curl checks against the rebuilt
  containers (Phase 4: six bad logins → `401 ×5, 429`, `retry-after: 59`), and Phase 7 runs
  every flow in a browser.
- **Flakiness.** The e2e suite ran three times in a row with retries off (twice), and the
  React #185 fix was checked over 40 runs.
- **Independent review.** In Phase 9 two separate reviewer agents read the whole codebase; the
  AI reproduced the most serious finding (B1) against the running stack before rating it.
- **Architecture boundaries.** The reviewer checked layer imports and found one violation
  (the health router, B8).
- **Library APIs.** Checked against documentation when something didn't behave as expected:
  slowapi's middleware on FastAPI 0.162, the msw v3 rename, typescript-eslint's TypeScript
  range, dnd-kit's guard against update loops.


### How I corrected or improved the output

1. **Rate limiting that didn't limit (Phase 4).** slowapi's middleware let every request
   through on FastAPI 0.162. The tests caught it; enforcement was rewritten as FastAPI
   dependencies using slowapi's Redis storage.
2. **A 500 on long passwords (Phase 9, B1).** bcrypt raises on passwords over 72 bytes. The AI
   wrote the original hasher; the review found it, reproduced it with curl, and fixed it with
   tests on both login and register.
3. **Race conditions in ordering (Phase 9, B2/B4/B5).** Phase 3's locking was only tested with
   fakes. The review found lost updates and possible deadlocks; locks were added in a fixed
   order (still to be fully verified).
4. **Version drift (Phase 5).** The AI's training-era defaults (React 18, TypeScript 7 with
   typescript-eslint) didn't match the current ecosystem; I approved React 19 / react-router v8
   and pinned TypeScript below 6.1, and updated `CLAUDE.md`.
5. **Choosing everything instead of the AI's triage (Phase 9).** The AI proposed fixing 7 of
   28 findings and deferring the rest; I had all of them fixed, including a Register page and
   jsx-a11y.
6. **Asking for options.** In most phases the AI's first round was free-text questions; I asked
   for multiple choice every time, and twice (Phase 6) chose differently from its
   recommendation.

### How edge cases, authentication, and validation were handled

- **Authentication:** 15-minute access tokens and 7-day refresh tokens; a `type` claim so a
  refresh token can't be used as an access token; the same error for unknown email and wrong
  password, plus a dummy bcrypt check so the response time doesn't reveal which; inactive users
  rejected; the JWT secret required and at least 32 characters; passwords limited to 72 bytes.
  On the client, concurrent 401s share one refresh, and only a 400/401 from refresh ends the
  session. Refresh-token revocation and logout are in progress (B6).
- **Authorization:** one shared board. Any active, authenticated user can create, edit, move,
  assign and delete every task and column; there is no owner rule and no 403. Enforced by the
  `get_current_user` dependency on every route except health, register, login and refresh.
  This was chosen in Phase 3 and confirmed after the Phase 9 review (D8).
- **Validation:** Pydantic on the API boundary, domain rules in the entities (title 1–200
  characters, column names 1–50 and unique case-insensitively, due date not in the past),
  and Zod on the frontend mirroring the backend rules. Domain 422s use the same shape as
  FastAPI's (B7). Unknown ids in the path are 404, in the body 422.
- **Domain edge cases:** deleting a column that still has tasks returns 409 and every foreign
  key from `tasks` is `ON DELETE RESTRICT`; `completed_at` is set and cleared when moving into
  and out of a done column and kept between two done columns; ordering handles empty columns,
  rebalances below a gap of `1e-6`, and returns 409 when the client's view of the neighbours is
  stale; pagination bounds are enforced (size 1–100) and a page past the end is empty;
  search escapes `%`, `_` and `\`. All of this is in [`DECISIONS.md`](DECISIONS.md).
- **Abuse and consistency:** login 5/min and register 3/min per IP, 100/min otherwise, with
  `Retry-After`; Celery notifications are dispatched only after the transaction commits and
  carry only ids; column and task writes lock rows so concurrent writers can't pick the same
  slot.

### How performance and idiomatic quality were assessed

- **Database:** GetBoard runs exactly two SQL statements whatever the board size, and a test
  asserts it. Indexes: unique `lower(name)` on statuses; `tasks(status_id, position)`;
  `tasks(assignee_id)`; `tasks(created_at DESC, id)` for the list sort and `tasks(due_date)`
  (migration `0003`, added after the review). No index on `completed_at`, because the filter
  matches a large share of rows (rationale in the migration).
- **Async correctness:** Celery enqueueing runs through `asyncio.to_thread`, Celery jobs get
  their own NullPool engine, and the health checks use `asyncio.wait_for` with a timeout.
  **Known gap:** bcrypt (12 rounds) runs synchronously inside the async `Authenticate` and
  `RegisterUser` handlers, so each login or registration blocks the event loop for the length
  of one hash. Neither the AI nor the Phase 9 reviewers flagged it; the fix is to call the
  hasher through `asyncio.to_thread`. Login is rate limited to 5/min per IP, which limits the
  impact but doesn't remove it.
- **Idiomatic code:** SQLAlchemy 2.0 typed models and `select()` style, FastAPI dependencies
  for wiring, Pydantic v2 APIs, and ruff and mypy (strict on `domain` and `application`)
  enforcing consistency. On the frontend, server state stays in TanStack Query and only UI
  state goes in Zustand; ESLint with jsx-a11y and `tsc` strict.
- **Frontend:** optimistic updates for card and column moves with rollback, a 562 kB bundle
  split into chunks, and no console warnings, enforced by the Playwright console-error fixture.

---

## Lessons learned

- Phased prompts with stop points produced reviewable changes; one large prompt would have
  produced more code than I could properly check.
- A good `CLAUDE.md` reduced repeated corrections, because rules written once applied to
  every session. It also had to be corrected when the AI found it was out of date (React,
  TypeScript, folder layout).
- The grill-me interview was the most useful step: it surfaced conflicts before code (the
  `application` layer importing SQLAlchemy, two contradictory 409/422 answers, the 5-second
  token versus the console check). Asking for multiple-choice options made it much faster.
- The AI was most reliable on well-specified, test-covered backend work, and when it checked
  its own assumptions against the code (Explore agents) before proposing answers.
- It was least reliable when a check needed something outside the test suite: the board was
  not opened in a browser until e2e existed, CI has never run on GitHub, its summaries left
  out an error in the logs (Phase 1) and the slowapi problem only showed because tests failed.
  Concurrency bugs passed every unit test and were only found by a separate review.
- Next time: commit after each phase, I decided to make all changes locally and check everything first before commiting the changes. However, this made the history harder to follow and left the Phase 9 fixes half applied in the working tree; write a real two-transaction test for locking in Phase 3; Run the e2e and CI pipeline earlier if I had created the pipeline on earliest steps, and committed every phased before moving to the next one, I'd have one less step, I didn't need to run all the tests, lint and everything because the github actions would do that for me.
