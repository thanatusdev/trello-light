from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.status_repository import SqlAlchemyStatusRepository
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.users = SqlAlchemyUserRepository(session)
        self.statuses = SqlAlchemyStatusRepository(session)
        self.tasks = SqlAlchemyTaskRepository(session)

    async def commit(self) -> None:
        await self._session.commit()
