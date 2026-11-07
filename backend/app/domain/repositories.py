from collections.abc import Mapping
from typing import Protocol
from uuid import UUID

from app.domain.statuses import Status, StatusName
from app.domain.tasks import Task
from app.domain.users import Email, User

# Lock order. Every write transaction takes its locks in this order, so no two can wait on
# each other in a cycle (deadlock):
#   1. the board lock (``StatusRepository.lock_board``) - only column create/reorder;
#   2. status rows, in ascending id order (``list_for_update`` locks all of them that way;
#      a task move locks its source and target columns that way);
#   3. the task row (``TaskRepository.get_for_update``), then rows it rebalances.
# Commands that lock only a task row (update, assign, delete) never wait for a status row
# afterwards, so they cannot close a cycle with a move holding status rows.


class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...


class StatusRepository(Protocol):
    async def add(self, status: Status) -> None: ...

    async def get(self, status_id: UUID) -> Status | None: ...

    async def lock_board(self) -> None:
        """Serialise changes to the set of columns and their order, until commit.

        Row locks alone can't do this: a concurrently inserted column is not locked by
        ``list_for_update``, and an empty board has no rows to lock. Re-read the columns
        after taking it.
        """
        ...

    async def get_for_update(self, status_id: UUID) -> Status | None:
        """Load and lock the status, serialising concurrent writes to its column."""
        ...

    async def get_by_name(self, name: StatusName) -> Status | None:
        """Case-insensitive lookup."""
        ...

    async def list_for_update(self) -> list[Status]:
        """All statuses ordered by position, locked (in id order) for reordering."""
        ...

    async def save(self, status: Status) -> None: ...

    async def set_positions(self, positions: Mapping[UUID, float]) -> None: ...

    async def has_tasks(self, status_id: UUID) -> bool: ...

    async def delete(self, status_id: UUID) -> None: ...


class TaskRepository(Protocol):
    async def add(self, task: Task) -> None: ...

    async def get(self, task_id: UUID) -> Task | None: ...

    async def get_for_update(self, task_id: UUID) -> Task | None:
        """Load and lock the task until commit, so a read-modify-save can't lose a
        concurrent change (``save`` writes every mutable field)."""
        ...

    async def save(self, task: Task) -> None: ...

    async def delete(self, task_id: UUID) -> None: ...

    async def list_positions(self, status_id: UUID) -> list[tuple[UUID, float]]:
        """``(task_id, position)`` for every task in the column, ordered by position."""
        ...

    async def set_positions(self, status_id: UUID, positions: Mapping[UUID, float]) -> None:
        """Renumber tasks of column ``status_id``; a task no longer in it is left alone."""
        ...
