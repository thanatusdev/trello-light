from dataclasses import dataclass
from uuid import UUID

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import StatusHasTasks, StatusNotFound


@dataclass(frozen=True, slots=True)
class DeleteStatus:
    status_id: UUID


class DeleteStatusHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: DeleteStatus) -> None:
        # The lock stops a task being created/moved into the column between check and delete.
        status = await self._uow.statuses.get_for_update(command.status_id)
        if status is None:
            raise StatusNotFound()
        if await self._uow.statuses.has_tasks(status.id):
            raise StatusHasTasks()

        await self._uow.statuses.delete(status.id)
        await self._uow.commit()
