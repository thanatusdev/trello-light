from dataclasses import dataclass
from uuid import UUID

from app.application.ports.clock import Clock
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import StaleOrdering, TaskNotFound, UnknownStatus
from app.domain.ordering import place
from app.domain.statuses import Status


@dataclass(frozen=True, slots=True)
class MoveTask:
    """Put a task in ``status_id`` between ``after_id`` and ``before_id`` (both optional).

    With no neighbours the task goes to the bottom of the column.
    """

    task_id: UUID
    status_id: UUID
    after_id: UUID | None = None
    before_id: UUID | None = None


class MoveTaskHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def handle(self, command: MoveTask) -> None:
        # Unlocked read, only to learn the source column.
        current = await self._uow.tasks.get(command.task_id)
        if current is None:
            raise TaskNotFound()

        # Lock order (domain/repositories.py): column rows in id order, then the task row.
        # Locking the target stops concurrent moves into it picking the same slot; locking
        # the source too means a task leaving the column can't race with its rebalance.
        status = await self._lock_columns(current.status_id, command.status_id)
        task = await self._uow.tasks.get_for_update(command.task_id)
        if task is None:
            raise TaskNotFound()
        if task.status_id != current.status_id:
            # Moved by someone else before we locked it; the client's board is out of date.
            raise StaleOrdering()

        placement = place(
            await self._uow.tasks.list_positions(status.id),
            task.id,
            after_id=command.after_id,
            before_id=command.before_id,
        )
        if placement.rebalanced:
            await self._uow.tasks.set_positions(status.id, placement.rebalanced)
        task.move_to(status, position=placement.position, now=self._clock())
        await self._uow.tasks.save(task)
        await self._uow.commit()

    async def _lock_columns(self, source_id: UUID, target_id: UUID) -> Status:
        target: Status | None = None
        for status_id in sorted({source_id, target_id}):
            locked = await self._uow.statuses.get_for_update(status_id)
            if status_id == target_id:
                target = locked
        if target is None:
            raise UnknownStatus()
        return target
