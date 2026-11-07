from dataclasses import dataclass
from uuid import UUID

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import StatusNotFound
from app.domain.ordering import place


@dataclass(frozen=True, slots=True)
class ReorderStatus:
    """Move a column so it sits between ``after_id`` and ``before_id`` (both optional)."""

    status_id: UUID
    after_id: UUID | None = None
    before_id: UUID | None = None


class ReorderStatusHandler:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def handle(self, command: ReorderStatus) -> None:
        await self._uow.statuses.lock_board()
        statuses = await self._uow.statuses.list_for_update()
        status = next((s for s in statuses if s.id == command.status_id), None)
        if status is None:
            raise StatusNotFound()

        placement = place(
            [(s.id, s.position) for s in statuses],
            status.id,
            after_id=command.after_id,
            before_id=command.before_id,
        )
        if placement.rebalanced:
            await self._uow.statuses.set_positions(placement.rebalanced)
        status.position = placement.position
        await self._uow.statuses.save(status)
        await self._uow.commit()
