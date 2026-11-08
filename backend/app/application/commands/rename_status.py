from dataclasses import dataclass
from uuid import UUID

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import StatusNameTaken, StatusNotFound
from app.domain.statuses import StatusName


@dataclass(frozen=True, slots=True)
class RenameStatus:
    status_id: UUID
    name: str


class RenameStatusHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: RenameStatus) -> None:
        name = StatusName(command.name)
        # Locked: ``save`` writes the position back too, so an unlocked read could undo a
        # concurrent reorder or rebalance of this column.
        status = await self._uow.statuses.get_for_update(command.status_id)
        if status is None:
            raise StatusNotFound()

        existing = await self._uow.statuses.get_by_name(name)
        if existing is not None and existing.id != status.id:
            raise StatusNameTaken()

        status.rename(name)
        await self._uow.statuses.save(status)
        await self._uow.commit()
