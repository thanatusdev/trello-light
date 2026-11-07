# Design decisions

Rules that are not obvious from the code, with the reasoning behind them.

## Board and authorization

- One shared board. Any active, authenticated user can create, edit, move, assign and delete
  every task and column. There is no admin role and no owner-only rule (no 403s yet).
- A fresh database is seeded by migration `0002` with three columns: **To Do**, **In Progress**,
  **Done** (`is_done = true`).

## Sessions and refresh tokens

- A login starts a session. Every refresh token carries the session id (`sid`) and the login's
  absolute expiry; rotating keeps both, so a session never outlives `REFRESH_TOKEN_EXPIRE_DAYS`.
- Each refresh token can be spent once. Redis records spent token ids (`SET NX`, atomic) and
  revoked sessions, each key expiring with the token, so nothing needs cleaning up.
- Replaying a spent token within 10 seconds of its first use is only rejected (`401`): that is
  two tabs refreshing at once, and the winner keeps the session. Later replays revoke the whole
  session, because one of the two holders is not the real user.
- `POST /auth/logout` revokes the session of the given refresh token, including tokens rotated
  from it. It needs no access token and answers `204` even for invalid tokens. Access tokens are
  not revoked; they expire within 15 minutes.
- If Redis is unreachable, refresh and logout answer `503` (fail closed). Rate limiting fails
  open instead, because a missed limit is less harmful than accepting a revoked token.
- The SPA shares one refresh token across tabs (`localStorage`). Refreshes are serialized with
  the Web Locks API and reload the stored token first, so a tab never replays a token that
  another tab already rotated. Sign-out clears the browser at once and calls logout in the
  background.

## Columns (statuses)

- Names are trimmed, 1–50 characters, and unique **case-insensitively** (unique index on
  `lower(name)`), but stored with the casing the user typed. A duplicate returns `409`.
- `is_done` is chosen at creation and cannot be changed later. Changing it would mean backfilling
  or clearing `completed_at` for every task already in the column. More than one done column is
  allowed.
- Deleting a column that still has tasks returns `409`. Tasks are never deleted by cascade: every
  foreign key from `tasks` is `ON DELETE RESTRICT`.

## Tasks

- **Due date in the past:** `due_date` must be today or later (UTC) when a task is created and
  whenever an update *changes* it. Re-sending a stored date that has since become overdue is
  allowed, so editing the title of an overdue task still works. Violations return `422`.
- **Completion:** moving a task into an `is_done` column sets `completed_at` (creating it there
  does too). Moving it out clears `completed_at`. Moving between two done columns keeps the
  original completion time.
- `PATCH /tasks/{id}` changes only `title`, `description` and `due_date`. An omitted field is
  unchanged; `null` clears `description`/`due_date`. The column and the assignee change only
  through `POST /tasks/{id}/move` and `PUT /tasks/{id}/assignee`. Sending `status_id` or
  `assignee_id` to PATCH returns `422`.
- A blank description is stored as `null`. Descriptions are capped at 5000 characters.

## Ordering (fractional indexing)

- Columns and tasks have a float `position`. The client sends the **neighbours it sees**
  (`after_id`, `before_id`), never a raw position:
  - neither neighbour: bottom of the column (or the right end of the board);
  - `before_id` only: directly above that item;
  - `after_id` only: directly below that item;
  - both: between them; they must be adjacent.
- The server calculates the position. The first item goes at `1024`, appended items at
  `last + 1024`, the top at `first / 2`, and an item between two others at their midpoint.
- When the gap between neighbours drops below `1e-6`, the whole column is renumbered to
  `1024, 2048, …` in the same transaction.
- If a neighbour is unknown, sits in another column, is not adjacent, or is the item being moved,
  the client's view is out of date and the request returns `409`. The client should refetch the
  board.
- Concurrency: creating or moving a task locks the target column row
  (`SELECT … FOR UPDATE`); creating or reordering a column locks all column rows. Concurrent
  writers therefore cannot pick the same slot.

## Status codes for unknown ids

- An unknown id in the **path** returns `404` (`Task not found`, `Status not found`).
- An unknown `status_id` or `assignee_id` in the **body**, or an inactive assignee, returns `422`
  with a message naming the field.
- Ordering neighbours are an exception: an unknown `after_id`/`before_id` returns `409` (see above).

## Filters (`GET /tasks` and `GET /board`)

- Supported filters: `status_id`, `assignee_id`, `due_before`, `due_after`, `is_completed`,
  `search`. They combine with AND.
- `due_before`/`due_after` include the boundary date. When either is set, tasks with no due date
  are excluded. `due_after > due_before` returns `422`.
- `is_completed` means `completed_at IS NOT NULL`.
- `search` is a case-insensitive substring match on the title (`ILIKE`). `%`, `_` and `\` in
  the search term are escaped, so they match literally. A blank search is ignored.
- `GET /tasks` is paginated (`page ≥ 1`, `1 ≤ size ≤ 100`, otherwise `422`) and sorted newest
  first. A page past the end returns an empty `items` list.
- `GET /board` is not paginated. It always returns every column; filters narrow the tasks but
  never hide a column.

## GetBoard runs exactly two SQL statements

The number of statements does not depend on the number of columns or tasks; a test checks this.

```sql
SELECT statuses.id, statuses.name, statuses.position, statuses.is_done
FROM statuses ORDER BY statuses.position, statuses.id;

SELECT tasks.id, tasks.title, tasks.description, tasks.status_id, tasks.assignee_id,
       users.full_name AS assignee_name, tasks.created_by_id, tasks.due_date, tasks.position,
       tasks.completed_at, tasks.created_at, tasks.updated_at
FROM tasks LEFT OUTER JOIN users ON users.id = tasks.assignee_id
WHERE <active filters>
ORDER BY tasks.position, tasks.id;
```

Tasks are grouped into their columns in Python. The assignee's name comes from the join, so no
per-task lookups are needed.
