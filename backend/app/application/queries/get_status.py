from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GetStatus:
    status_id: UUID


@dataclass(frozen=True, slots=True)
class StatusRead:
    id: UUID
    name: str
    position: float
    is_done: bool
    created_at: datetime


class GetStatusHandler(Protocol):
    async def handle(self, query: GetStatus) -> StatusRead | None: ...
