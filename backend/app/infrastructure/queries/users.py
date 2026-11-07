from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.get_user import GetUserById, UserRead
from app.application.queries.list_users import ListUsers, UserSummary
from app.application.queries.pagination import PageResult
from app.infrastructure.models.user import UserModel


class SqlAlchemyGetUserByIdHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetUserById) -> UserRead | None:
        stmt = select(
            UserModel.id,
            UserModel.email,
            UserModel.full_name,
            UserModel.is_active,
            UserModel.created_at,
        ).where(UserModel.id == query.user_id)
        row = (await self._session.execute(stmt)).one_or_none()
        return UserRead(**row._mapping) if row else None


class SqlAlchemyListUsersHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListUsers) -> PageResult[UserSummary]:
        active = UserModel.is_active.is_(True)
        total = (
            await self._session.scalar(select(func.count()).select_from(UserModel).where(active))
            or 0
        )
        stmt = (
            select(UserModel.id, UserModel.email, UserModel.full_name)
            .where(active)
            .order_by(UserModel.full_name, UserModel.email)
            .offset(query.offset)
            .limit(query.size)
        )
        rows = (await self._session.execute(stmt)).all()
        return PageResult(
            items=[UserSummary(**row._mapping) for row in rows],
            total=total,
            page=query.page,
            size=query.size,
        )
