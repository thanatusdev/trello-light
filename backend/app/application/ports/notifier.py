from typing import Protocol
from uuid import UUID


class Notifier(Protocol):
    """Tells users about things that happened to them.

    Handlers call it only after the unit of work has committed, so nobody is told
    about a change that was rolled back. Implementations must not raise: by the
    time they run, the change is already saved.
    """

    async def task_assigned(
        self, *, task_id: UUID, assignee_id: UUID, assigned_by_id: UUID
    ) -> None: ...
