import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff

from app.domain.errors import TokenStoreUnavailable
from app.infrastructure.security.redis_refresh_token_store import (
    REVOKED_PREFIX,
    USED_PREFIX,
    RedisRefreshTokenStore,
)


@pytest.fixture
def store(redis_client: Redis) -> RedisRefreshTokenStore:
    return RedisRefreshTokenStore(redis_client)


def _in(delta: timedelta) -> datetime:
    return datetime.now(UTC) + delta


async def test_first_use_is_recorded_and_later_uses_report_it(
    store: RedisRefreshTokenStore,
) -> None:
    first, later = datetime(2026, 1, 1, 12, 0, tzinfo=UTC), datetime(2026, 1, 1, 13, 0, tzinfo=UTC)
    expires = _in(timedelta(hours=1))

    assert await store.mark_used("jti", at=first, expires_at=expires) is None
    assert await store.mark_used("jti", at=later, expires_at=expires) == first


async def test_concurrent_uses_have_exactly_one_winner(store: RedisRefreshTokenStore) -> None:
    now, expires = datetime.now(UTC), _in(timedelta(hours=1))

    results = await asyncio.gather(
        *(store.mark_used("jti", at=now, expires_at=expires) for _ in range(10))
    )

    assert results.count(None) == 1


async def test_session_revocation(store: RedisRefreshTokenStore) -> None:
    assert not await store.is_revoked("sid")

    await store.revoke_session("sid", expires_at=_in(timedelta(hours=1)))

    assert await store.is_revoked("sid")
    assert not await store.is_revoked("other-sid")


async def test_keys_expire_with_the_token(
    store: RedisRefreshTokenStore, redis_client: Redis
) -> None:
    expires = _in(timedelta(hours=1))

    await store.mark_used("jti", at=datetime.now(UTC), expires_at=expires)
    await store.revoke_session("sid", expires_at=expires)

    for key in (USED_PREFIX + "jti", REVOKED_PREFIX + "sid"):
        ttl_ms = await redis_client.pttl(key)
        assert timedelta(minutes=59) < timedelta(milliseconds=ttl_ms) <= timedelta(hours=1)


async def test_unreachable_redis_fails_closed() -> None:
    redis = Redis(host="127.0.0.1", port=1, retry=Retry(NoBackoff(), retries=0))
    store = RedisRefreshTokenStore(redis)
    expires = _in(timedelta(hours=1))
    try:
        with pytest.raises(TokenStoreUnavailable):
            await store.is_revoked("sid")
        with pytest.raises(TokenStoreUnavailable):
            await store.mark_used("jti", at=datetime.now(UTC), expires_at=expires)
        with pytest.raises(TokenStoreUnavailable):
            await store.revoke_session("sid", expires_at=expires)
    finally:
        await redis.aclose()
