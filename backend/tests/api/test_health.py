import asyncio
from typing import Any, NoReturn

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_health_probe, get_redis, get_session
from app.application.ports.health import HealthReport
from app.infrastructure.config import Settings
from app.main import create_app

HEALTH_URL = "/api/v1/health"


class _BrokenSession:
    async def execute(self, *args: Any, **kwargs: Any) -> NoReturn:
        raise ConnectionRefusedError("database unreachable")


class _BrokenRedis:
    async def ping(self) -> NoReturn:
        raise ConnectionRefusedError("redis unreachable")


async def test_health_ok_when_database_and_redis_are_reachable(client: AsyncClient) -> None:
    response = await client.get(HEALTH_URL)

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


async def test_health_degraded_when_database_is_down(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_session] = lambda: _BrokenSession()

    response = await client.get(HEALTH_URL)

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {"database": "error", "redis": "ok"},
    }


async def test_health_degraded_when_redis_is_down(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_redis] = lambda: _BrokenRedis()

    response = await client.get(HEALTH_URL)

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {"database": "ok", "redis": "error"},
    }


class _FakeProbe:
    def __init__(self, report: HealthReport) -> None:
        self._report = report

    async def check(self) -> HealthReport:
        return self._report


async def test_health_reports_what_the_injected_probe_finds(
    app: FastAPI, client: AsyncClient
) -> None:
    app.dependency_overrides[get_health_probe] = lambda: _FakeProbe(
        HealthReport(database=True, redis=False)
    )

    response = await client.get(HEALTH_URL)

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {"database": "ok", "redis": "error"},
    }


class _HangingRedis:
    async def ping(self) -> None:
        await asyncio.sleep(10)


async def test_health_probe_times_out_slow_dependencies(
    app: FastAPI, client: AsyncClient, test_settings: Settings
) -> None:
    app.state.settings = test_settings.model_copy(update={"health_check_timeout_seconds": 0.01})
    app.dependency_overrides[get_redis] = lambda: _HangingRedis()

    response = await client.get(HEALTH_URL)

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "redis": "error"}


async def test_lifespan_wires_and_releases_resources(
    test_settings: Settings, migrated_database: None
) -> None:
    app = create_app(test_settings)

    async with app.router.lifespan_context(app):
        assert await app.state.redis.ping() is True
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get(HEALTH_URL)

    assert response.status_code == 200
