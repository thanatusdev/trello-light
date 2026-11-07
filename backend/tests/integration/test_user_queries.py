from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.get_user import GetUserById, UserRead
from app.application.queries.list_users import ListUsers, UserSummary
from app.domain.users import Email, FullName, User
from app.infrastructure.queries.users import (
    SqlAlchemyGetUserByIdHandler,
    SqlAlchemyListUsersHandler,
)
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository

CREATED = datetime(2026, 1, 1, tzinfo=UTC)


async def _add(session: AsyncSession, email: str, name: str, *, is_active: bool = True) -> User:
    user = User.register(
        email=Email(email), full_name=FullName(name), hashed_password="h", now=CREATED
    )
    user.is_active = is_active
    await SqlAlchemyUserRepository(session).add(user)
    return user


async def test_get_user_by_id(db_session: AsyncSession) -> None:
    user = await _add(db_session, "alice@example.com", "Alice")

    result = await SqlAlchemyGetUserByIdHandler(db_session).handle(GetUserById(user.id))

    assert result == UserRead(
        id=user.id,
        email="alice@example.com",
        full_name="Alice",
        is_active=True,
        created_at=CREATED,
    )


async def test_get_user_by_id_missing(db_session: AsyncSession) -> None:
    assert await SqlAlchemyGetUserByIdHandler(db_session).handle(GetUserById(uuid4())) is None


async def test_list_users_paginates_active_users_sorted(db_session: AsyncSession) -> None:
    carol = await _add(db_session, "carol@example.com", "Carol")
    await _add(db_session, "dave@example.com", "Dave", is_active=False)
    bob = await _add(db_session, "bob@example.com", "Bob")
    alice2 = await _add(db_session, "alice2@example.com", "Alice")
    alice1 = await _add(db_session, "alice1@example.com", "Alice")
    handler = SqlAlchemyListUsersHandler(db_session)

    first = await handler.handle(ListUsers(page=1, size=2))
    last = await handler.handle(ListUsers(page=2, size=2))
    beyond = await handler.handle(ListUsers(page=3, size=2))

    def summary(u: User) -> UserSummary:
        return UserSummary(id=u.id, email=u.email.value, full_name=u.full_name.value)

    assert first.items == [summary(alice1), summary(alice2)]
    assert last.items == [summary(bob), summary(carol)]
    assert (first.total, first.page, first.size, first.pages) == (4, 1, 2, 2)
    assert beyond.items == []
    assert beyond.total == 4


async def test_list_users_empty(db_session: AsyncSession) -> None:
    page = await SqlAlchemyListUsersHandler(db_session).handle(ListUsers(page=1, size=20))

    assert (page.items, page.total, page.pages) == ([], 0, 0)
