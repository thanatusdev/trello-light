from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final, Literal
from uuid import UUID

from app.application.ports.clock import Clock
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import TaskNotFound
from app.domain.tasks import TaskDescription, TaskTitle


class _Unset(Enum):
    UNSET = "UNSET"


# Distinguishes "field not sent" from an explicit ``None`` (which clears the field).
UNSET: Final = _Unset.UNSET
type Unset = Literal[_Unset.UNSET]


@dataclass(frozen=True, slots=True)
class UpdateTask:
    task_id: UUID
    title: str | Unset = UNSET
    description: str | Unset | None = UNSET
    due_date: date | Unset | None = UNSET


class UpdateTaskHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def handle(self, command: UpdateTask) -> None:
        task = await self._uow.tasks.get_for_update(command.task_id)
        if task is None:
            raise TaskNotFound()

        now = self._clock()
        if command.title is not UNSET:
            task.rename(TaskTitle(command.title), now=now)
        if command.description is not UNSET:
            task.describe(TaskDescription.from_raw(command.description), now=now)
        if command.due_date is not UNSET:
            task.reschedule(command.due_date, now=now)

        await self._uow.tasks.save(task)
        await self._uow.commit()
