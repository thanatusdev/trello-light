# Phase 4 — Rate limiting, background jobs, seed data

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 4.
1. Rate limiting with slowapi + Redis: stricter on /auth/login (e.g. 5/minute per IP), a default
   limit for other endpoints. Return 429 with a Retry-After header. Test it.
2. Celery: a notifier port in application, a Celery implementation in infrastructure. Send an
   "assigned to you" notification (log/console email backend is fine) when AssignTask runs,
   dispatched only after the transaction commits. Celery Beat job that runs daily and notifies
   assignees of tasks due within 24h. Unit-test the task functions directly.
3. Seed script (idempotent) creating 3 demo users, default statuses (To Do, In Progress, Done
   with is_done=true), and ~15 tasks with varied assignees and due dates. Run it on startup in
   docker-compose. Put the demo credentials in .env.example.
Stop and summarize.
```
