from uuid import UUID

from app.application.ports.notifier import Notifier
from app.domain.errors import InvalidAssignee
from app.domain.repositories import UserRepository


async def ensure_assignable(users: UserRepository, assignee_id: UUID | None) -> None:
    """``None`` means unassigned; anything else must be an existing, active user."""
    if assignee_id is None:
        return
    user = await users.get_by_id(assignee_id)
    if user is None or not user.is_active:
        raise InvalidAssignee()


async def notify_assignment(
    notifier: Notifier, *, task_id: UUID, assignee_id: UUID | None, assigned_by_id: UUID
) -> None:
    """Call only after commit. Nobody is told about unassigning or assigning themselves."""
    if assignee_id is None or assignee_id == assigned_by_id:
        return
    await notifier.task_assigned(
        task_id=task_id, assignee_id=assignee_id, assigned_by_id=assigned_by_id
    )
