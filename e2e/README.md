# E2E tests (Playwright)

Browser tests against the full docker-compose stack, using the production frontend build.

Run everything from the repo root:

```sh
make install-e2e                             # dependencies (`make install` also gets the browser)
make test-e2e                                # start the e2e stack, wait for health, run Chromium, tear down
make test-e2e args="tests/auth.spec.ts"      # args go to `playwright test`
make test-e2e E2E_ALL_BROWSERS=1             # also Firefox and WebKit
make test-e2e KEEP_STACK=1                   # leave the stack up afterwards for repeated runs
make test-e2e-ui                             # Playwright UI mode, for debugging
make e2e-report                              # HTML report (traces/screenshots/video kept on failure only)
```

`make test-e2e` wraps `run.sh`, which owns the stack lifecycle.

## The stack

`docker-compose.e2e.yml` overrides the base compose file. `run.sh` runs it as project
`trello-e2e` (override with `E2E_PROJECT`), so it gets its own containers, network and database volume, and can run alongside
the dev stack. Only the web app is published, on port 8081 (override with `E2E_PORT`).

- Every value in the override is a throwaway for this stack only, so no `.env` is needed.
- Demo data is seeded on startup: alice, bob and carol `@example.com`, password `Demo1234!`.
- Access tokens live **5 seconds** (`ACCESS_TOKEN_EXPIRE_SECONDS`), so the refresh flow is real.
- Rate limits are raised, not disabled. All browser traffic reaches the API through nginx from a
  single IP.
- A real Celery worker runs. Beat is left out because its daily job never fires during a run.

## Configuration

| Variable                                | Default                           |
| --------------------------------------- | --------------------------------- |
| `E2E_BASE_URL`                          | `http://localhost:8081`           |
| `E2E_USER_EMAIL` / `E2E_USER_PASSWORD`  | `alice@example.com` / `Demo1234!` |
| `E2E_USER_NAME` / `E2E_OTHER_USER_NAME` | `Alice Johnson` / `Bob Martinez`  |
| `E2E_ALL_BROWSERS`                      | unset (Chromium only)             |
| `E2E_SKIP_BUILD`                        | unset (`run.sh` builds images)    |
| `E2E_LOGS_DIR`                          | unset (no log dump on failure)    |

CI pre-builds the images with `docker/build-push-action` (layer cache shared with the image scan
job), then runs `make test-e2e` with `E2E_SKIP_BUILD=1 E2E_LOGS_DIR=…`, so CI and local runs use
the same target.

## Conventions

- **Page objects** live in `pages/`: `LoginPage`, `RegisterPage`, `BoardPage`, `TaskModal` and `FilterBar`.
- **Fixtures** live in `fixtures/test.ts`. Always import `test`/`expect` from there.
- **Auth:** the `setup` project signs in once and saves `.auth/user.json`. Tests reuse it, and
  each page load swaps the stored refresh token for a fresh access token.
- **Independent data:** every test sets up its own data through the `api` fixture, with names
  containing its `uid`. Teardown deletes everything carrying that `uid`.
  - Seeded tasks are never touched.
  - Drag tests use columns they create themselves. Moves send the neighbours the client saw, so
    sharing columns with parallel tests would rightly return 409s.
- **Console guard:** any console error or warning, or an uncaught page error, fails the test.
  - Allow an expected one per test with `allowConsole(/status of 409/)`.
  - The only global exception is a 401 from an expired access token on an API call, and only
    when a successful refresh follows.
- **Waiting:** use web-first assertions and `expect.poll` only. Fixed sleeps are banned by
  ESLint (`eslint-plugin-playwright`).

## Drag and drop

Moves and reorders use dnd-kit's **keyboard sensor**: Space on the card's "Move …" grip, then
arrow keys, then Space.

- It needs no pixel geometry, so layout changes from other tests' columns don't matter.
- Each arrow press is confirmed by dnd-kit's live-region announcement ("… moved to position 2 of
  3 in “Col”") before the next press. A press can be spent scrolling a container instead of
  moving the card, so tests press until the announcement names the target.
- One test drives the **pointer sensor** with stepped `mouse.move` calls, which get past its 6px
  activation distance. It reorders within a single column so both cards are on screen.

## Checks

`make lint-e2e`, `make typecheck-e2e`, `make format-check-e2e` (all three also run as part of
`make lint`, `make typecheck` and `make format-check`).
