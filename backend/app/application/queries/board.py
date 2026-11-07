from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.application.queries.tasks import TaskFilters, TaskRead


@dataclass(frozen=True, slots=True)
class GetBoard:
    """Every column, each with its (filtered) tasks. Columns are never filtered out."""

    filters: TaskFilters = field(default_factory=TaskFilters)


@dataclass(frozen=True, slots=True)
class BoardColumnRead:
    id: UUID
    name: str
    position: float
    is_done: bool
    tasks: list[TaskRead]


@dataclass(frozen=True, slots=True)
class BoardRead:
    columns: list[BoardColumnRead]


class GetBoardHandler(Protocol):
    async def handle(self, query: GetBoard) -> BoardRead: ...
