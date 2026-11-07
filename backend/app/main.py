from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI

from app.api.errors import register_error_handlers
from app.api.rate_limit import (
    RATE_LIMITED_RESPONSES,
    default_rate_limit,
    install_rate_limiting,
)
from app.api.routers import auth, board, health, statuses, tasks, users
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import create_engine, create_sessionmaker
from app.infrastructure.logging import configure_logging
from app.infrastructure.notifications.notifier import CeleryNotifier
from app.infrastructure.redis import create_redis
from app.infrastructure.security.password_hasher import BcryptPasswordHasher

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine = create_engine(settings)
    redis = create_redis(settings)
    app.state.engine = engine
    app.state.sessionmaker = create_sessionmaker(engine)
    app.state.redis = redis
    try:
        yield
    finally:
        await redis.aclose()
        await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="Trello Light API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=f"{API_PREFIX}/redoc",
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.state.settings = settings = settings or get_settings()
    configure_logging(settings.log_level)
    app.state.password_hasher = BcryptPasswordHasher(rounds=settings.bcrypt_rounds)
    app.state.notifier = CeleryNotifier()
    register_error_handlers(app)
    # Login and register have their own, stricter per-IP limits instead of the default.
    install_rate_limiting(app, settings, exempt=[auth.login, auth.register])

    # Health checks are never rate limited; every other route gets the default limit,
    # and its 429 is documented once here.
    limited = APIRouter(
        dependencies=[Depends(default_rate_limit)], responses=RATE_LIMITED_RESPONSES
    )
    for module in (auth, users, board, statuses, tasks):
        limited.include_router(module.router)

    api_router = APIRouter(prefix=API_PREFIX)
    api_router.include_router(health.router)
    api_router.include_router(limited)
    app.include_router(api_router)
    return app


app = create_app()
