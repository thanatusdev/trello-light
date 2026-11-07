# Phase 8 — CI pipeline

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 8: GitHub Actions CI.

Create `.github/workflows/ci.yml` triggered on pull_request and push to main, with jobs that
run in parallel where possible:

1. backend-quality: uv with caching; ruff check, ruff format --check, mypy.
2. backend-tests: Postgres 16 and Redis service containers with healthchecks; run Alembic
   migrations then pytest with coverage (fail under 80%). Upload coverage.xml as an artifact
   and post a coverage summary to the job summary.
3. migrations-check: verify `alembic check` reports no model/migration drift, and that
   upgrade head -> downgrade base -> upgrade head works on a clean DB.
4. frontend-quality: npm ci with caching; ESLint, Prettier check, `tsc --noEmit`, Vitest with
   coverage, and `vite build`.
5. security:
   - pip-audit on the backend lockfile, npm audit --audit-level=high on frontend and e2e
   - Bandit (or ruff's S rules) for Python security issues
   - gitleaks for committed secrets
   - Build the backend and frontend images and scan them with Trivy (fail on HIGH/CRITICAL
     with a fix available)
6. e2e: depends on backend-tests and frontend-quality; runs the docker-compose e2e stack and
   Playwright. Always upload the Playwright HTML report and traces as artifacts on failure.
7. pre-commit: run `pre-commit run --all-files` so local hooks and CI never disagree.

Also:
- `.github/dependabot.yml` for pip/uv, npm (frontend and e2e), Docker, and GitHub Actions, weekly.
- Optional `.github/workflows/codeql.yml` for Python and JavaScript/TypeScript.
- Pin every action to a commit SHA with the version in a comment, set top-level
  `permissions: contents: read`, and add `concurrency` to cancel superseded runs.
- Add status badges to the top of the README.

Explain any check you made non-blocking and why. Stop and summarize, including the expected
total pipeline duration and how you kept it fast (caching, parallel jobs).
```
