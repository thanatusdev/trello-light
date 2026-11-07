from dataclasses import dataclass
from uuid import UUID

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import TaskNotFound


@dataclass(frozen=True, slots=True)
class DeleteTask:
    task_id: UUID


class DeleteTaskHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: DeleteTask) -> None:
        if await self._uow.tasks.get_for_update(command.task_id) is None:
            raise TaskNotFound()
        await self._uow.tasks.delete(command.task_id)
        await self._uow.commit()
