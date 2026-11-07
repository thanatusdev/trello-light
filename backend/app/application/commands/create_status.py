from dataclasses import dataclass
from uuid import UUID

from app.application.ports.clock import Clock
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import StatusNameTaken
from app.domain.ordering import position_between
from app.domain.statuses import Status, StatusName


@dataclass(frozen=True, slots=True)
class CreateStatus:
    name: str
    is_done: bool = False


class CreateStatusHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def handle(self, command: CreateStatus) -> UUID:
        name = StatusName(command.name)
        # The board lock serialises concurrent creates/reorders (even on an empty board);
        # the list is read after taking it, so it includes columns committed meanwhile.
        await self._uow.statuses.lock_board()
        statuses = await self._uow.statuses.list_for_update()
        if any(s.name.matches(name) for s in statuses):
            raise StatusNameTaken()

        last = statuses[-1].position if statuses else None
        position = position_between(last, None)
        assert position is not None  # noqa: S101 - appending never needs a rebalance
        status = Status.create(
            name=name, is_done=command.is_done, position=position, now=self._clock()
        )
        await self._uow.statuses.add(status)
        await self._uow.commit()
        return status.id
