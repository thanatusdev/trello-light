from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import EmailAlreadyRegistered
from app.domain.users import Email, FullName, User
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


def _user(email: str = "alice@example.com") -> User:
    return User.register(
        email=Email(email),
        full_name=FullName("Alice"),
        hashed_password="hashed",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )


async def test_add_and_get_by_id_and_email(db_session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(db_session)
    user = _user()

    await repo.add(user)
    db_session.expunge_all()

    by_id = await repo.get_by_id(user.id)
    by_email = await repo.get_by_email(Email("ALICE@example.com"))

    assert by_id == user
    assert by_email == user


async def test_get_returns_none_when_missing(db_session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(db_session)

    assert await repo.get_by_id(uuid4()) is None
    assert await repo.get_by_email(Email("ghost@example.com")) is None


async def test_duplicate_email_raises_domain_error(db_session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(db_session)
    await repo.add(_user())

    with pytest.raises(EmailAlreadyRegistered):
        await repo.add(_user())


async def test_session_stays_usable_after_duplicate_email(db_session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(db_session)
    await repo.add(_user())
    with pytest.raises(EmailAlreadyRegistered):
        await repo.add(_user())

    # The rejected user must not linger as pending and break the next flush/query.
    other = _user("bob@example.com")
    await repo.add(other)
    assert await repo.get_by_email(Email("bob@example.com")) == other


async def test_unit_of_work_commits(db_session: AsyncSession) -> None:
    uow = SqlAlchemyUnitOfWork(db_session)
    user = _user()

    await uow.users.add(user)
    await uow.commit()

    assert await uow.users.get_by_id(user.id) == user
