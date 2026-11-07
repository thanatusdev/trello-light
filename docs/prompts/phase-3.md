# Phase 3 — Statuses and tasks (CQRS)

Sent to Claude Code as the arguments of `/grill-me`, so the AI interviewed me about the open
design questions before writing any code. Verbatim:

```text
Read CLAUDE.md. Phase 3: statuses and tasks, using the CQRS structure. TDD.

Commands: CreateStatus, RenameStatus, ReorderStatus, DeleteStatus (fail with 409 if it has tasks),
CreateTask, UpdateTask, DeleteTask, MoveTask (status_id + position between neighbours, fractional
indexing, rebalance when needed), AssignTask (assignee must exist and be active).
Moving into an is_done status sets completed_at; moving out clears it.

Queries: GetBoard (all statuses ordered by position, each with its tasks ordered by position, in a
fixed number of SQL queries with no N+1, applying the same filters as ListTasks), ListTasks
(paginated, filters from CLAUDE.md), GetTask.

Write unit tests for command handlers using in-memory fake repositories, and integration tests
for the endpoints against Postgres. Cover edge cases: due_date in the past on create (decide and
document the rule), unknown status_id/assignee_id, title validation, pagination bounds, filter
combinations, and moving a task to the top or bottom of an empty or full column.

Stop and summarize, including the SQL queries GetBoard runs.
```
