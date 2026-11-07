from dataclasses import dataclass, field
from typing import Protocol

from app.application.queries.get_status import StatusRead
from app.application.queries.pagination import PageRequest, PageResult

DEFAULT_STATUS_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class ListStatuses(PageRequest):
    """Board columns in board order (position, then id)."""

    size: int = field(default=DEFAULT_STATUS_PAGE_SIZE)


class ListStatusesHandler(Protocol):
    async def handle(self, query: ListStatuses) -> PageResult[StatusRead]: ...
