import pytest

from app.application.commands.register_user import RegisterUser, RegisterUserHandler
from app.domain.errors import EmailAlreadyRegistered, ValidationError
from app.domain.users import Email
from tests.unit.application.fakes import (
    FIXED_NOW,
    FakePasswordHasher,
    FakeUnitOfWork,
    fixed_clock,
    make_user,
)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def handler(uow: FakeUnitOfWork) -> RegisterUserHandler:
    return RegisterUserHandler(uow=uow, hasher=FakePasswordHasher(), clock=fixed_clock)


async def test_registers_user_with_hashed_password(
    handler: RegisterUserHandler, uow: FakeUnitOfWork
) -> None:
    user_id = await handler.handle(
        RegisterUser(email=" Alice@Example.com", full_name="Alice", password="correct-horse")
    )

    user = uow.users.users[user_id]
    assert user.email == Email("alice@example.com")
    assert user.hashed_password == "hashed:correct-horse"
    assert user.is_active is True
    assert user.created_at == FIXED_NOW
    assert uow.commits == 1


async def test_rejects_duplicate_email_case_insensitively(
    handler: RegisterUserHandler, uow: FakeUnitOfWork
) -> None:
    await uow.users.add(make_user("alice@example.com"))

    with pytest.raises(EmailAlreadyRegistered):
        await handler.handle(
            RegisterUser(email="ALICE@example.com", full_name="Alice 2", password="password1")
        )
    assert uow.commits == 0


async def test_rejects_short_password(handler: RegisterUserHandler, uow: FakeUnitOfWork) -> None:
    with pytest.raises(ValidationError):
        await handler.handle(RegisterUser(email="a@example.com", full_name="A", password="short"))
    assert uow.users.users == {}
