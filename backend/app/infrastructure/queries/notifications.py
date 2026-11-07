"""Reads for the notification jobs. Run in the Celery worker, not behind the API."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.infrastructure.models.task import TaskModel
from app.infrastructure.models.user import UserModel


@dataclass(frozen=True, slots=True)
class AssignmentDetails:
    task_title: str
    due_date: date | None
    assignee_email: str
    assignee_name: str
    assigned_by_name: str | None


@dataclass(frozen=True, slots=True)
class DueSoonTask:
    assignee_email: str
    assignee_name: str
    title: str
    due_date: date


async def get_assignment_details(
    session: AsyncSession, *, task_id: UUID, assignee_id: UUID, assigned_by_id: UUID
) -> AssignmentDetails | None:
    """``None`` if the task is gone, now has someone else, or the assignee is inactive."""
    assignee = aliased(UserModel)
    assigner = aliased(UserModel)
    stmt = (
        select(
            TaskModel.title.label("task_title"),
            TaskModel.due_date,
            assignee.email.label("assignee_email"),
            assignee.full_name.label("assignee_name"),
            assigner.full_name.label("assigned_by_name"),
        )
        .join(assignee, assignee.id == TaskModel.assignee_id)
        .outerjoin(assigner, assigner.id == assigned_by_id)
        .where(
            TaskModel.id == task_id,
            TaskModel.assignee_id == assignee_id,
            assignee.is_active.is_(True),
        )
    )
    row = (await session.execute(stmt)).one_or_none()
    return AssignmentDetails(**row._mapping) if row else None


async def list_due_soon(session: AsyncSession, *, start: date, end: date) -> list[DueSoonTask]:
    """Open, assigned tasks due in ``[start, end]``, grouped by assignee, soonest first."""
    stmt = (
        select(
            UserModel.email.label("assignee_email"),
            UserModel.full_name.label("assignee_name"),
            TaskModel.title,
            TaskModel.due_date,
        )
        .join(UserModel, UserModel.id == TaskModel.assignee_id)
        .where(
            TaskModel.due_date.between(start, end),
            TaskModel.completed_at.is_(None),
            UserModel.is_active.is_(True),
        )
        .order_by(UserModel.email, TaskModel.due_date, TaskModel.title)
    )
    rows = (await session.execute(stmt)).all()
    return [DueSoonTask(**row._mapping) for row in rows]
