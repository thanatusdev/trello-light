from datetime import datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.domain.errors import TokenStoreUnavailable

USED_PREFIX = "auth:refresh:used:"
REVOKED_PREFIX = "auth:refresh:revoked:"


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


class RedisRefreshTokenStore:
    """Keys expire with the token they describe, so the store never needs cleaning up."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def mark_used(
        self, token_id: str, *, at: datetime, expires_at: datetime
    ) -> datetime | None:
        try:
            # SET NX GET is one atomic step: two concurrent refreshes can't both win.
            previous = await self._redis.set(
                USED_PREFIX + token_id, at.isoformat(), nx=True, get=True, pxat=_ms(expires_at)
            )
        except RedisError as exc:
            raise TokenStoreUnavailable() from exc
        if previous is None:
            return None
        raw = previous.decode() if isinstance(previous, bytes) else str(previous)
        return datetime.fromisoformat(raw)

    async def revoke_session(self, session_id: str, *, expires_at: datetime) -> None:
        try:
            await self._redis.set(REVOKED_PREFIX + session_id, "1", pxat=_ms(expires_at))
        except RedisError as exc:
            raise TokenStoreUnavailable() from exc

    async def is_revoked(self, session_id: str) -> bool:
        try:
            return bool(await self._redis.exists(REVOKED_PREFIX + session_id))
        except RedisError as exc:
            raise TokenStoreUnavailable() from exc
