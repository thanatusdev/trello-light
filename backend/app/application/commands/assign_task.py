from dataclasses import dataclass
from uuid import UUID

from app.application.commands._assignees import ensure_assignable, notify_assignment
from app.application.ports.clock import Clock
from app.application.ports.notifier import Notifier
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import TaskNotFound


@dataclass(frozen=True, slots=True)
class AssignTask:
    task_id: UUID
    assignee_id: UUID | None  # None unassigns
    assigned_by_id: UUID


class AssignTaskHandler:
    def __init__(self, uow: UnitOfWork, clock: Clock, notifier: Notifier) -> None:
        self._uow = uow
        self._clock = clock
        self._notifier = notifier

    async def handle(self, command: AssignTask) -> None:
        task = await self._uow.tasks.get_for_update(command.task_id)
        if task is None:
            raise TaskNotFound()
        await ensure_assignable(self._uow.users, command.assignee_id)

        changed = task.assign(command.assignee_id, now=self._clock())
        await self._uow.tasks.save(task)
        await self._uow.commit()

        if changed:
            await notify_assignment(
                self._notifier,
                task_id=task.id,
                assignee_id=task.assignee_id,
                assigned_by_id=command.assigned_by_id,
            )
