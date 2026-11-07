import asyncio
import logging
from collections.abc import Awaitable
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.health import HealthReport

logger = logging.getLogger(__name__)


class ServiceHealthProbe:
    """Pings Postgres and Redis concurrently, each bounded by ``timeout`` seconds."""

    def __init__(self, session: AsyncSession, redis: Redis, *, timeout: float) -> None:
        self._session = session
        self._redis = redis
        self._timeout = timeout

    async def check(self) -> HealthReport:
        database, redis = await asyncio.gather(
            self._probe("database", self._session.execute(text("SELECT 1"))),
            self._probe("redis", self._redis.ping()),
        )
        return HealthReport(database=database, redis=redis)

    async def _probe(self, name: str, probe: Awaitable[Any]) -> bool:
        try:
            await asyncio.wait_for(probe, self._timeout)
        except Exception:
            logger.warning("Health check %r failed", name, exc_info=True)
            return False
        return True
