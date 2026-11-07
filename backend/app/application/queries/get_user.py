from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class GetUserById:
    user_id: UUID


@dataclass(frozen=True, slots=True)
class UserRead:
    id: UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class GetUserByIdHandler(Protocol):
    async def handle(self, query: GetUserById) -> UserRead | None: ...
