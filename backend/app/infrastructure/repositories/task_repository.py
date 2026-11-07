from collections.abc import Mapping
from typing import cast
from uuid import UUID

from sqlalchemy import Table, bindparam, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tasks import Task, TaskDescription, TaskTitle
from app.infrastructure.models.task import TaskModel


def _to_entity(model: TaskModel) -> Task:
    return Task(
        id=model.id,
        title=TaskTitle(model.title),
        description=TaskDescription(model.description) if model.description else None,
        status_id=model.status_id,
        assignee_id=model.assignee_id,
        created_by_id=model.created_by_id,
        due_date=model.due_date,
        position=model.position,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _mutable_fields(task: Task) -> dict[str, object]:
    return {
        "title": task.title.value,
        "description": task.description.value if task.description else None,
        "status_id": task.status_id,
        "assignee_id": task.assignee_id,
        "due_date": task.due_date,
        "position": task.position,
        "completed_at": task.completed_at,
        "updated_at": task.updated_at,
    }


class SqlAlchemyTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, task: Task) -> None:
        self._session.add(
            TaskModel(
                id=task.id,
                created_by_id=task.created_by_id,
                created_at=task.created_at,
                **_mutable_fields(task),
            )
        )
        await self._session.flush()

    async def get(self, task_id: UUID) -> Task | None:
        model = await self._session.get(TaskModel, task_id)
        return _to_entity(model) if model else None

    async def get_for_update(self, task_id: UUID) -> Task | None:
        stmt = (
            select(TaskModel)
            .where(TaskModel.id == task_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = await self._session.scalar(stmt)
        return _to_entity(model) if model else None

    async def save(self, task: Task) -> None:
        await self._session.execute(
            update(TaskModel).where(TaskModel.id == task.id).values(**_mutable_fields(task))
        )

    async def delete(self, task_id: UUID) -> None:
        await self._session.execute(delete(TaskModel).where(TaskModel.id == task_id))

    async def list_positions(self, status_id: UUID) -> list[tuple[UUID, float]]:
        stmt = (
            select(TaskModel.id, TaskModel.position)
            .where(TaskModel.status_id == status_id)
            .order_by(TaskModel.position, TaskModel.id)
        )
        return [(row.id, row.position) for row in await self._session.execute(stmt)]

    async def set_positions(self, status_id: UUID, positions: Mapping[UUID, float]) -> None:
        if not positions:
            return
        # Core UPDATE (not ORM bulk-by-primary-key) so the extra status_id condition applies.
        table = cast(Table, TaskModel.__table__)
        stmt = (
            update(table)
            .where(table.c.id == bindparam("task_id"), table.c.status_id == status_id)
            .values(position=bindparam("new_position"))
        )
        await self._session.execute(
            stmt,
            [{"task_id": task_id, "new_position": pos} for task_id, pos in positions.items()],
        )
