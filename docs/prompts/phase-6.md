# Phase 6 — Board

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 6: the board.
- Board page rendering columns from GetBoard; drag tasks within and across columns with @dnd-kit
  (keyboard accessible), computing the new position from neighbours. Use optimistic updates with
  rollback on error and a toast.
- Create, rename, reorder, and delete columns (show the API's error if the column has tasks).
- Task modal: create, edit, delete (with confirmation), assign, due date, mark complete.
  Forms use react-hook-form + Zod mirroring backend rules.
- Filter bar (status, assignee, due date range, search) kept in Zustand and synced to the URL.
- A paginated list view of tasks as an alternative to the board.
- Responsive: columns scroll horizontally on mobile. Loading and empty states.
- Vitest tests for the task form validation and the position calculation helper.
Stop and summarize.
```
