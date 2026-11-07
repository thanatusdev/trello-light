# Phase 7 — End-to-end tests

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 7: end-to-end tests with Playwright.

1. Set up `e2e/` with Playwright + TypeScript, config with a `setup` project for authentication
   (storageState) and Chromium as the main project (add Firefox/WebKit behind an env flag).
   Base URL and credentials from env vars with defaults matching the seed data.
2. Create `docker-compose.e2e.yml` overriding the stack for testing: separate DB volume,
   seed on startup, rate limits relaxed via env vars, frontend served from the production build
   (not the dev server). Add a script `e2e/run.sh` that starts the stack, waits for the health
   endpoint, runs the tests, and tears down.
3. Use the Page Object pattern: LoginPage, BoardPage, TaskModal, FilterBar.
4. Cover these flows:
   - Login success, login failure with an error message, logout, protected route redirects to login
   - Session survives access-token expiry (refresh flow), e.g. by setting a short TTL in the e2e env
   - Create a task, see it in the right column, edit it, delete it with confirmation
   - Drag a task to another column; reload the page and confirm it persisted
   - Drag a task into the Done column; confirm it shows as completed
   - Reorder tasks within a column; reload and confirm the order persisted
   - Create, rename, and delete a column; deleting a column with tasks shows the API error
   - Assign a task to another user and filter by assignee
   - Filter by status and due date range; filters survive reload (URL sync)
   - Form validation messages for invalid input (empty title, too long title)
   - Mobile viewport: board scrolls horizontally and the task modal is usable
   - No console errors or warnings during any test (fail the test via a shared fixture that
     listens to `page.on('console')` and `pageerror`)
5. Use web-first assertions (`expect(locator).toBeVisible()`), never fixed timeouts.
   For drag and drop with @dnd-kit, use mouse move steps or the keyboard sensor
   (whichever is reliable) and explain the choice.

Run the suite three times in a row to check for flakiness and report the results.
Stop and summarize, including any flows you could not make reliable and why.
```
