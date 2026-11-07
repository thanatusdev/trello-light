from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import EmailAlreadyRegistered
from app.domain.users import Email, FullName, User
from app.infrastructure.models.user import UserModel


def _to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        email=Email(model.email),
        full_name=FullName(model.full_name),
        hashed_password=model.hashed_password,
        is_active=model.is_active,
        created_at=model.created_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        model = UserModel(
            id=user.id,
            email=user.email.value,
            full_name=user.full_name.value,
            hashed_password=user.hashed_password,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        # Flush now so a concurrent registration racing past the handler's existence
        # check surfaces as a domain error rather than a 500 at commit time. Adding inside
        # the savepoint means a failed insert is expunged on rollback instead of lingering.
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as exc:
            raise EmailAlreadyRegistered() from exc

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_entity(model) if model else None

    async def get_by_email(self, email: Email) -> User | None:
        model = await self._session.scalar(select(UserModel).where(UserModel.email == email.value))
        return _to_entity(model) if model else None
