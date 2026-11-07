from collections.abc import AsyncIterator, Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.api.dependencies import get_notifier, get_redis, get_session
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import create_engine
from app.infrastructure.redis import create_redis
from app.main import create_app
from tests.unit.application.fakes import FakeNotifier

TEST_REDIS_DB = 15


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    settings = get_settings()
    return settings.model_copy(
        update={
            "app_env": "test",
            "postgres_db": settings.test_postgres_db,
            "redis_db": TEST_REDIS_DB,
            "bcrypt_rounds": 4,
            # Enabled only by the rate-limit tests, so other tests never see a 429.
            "rate_limit_enabled": False,
        }
    )


@pytest.fixture(scope="session")
def migrated_database(test_settings: Settings) -> Iterator[None]:
    """Bring the test database schema up to date once per test session."""
    config = Config("alembic.ini")
    config.attributes["database_url"] = test_settings.database_url
    command.upgrade(config, "head")
    yield


@pytest.fixture(scope="session")
async def engine(test_settings: Settings, migrated_database: None) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(test_settings)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session bound to an outer transaction that is rolled back after each test.

    Code under test may call ``commit()``; with ``create_savepoint`` that only
    releases a savepoint, so nothing ever persists past the test.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def redis_client(test_settings: Settings) -> AsyncIterator[Redis]:
    client = create_redis(test_settings)
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


@pytest.fixture
def app(
    test_settings: Settings, db_session: AsyncSession, redis_client: Redis, notifier: FakeNotifier
) -> FastAPI:
    """App wired to the per-test transaction, the test Redis database and a recording
    notifier (so tests never queue real Celery tasks)."""
    app = create_app(test_settings)

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_redis] = lambda: redis_client
    app.dependency_overrides[get_notifier] = lambda: notifier
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
