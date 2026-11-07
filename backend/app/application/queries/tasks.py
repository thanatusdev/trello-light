from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.application.queries.pagination import PageRequest, PageResult
from app.domain.errors import InvalidDueDateRange


@dataclass(frozen=True, slots=True)
class TaskFilters:
    """Shared by ListTasks and GetBoard. Every filter is optional and they combine with AND.

    Due-date bounds are inclusive; when either is set, tasks without a due date are excluded.
    ``search`` is a case-insensitive substring match on the title; blank means no filter.
    """

    status_id: UUID | None = None
    assignee_id: UUID | None = None
    due_before: date | None = None
    due_after: date | None = None
    is_completed: bool | None = None
    search: str | None = None

    def __post_init__(self) -> None:
        if self.due_before and self.due_after and self.due_after > self.due_before:
            raise InvalidDueDateRange()
        search = self.search.strip() if self.search else None
        object.__setattr__(self, "search", search or None)


@dataclass(frozen=True, slots=True)
class AssigneeRead:
    id: UUID
    full_name: str


@dataclass(frozen=True, slots=True)
class TaskRead:
    id: UUID
    title: str
    description: str | None
    status_id: UUID
    assignee: AssigneeRead | None
    created_by_id: UUID
    due_date: date | None
    position: float
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class GetTask:
    task_id: UUID


@dataclass(frozen=True, slots=True)
class ListTasks(PageRequest):
    """Filtered tasks, newest first."""

    filters: TaskFilters = field(default_factory=TaskFilters)


class GetTaskHandler(Protocol):
    async def handle(self, query: GetTask) -> TaskRead | None: ...


class ListTasksHandler(Protocol):
    async def handle(self, query: ListTasks) -> PageResult[TaskRead]: ...
