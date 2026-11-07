# Phase 5 — Frontend foundation

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 5: frontend foundation.
Scaffold Vite + React + TS strict, Tailwind, shadcn/ui, TanStack Query, Zustand, Zod,
react-hook-form, @dnd-kit, Vitest. Generate API types from http://localhost:8000/openapi.json.
Build an API client with auth header injection and automatic refresh on 401 (one refresh at a
time, queue concurrent requests), and redirect to login if refresh fails.
Build the login page and protected routes. Add the frontend service to docker-compose and a
Dockerfile. No console warnings. Stop and summarize.
```
