"""add task list indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-07 12:00:00.000000+00:00

- ``ix_tasks_created_at_desc_id``: matches the ``ORDER BY created_at DESC, id`` of
  ``GET /tasks``, so a page is read in index order instead of sorting every task.
- ``ix_tasks_due_date``: range scans for the ``due_before``/``due_after`` filters and the
  daily due-soon digest (``due_date BETWEEN ...``).

``completed_at`` is only ever filtered as ``IS NULL``/``IS NOT NULL`` (``is_completed``),
which typically matches a large share of the table, so a B-tree index would rarely be
used there; none is added.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_tasks_created_at_desc_id",
        "tasks",
        [sa.literal_column("created_at DESC"), "id"],
        unique=False,
    )
    op.create_index("ix_tasks_due_date", "tasks", ["due_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tasks_due_date", table_name="tasks")
    op.drop_index("ix_tasks_created_at_desc_id", table_name="tasks")
