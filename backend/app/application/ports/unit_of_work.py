from typing import Protocol

from app.domain.repositories import StatusRepository, TaskRepository, UserRepository


class UnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...

    @property
    def statuses(self) -> StatusRepository: ...

    @property
    def tasks(self) -> TaskRepository: ...

    async def commit(self) -> None: ...
