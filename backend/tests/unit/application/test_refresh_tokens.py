from datetime import timedelta
from uuid import uuid4

import pytest
from app.application.commands.logout import Logout, LogoutHandler

from app.application.commands.refresh_tokens import (
    REUSE_GRACE,
    RefreshTokens,
    RefreshTokensHandler,
)
from app.domain.errors import InvalidToken, TokenStoreUnavailable
from app.domain.users import User
from tests.unit.application.fakes import (
    FIXED_NOW,
    FakeRefreshTokenStore,
    FakeTokenService,
    FakeUnitOfWork,
    MutableClock,
    make_user,
)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def tokens() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def store() -> FakeRefreshTokenStore:
    return FakeRefreshTokenStore()


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock(FIXED_NOW)


@pytest.fixture
def handler(
    uow: FakeUnitOfWork, tokens: FakeTokenService, store: FakeRefreshTokenStore, clock: MutableClock
) -> RefreshTokensHandler:
    return RefreshTokensHandler(uow=uow, tokens=tokens, store=store, clock=clock)


@pytest.fixture
async def user(uow: FakeUnitOfWork) -> User:
    user = make_user()
    await uow.users.add(user)
    return user


async def _refresh(handler: RefreshTokensHandler, token: str) -> str:
    return (await handler.handle(RefreshTokens(refresh_token=token))).refresh_token


async def test_refresh_rotates_within_the_same_session_and_expiry(
    handler: RefreshTokensHandler, tokens: FakeTokenService, user: User
) -> None:
    login = tokens.issue_pair(user.id)

    pair = await handler.handle(RefreshTokens(refresh_token=login.refresh_token))

    old, new = tokens.claims[login.refresh_token], tokens.claims[pair.refresh_token]
    assert pair.access_token == f"access:{user.id}"
    assert new.token_id != old.token_id
    assert (new.session_id, new.expires_at) == (old.session_id, old.expires_at)


async def test_rotated_token_works_and_the_chain_continues(
    handler: RefreshTokensHandler, tokens: FakeTokenService, user: User
) -> None:
    first = tokens.issue_pair(user.id).refresh_token

    second = await _refresh(handler, first)
    third = await _refresh(handler, second)

    assert third not in (first, second)


async def test_reuse_within_grace_is_rejected_without_ending_the_session(
    handler: RefreshTokensHandler,
    tokens: FakeTokenService,
    store: FakeRefreshTokenStore,
    clock: MutableClock,
    user: User,
) -> None:
    login = tokens.issue_pair(user.id).refresh_token
    rotated = await _refresh(handler, login)
    clock.now += REUSE_GRACE  # still inside the grace window

    with pytest.raises(InvalidToken):
        await _refresh(handler, login)

    assert store.revoked == {}
    assert await _refresh(handler, rotated)  # the winner of the race keeps the session


async def test_reuse_after_grace_revokes_the_whole_session(
    handler: RefreshTokensHandler,
    tokens: FakeTokenService,
    store: FakeRefreshTokenStore,
    clock: MutableClock,
    user: User,
) -> None:
    login = tokens.issue_pair(user.id).refresh_token
    rotated = await _refresh(handler, login)
    clock.now += REUSE_GRACE + timedelta(seconds=1)

    with pytest.raises(InvalidToken):
        await _refresh(handler, login)

    session = tokens.claims[login].session_id
    assert store.revoked == {session: tokens.claims[login].expires_at}
    with pytest.raises(InvalidToken):  # the legitimate holder is signed out too
        await _refresh(handler, rotated)


async def test_other_sessions_are_unaffected_by_a_revocation(
    handler: RefreshTokensHandler,
    tokens: FakeTokenService,
    clock: MutableClock,
    user: User,
) -> None:
    stolen = tokens.issue_pair(user.id).refresh_token
    other_device = tokens.issue_pair(user.id).refresh_token
    await _refresh(handler, stolen)
    clock.now += REUSE_GRACE * 2
    with pytest.raises(InvalidToken):
        await _refresh(handler, stolen)

    assert await _refresh(handler, other_device)


async def test_used_tokens_are_remembered_until_they_expire(
    handler: RefreshTokensHandler,
    tokens: FakeTokenService,
    store: FakeRefreshTokenStore,
    user: User,
) -> None:
    login = tokens.issue_pair(user.id).refresh_token

    await _refresh(handler, login)

    claims = tokens.claims[login]
    assert store.used[claims.token_id] == (FIXED_NOW, claims.expires_at)


async def test_rejects_access_token(handler: RefreshTokensHandler, user: User) -> None:
    with pytest.raises(InvalidToken):
        await _refresh(handler, f"access:{user.id}")


async def test_rejects_unknown_user(
    handler: RefreshTokensHandler, tokens: FakeTokenService
) -> None:
    with pytest.raises(InvalidToken):
        await _refresh(handler, tokens.issue_pair(uuid4()).refresh_token)


async def test_rejects_inactive_user(
    handler: RefreshTokensHandler, tokens: FakeTokenService, uow: FakeUnitOfWork
) -> None:
    user = make_user(is_active=False)
    await uow.users.add(user)

    with pytest.raises(InvalidToken):
        await _refresh(handler, tokens.issue_pair(user.id).refresh_token)


async def test_store_outage_fails_closed(
    handler: RefreshTokensHandler,
    tokens: FakeTokenService,
    store: FakeRefreshTokenStore,
    user: User,
) -> None:
    store.available = False

    with pytest.raises(TokenStoreUnavailable):
        await _refresh(handler, tokens.issue_pair(user.id).refresh_token)


# --- Logout ---------------------------------------------------------------------


async def test_logout_revokes_the_session_including_rotated_tokens(
    handler: RefreshTokensHandler,
    tokens: FakeTokenService,
    store: FakeRefreshTokenStore,
    user: User,
) -> None:
    login = tokens.issue_pair(user.id).refresh_token
    rotated = await _refresh(handler, login)

    await LogoutHandler(tokens=tokens, store=store).handle(Logout(refresh_token=rotated))

    with pytest.raises(InvalidToken):
        await _refresh(handler, rotated)


async def test_logout_is_idempotent(
    tokens: FakeTokenService, store: FakeRefreshTokenStore, user: User
) -> None:
    token = tokens.issue_pair(user.id).refresh_token
    logout = LogoutHandler(tokens=tokens, store=store)

    await logout.handle(Logout(refresh_token=token))
    await logout.handle(Logout(refresh_token=token))

    assert list(store.revoked) == [tokens.claims[token].session_id]


async def test_logout_with_invalid_token_does_nothing(
    tokens: FakeTokenService, store: FakeRefreshTokenStore
) -> None:
    await LogoutHandler(tokens=tokens, store=store).handle(Logout(refresh_token="garbage"))

    assert store.revoked == {}
