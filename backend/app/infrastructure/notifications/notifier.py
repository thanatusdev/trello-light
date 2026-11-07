import asyncio
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

type Enqueue = Callable[[str, str, str], Any]


def _enqueue_task_assigned(task_id: str, assignee_id: str, assigned_by_id: str) -> Any:
    # Imported lazily so the API process does not build the Celery app until it needs it.
    from app.infrastructure.tasks import send_task_assigned

    return send_task_assigned.delay(task_id, assignee_id, assigned_by_id)


class CeleryNotifier:
    """Queues a Celery task per notification. Only ids go on the queue; the worker reads
    the current task and user data when it sends."""

    def __init__(self, enqueue: Enqueue = _enqueue_task_assigned) -> None:
        self._enqueue = enqueue

    async def task_assigned(
        self, *, task_id: UUID, assignee_id: UUID, assigned_by_id: UUID
    ) -> None:
        try:
            # .delay() is blocking network I/O to the broker.
            await asyncio.to_thread(
                self._enqueue, str(task_id), str(assignee_id), str(assigned_by_id)
            )
        except Exception:
            # The assignment is already committed; a lost notification must not fail it.
            logger.exception("Could not queue assignment notification for task %s", task_id)


class NullNotifier:
    """Sends nothing. Used by the seed script."""

    async def task_assigned(
        self, *, task_id: UUID, assignee_id: UUID, assigned_by_id: UUID
    ) -> None:
        return None
