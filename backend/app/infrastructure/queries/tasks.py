from typing import Any

from sqlalchemy import Row, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.pagination import PageResult
from app.application.queries.tasks import (
    AssigneeRead,
    GetTask,
    ListTasks,
    TaskFilters,
    TaskRead,
)
from app.infrastructure.models.task import TaskModel
from app.infrastructure.models.user import UserModel


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def task_select() -> Select[Any]:
    """Columns for a TaskRead, with the assignee's name joined in (no per-task lookups)."""
    return select(
        TaskModel.id,
        TaskModel.title,
        TaskModel.description,
        TaskModel.status_id,
        TaskModel.assignee_id,
        UserModel.full_name.label("assignee_name"),
        TaskModel.created_by_id,
        TaskModel.due_date,
        TaskModel.position,
        TaskModel.completed_at,
        TaskModel.created_at,
        TaskModel.updated_at,
    ).outerjoin(UserModel, UserModel.id == TaskModel.assignee_id)


def apply_filters(stmt: Select[Any], filters: TaskFilters) -> Select[Any]:
    if filters.status_id is not None:
        stmt = stmt.where(TaskModel.status_id == filters.status_id)
    if filters.assignee_id is not None:
        stmt = stmt.where(TaskModel.assignee_id == filters.assignee_id)
    if filters.due_before is not None:
        stmt = stmt.where(TaskModel.due_date <= filters.due_before)
    if filters.due_after is not None:
        stmt = stmt.where(TaskModel.due_date >= filters.due_after)
    if filters.is_completed is not None:
        completed = TaskModel.completed_at.is_not(None)
        stmt = stmt.where(completed if filters.is_completed else ~completed)
    if filters.search:
        stmt = stmt.where(TaskModel.title.ilike(f"%{_escape_like(filters.search)}%", escape="\\"))
    return stmt


def to_task_read(row: Row[Any]) -> TaskRead:
    data = dict(row._mapping)
    assignee_id, assignee_name = data.pop("assignee_id"), data.pop("assignee_name")
    assignee = AssigneeRead(id=assignee_id, full_name=assignee_name) if assignee_id else None
    return TaskRead(**data, assignee=assignee)


class SqlAlchemyGetTaskHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetTask) -> TaskRead | None:
        stmt = task_select().where(TaskModel.id == query.task_id)
        row = (await self._session.execute(stmt)).one_or_none()
        return to_task_read(row) if row else None


class SqlAlchemyListTasksHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListTasks) -> PageResult[TaskRead]:
        count_stmt = apply_filters(select(func.count()).select_from(TaskModel), query.filters)
        total = await self._session.scalar(count_stmt) or 0
        stmt = (
            apply_filters(task_select(), query.filters)
            .order_by(TaskModel.created_at.desc(), TaskModel.id)
            .offset(query.offset)
            .limit(query.size)
        )
        rows = (await self._session.execute(stmt)).all()
        return PageResult(
            items=[to_task_read(row) for row in rows],
            total=total,
            page=query.page,
            size=query.size,
        )
