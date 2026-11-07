"""create statuses and tasks

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07 01:07:28.098325+00:00

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Default board so a fresh install is usable straight away: (name, position, is_done).
DEFAULT_STATUSES = [("To Do", 1024.0, False), ("In Progress", 2048.0, False), ("Done", 3072.0, True)]


def upgrade() -> None:
    statuses = op.create_table(
        "statuses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("position", sa.Float(), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_statuses")),
    )
    op.create_index(
        "uq_statuses_name_lower", "statuses", [sa.literal_column("lower(name)")], unique=True
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status_id", sa.Uuid(), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("position", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assignee_id"],
            ["users.id"],
            name=op.f("fk_tasks_assignee_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_tasks_created_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["status_id"],
            ["statuses.id"],
            name=op.f("fk_tasks_status_id_statuses"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_assignee_id"), "tasks", ["assignee_id"], unique=False)
    op.create_index("ix_tasks_status_id_position", "tasks", ["status_id", "position"], unique=False)

    now = datetime.now(UTC)
    op.bulk_insert(
        statuses,
        [
            {"id": uuid.uuid4(), "name": name, "position": pos, "is_done": done, "created_at": now}
            for name, pos, done in DEFAULT_STATUSES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_status_id_position", table_name="tasks")
    op.drop_index(op.f("ix_tasks_assignee_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("uq_statuses_name_lower", table_name="statuses")
    op.drop_table("statuses")
