from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.board import BoardColumnRead, BoardRead, GetBoard
from app.application.queries.tasks import TaskRead
from app.infrastructure.models.status import StatusModel
from app.infrastructure.models.task import TaskModel
from app.infrastructure.queries.tasks import apply_filters, task_select, to_task_read


class SqlAlchemyGetBoardHandler:
    """Two statements regardless of board size: one for columns, one for all their tasks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetBoard) -> BoardRead:
        statuses_stmt = select(
            StatusModel.id, StatusModel.name, StatusModel.position, StatusModel.is_done
        ).order_by(StatusModel.position, StatusModel.id)
        statuses = (await self._session.execute(statuses_stmt)).all()

        tasks_stmt = apply_filters(task_select(), query.filters).order_by(
            TaskModel.position, TaskModel.id
        )
        tasks_by_status: defaultdict[UUID, list[TaskRead]] = defaultdict(list)
        for row in await self._session.execute(tasks_stmt):
            task = to_task_read(row)
            tasks_by_status[task.status_id].append(task)

        return BoardRead(
            columns=[
                BoardColumnRead(**row._mapping, tasks=tasks_by_status.get(row.id, []))
                for row in statuses
            ]
        )
