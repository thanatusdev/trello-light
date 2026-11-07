"""Celery tasks: thin sync wrappers that run the async jobs in ``notifications.jobs``."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.celery_app import celery_app
from app.infrastructure.clock import utc_now
from app.infrastructure.config import get_settings
from app.infrastructure.notifications import jobs
from app.infrastructure.notifications.email import ConsoleEmailSender

# Connection problems are worth retrying; anything else is a bug and should surface.
_RETRY_ON = (OSError, OperationalError)


def _run[T](job: Callable[[jobs.SessionFactory], Awaitable[T]]) -> T:
    async def main() -> T:
        # A fresh engine per run: each asyncio.run() has its own event loop, and asyncpg
        # connections cannot be shared across loops.
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        try:
            return await job(async_sessionmaker(engine, expire_on_commit=False))
        finally:
            await engine.dispose()

    return asyncio.run(main())


@celery_app.task(
    name="notifications.task_assigned",
    autoretry_for=_RETRY_ON,
    retry_backoff=True,
    max_retries=3,
)
def send_task_assigned(task_id: str, assignee_id: str, assigned_by_id: str) -> bool:
    return _run(
        lambda sessions: jobs.send_task_assigned_email(
            sessions,
            ConsoleEmailSender(),
            task_id=UUID(task_id),
            assignee_id=UUID(assignee_id),
            assigned_by_id=UUID(assigned_by_id),
        )
    )


@celery_app.task(
    name="notifications.due_soon_digests",
    autoretry_for=_RETRY_ON,
    retry_backoff=True,
    max_retries=3,
)
def send_due_soon_digests() -> int:
    today = utc_now().date()
    return _run(
        lambda sessions: jobs.send_due_soon_digests(sessions, ConsoleEmailSender(), today=today)
    )
