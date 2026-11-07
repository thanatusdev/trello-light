from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.application.commands._assignees import ensure_assignable, notify_assignment
from app.application.ports.clock import Clock
from app.application.ports.notifier import Notifier
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import UnknownStatus
from app.domain.ordering import position_between
from app.domain.tasks import Task, TaskDescription, TaskTitle


@dataclass(frozen=True, slots=True)
class CreateTask:
    title: str
    status_id: UUID
    created_by_id: UUID
    description: str | None = None
    assignee_id: UUID | None = None
    due_date: date | None = None


class CreateTaskHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock, notifier: Notifier) -> None:
        self._uow = uow
        self._clock = clock
        self._notifier = notifier

    async def handle(self, command: CreateTask) -> UUID:
        title = TaskTitle(command.title)
        description = TaskDescription.from_raw(command.description)

        status = await self._uow.statuses.get_for_update(command.status_id)
        if status is None:
            raise UnknownStatus()
        await ensure_assignable(self._uow.users, command.assignee_id)

        column = await self._uow.tasks.list_positions(status.id)
        position = position_between(column[-1][1] if column else None, None)
        assert position is not None  # noqa: S101 - appending never needs a rebalance

        task = Task.create(
            title=title,
            description=description,
            status=status,
            position=position,
            created_by_id=command.created_by_id,
            assignee_id=command.assignee_id,
            due_date=command.due_date,
            now=self._clock(),
        )
        await self._uow.tasks.add(task)
        await self._uow.commit()

        await notify_assignment(
            self._notifier,
            task_id=task.id,
            assignee_id=task.assignee_id,
            assigned_by_id=command.created_by_id,
        )
        return task.id
