# Phase 2 — Users and authentication

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 2: users and JWT authentication, test-first.

Write failing tests first, then implement:
- User entity and repository interface in domain; SQLAlchemy model + repository + Alembic migration.
- Commands: RegisterUser (email unique, password min 8 chars), and an Authenticate handler that
  returns access + refresh tokens. Access token 15 min, refresh token 7 days, with a `type` claim
  so a refresh token can't be used as an access token.
- Endpoints: POST /auth/register, POST /auth/login (OAuth2PasswordRequestForm so Swagger's
  Authorize button works), POST /auth/refresh, GET /auth/me. Query: GET /users (paginated, for
  the assignee picker).
- A `get_current_user` dependency. Inactive users get 401.
- Tests must cover: duplicate email (409), wrong password (401, same message as unknown email to
  avoid user enumeration), expired token, tampered token, refresh token used as access token,
  missing token.

Stop and summarize when tests pass.
```
