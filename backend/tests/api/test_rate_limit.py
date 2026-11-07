from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_notifier, get_redis, get_session
from app.infrastructure.config import Settings
from app.main import create_app
from tests.api.helpers import LOGIN_URL, PASSWORD, bearer, login, register, tokens_for
from tests.unit.application.fakes import FakeNotifier

ME_URL = "/api/v1/auth/me"
HEALTH_URL = "/api/v1/health"
RATE_LIMITED_BODY = {"detail": "Rate limit exceeded, try again later"}

type ClientFor = Callable[[str], AbstractAsyncContextManager[AsyncClient]]


@pytest.fixture(params=["memory", "redis"])
def limited_app(
    request: pytest.FixtureRequest,
    test_settings: Settings,
    db_session: AsyncSession,
    redis_client: Redis,
) -> FastAPI:
    """Like the ``app`` fixture, but with rate limiting on. Runs against in-memory storage
    and the test Redis database (flushed after each test by ``redis_client``)."""
    storage = "memory://" if request.param == "memory" else test_settings.redis_url
    settings = test_settings.model_copy(
        update={
            "rate_limit_enabled": True,
            "rate_limit_storage_uri": storage,
            "rate_limit_default": "4/minute",
            "rate_limit_login": "5/minute",
            "rate_limit_register": "3/minute",
        }
    )
    app = create_app(settings)

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_redis] = lambda: redis_client
    app.dependency_overrides[get_notifier] = FakeNotifier
    return app


@pytest.fixture
def client_for(limited_app: FastAPI) -> ClientFor:
    """A client whose requests come from the given IP address."""

    @asynccontextmanager
    async def _client(ip: str) -> AsyncIterator[AsyncClient]:
        transport = ASGITransport(app=limited_app, client=(ip, 12345))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

    return _client


def assert_rate_limited(response: Response) -> None:
    assert response.status_code == 429
    assert response.json() == RATE_LIMITED_BODY
    retry_after = int(response.headers["retry-after"])
    assert 0 < retry_after <= 60


async def _logins(client: AsyncClient, count: int, password: str = "wrong-password") -> list[int]:
    return [(await login(client, password=password)).status_code for _ in range(count)]


async def test_login_is_limited_to_five_per_minute_per_ip(client_for: ClientFor) -> None:
    async with client_for("10.0.0.1") as client:
        assert await _logins(client, 5) == [401] * 5

        response = await login(client, password=PASSWORD)

    assert_rate_limited(response)


async def test_login_limit_counts_successful_logins_too(client_for: ClientFor) -> None:
    async with client_for("10.0.0.1") as client:
        await register(client)
        assert await _logins(client, 4, password=PASSWORD) == [200] * 4  # plus register: own limit

        assert (await login(client, password=PASSWORD)).status_code == 200
        assert_rate_limited(await login(client, password=PASSWORD))


async def test_login_limit_is_per_ip(client_for: ClientFor) -> None:
    async with client_for("10.0.0.1") as first, client_for("10.0.0.2") as second:
        await _logins(first, 5)
        assert_rate_limited(await login(first))

        assert (await login(second)).status_code == 401


async def test_login_ignores_forwarded_for_header(client_for: ClientFor) -> None:
    async with client_for("10.0.0.1") as client:
        await _logins(client, 5)

        response = await client.post(
            LOGIN_URL,
            data={"username": "a@example.com", "password": "x"},
            headers={"X-Forwarded-For": "203.0.113.9"},
        )

    assert_rate_limited(response)


async def test_register_is_limited_to_three_per_minute_per_ip(client_for: ClientFor) -> None:
    async with client_for("10.0.0.1") as client:
        statuses = [(await register(client, f"u{i}@example.com")).status_code for i in range(3)]
        assert statuses == [201] * 3

        assert_rate_limited(await register(client, "u4@example.com"))


async def test_default_limit_applies_per_user_not_per_ip(client_for: ClientFor) -> None:
    async with client_for("10.0.0.1") as client:
        alice = bearer((await tokens_for(client, "alice@example.com"))["access_token"])
        bob = bearer((await tokens_for(client, "bob@example.com"))["access_token"])

        alice_statuses = [(await client.get(ME_URL, headers=alice)).status_code for _ in range(4)]
        assert alice_statuses == [200] * 4
        assert_rate_limited(await client.get(ME_URL, headers=alice))

        # Same IP, different user: own bucket.
        assert (await client.get(ME_URL, headers=bob)).status_code == 200


async def test_default_limit_falls_back_to_ip_without_a_valid_token(
    client_for: ClientFor,
) -> None:
    async with client_for("10.0.0.1") as client, client_for("10.0.0.2") as other:
        bad = bearer("not-a-token")
        assert [(await client.get(ME_URL, headers=bad)).status_code for _ in range(4)] == [401] * 4
        assert_rate_limited(await client.get(ME_URL, headers=bad))

        assert (await other.get(ME_URL, headers=bad)).status_code == 401


async def test_storage_failure_lets_requests_through(
    client_for: ClientFor, limited_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: Any) -> bool:
        raise ConnectionError("redis down")

    monkeypatch.setattr(limited_app.state.limiter.limiter, "hit", broken)

    async with client_for("10.0.0.1") as client:
        assert await _logins(client, 7) == [401] * 7


async def test_health_is_not_rate_limited(client_for: ClientFor) -> None:
    async with client_for("10.0.0.1") as client:
        statuses = {(await client.get(HEALTH_URL)).status_code for _ in range(10)}

    assert statuses == {200}


async def test_rate_limiting_off_by_default_in_tests(client: AsyncClient) -> None:
    statuses: list[Any] = [(await login(client)).status_code for _ in range(10)]

    assert statuses == [401] * 10
