import pytest

from app.application.commands.authenticate import Authenticate, AuthenticateHandler
from app.domain.errors import InvalidCredentials
from tests.unit.application.fakes import (
    FakePasswordHasher,
    FakeTokenService,
    FakeUnitOfWork,
    make_user,
)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def tokens() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def handler(
    uow: FakeUnitOfWork, hasher: FakePasswordHasher, tokens: FakeTokenService
) -> AuthenticateHandler:
    return AuthenticateHandler(uow=uow, hasher=hasher, tokens=tokens)


async def test_returns_token_pair_for_valid_credentials(
    handler: AuthenticateHandler, uow: FakeUnitOfWork, tokens: FakeTokenService
) -> None:
    user = make_user("alice@example.com", "correct-horse")
    await uow.users.add(user)

    pair = await handler.handle(Authenticate(email="ALICE@example.com", password="correct-horse"))

    assert pair.access_token == f"access:{user.id}"
    assert tokens.claims[pair.refresh_token].user_id == user.id


async def test_wrong_password_is_rejected(
    handler: AuthenticateHandler, uow: FakeUnitOfWork
) -> None:
    await uow.users.add(make_user("alice@example.com", "correct-horse"))

    with pytest.raises(InvalidCredentials):
        await handler.handle(Authenticate(email="alice@example.com", password="wrong-horse"))


async def test_unknown_email_is_rejected_after_dummy_verify(
    handler: AuthenticateHandler, hasher: FakePasswordHasher
) -> None:
    with pytest.raises(InvalidCredentials):
        await handler.handle(Authenticate(email="nobody@example.com", password="whatever1"))
    assert hasher.dummy_calls == 1


async def test_malformed_email_is_rejected_as_invalid_credentials(
    handler: AuthenticateHandler, hasher: FakePasswordHasher
) -> None:
    with pytest.raises(InvalidCredentials):
        await handler.handle(Authenticate(email="not-an-email", password="whatever1"))
    assert hasher.dummy_calls == 1


async def test_inactive_user_is_rejected_even_with_correct_password(
    handler: AuthenticateHandler, uow: FakeUnitOfWork
) -> None:
    await uow.users.add(make_user("alice@example.com", "correct-horse", is_active=False))

    with pytest.raises(InvalidCredentials):
        await handler.handle(Authenticate(email="alice@example.com", password="correct-horse"))
