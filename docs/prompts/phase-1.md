# Phase 1 — Scaffold and infrastructure

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Do Phase 1 only: project scaffolding and infrastructure.

1. Create the backend with uv: pyproject.toml with all dependencies from CLAUDE.md (dev deps separate),
   ruff + mypy config, pytest config with coverage threshold 80%.
2. Create the folder structure from CLAUDE.md with empty __init__.py files.
3. Implement config via pydantic-settings, the async SQLAlchemy engine/session factory,
   and the app factory in main.py with a GET /api/v1/health endpoint that checks DB and Redis.
4. Initialize Alembic configured for async SQLAlchemy and autogeneration from the models' metadata.
5. Multi-stage Dockerfile for the backend (uv-based, non-root user). docker-compose.yml with
   services: db (postgres:16, healthcheck), redis, api (runs alembic upgrade head then uvicorn),
   worker (celery), beat (celery beat). Use healthchecks and depends_on conditions. Add .env.example.
6. .pre-commit-config.yaml with ruff, ruff-format, mypy, end-of-file-fixer, trailing-whitespace.
7. Test setup: conftest.py with a separate test database, transactional fixtures that roll back
   per test, and an httpx AsyncClient fixture. Write a test for the health endpoint.

Do not implement any domain logic yet. Stop when `docker compose up` starts all services and
`pytest` passes. Summarize what you created and any assumptions.
```
