from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.application.queries.pagination import PageRequest, PageResult


@dataclass(frozen=True, slots=True)
class ListUsers(PageRequest):
    """Active users ordered by name, e.g. for the assignee picker."""


@dataclass(frozen=True, slots=True)
class UserSummary:
    id: UUID
    email: str
    full_name: str


class ListUsersHandler(Protocol):
    async def handle(self, query: ListUsers) -> PageResult[UserSummary]: ...
