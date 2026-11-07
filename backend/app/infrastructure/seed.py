"""Demo data: ``python -m app.infrastructure.seed``.

Runs at container startup (after migrations) and does nothing unless
``SEED_DEMO_DATA=true``. Safe to run repeatedly: users are matched by email, statuses by
name (case-insensitive) and tasks by title, and anything that already exists is left
alone. Everything is created through the normal command handlers, so the data obeys the
same rules as data created through the API (which is also why no task is overdue: the
domain does not accept due dates in the past).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.create_status import CreateStatus, CreateStatusHandler
from app.application.commands.create_task import CreateTask, CreateTaskHandler
from app.application.commands.register_user import RegisterUser, RegisterUserHandler
from app.application.ports.clock import Clock
from app.application.ports.password_hasher import PasswordHasher
from app.domain.statuses import StatusName
from app.domain.users import Email
from app.infrastructure.clock import utc_now
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import create_engine, create_sessionmaker
from app.infrastructure.logging import configure_logging
from app.infrastructure.models.task import TaskModel
from app.infrastructure.notifications.notifier import NullNotifier
from app.infrastructure.security.password_hasher import BcryptPasswordHasher
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

# Not __name__: run with `python -m` that is "__main__", outside the "app" logger.
logger = logging.getLogger("app.seed")

DEMO_USERS: list[tuple[str, str]] = [
    ("alice@example.com", "Alice Johnson"),
    ("bob@example.com", "Bob Martinez"),
    ("carol@example.com", "Carol Chen"),
]
DEFAULT_STATUSES: list[tuple[str, bool]] = [
    ("To Do", False),
    ("In Progress", False),
    ("Done", True),
]


@dataclass(frozen=True, slots=True)
class DemoTask:
    title: str
    status: str
    created_by: str  # demo user email
    assignee: str | None = None  # demo user email
    due_in_days: int | None = None  # relative to the day the seed runs
    description: str | None = None


_A, _B, _C = (email for email, _ in DEMO_USERS)

DEMO_TASKS: list[DemoTask] = [
    DemoTask("Set up CI pipeline", "Done", _A, _A, description="Lint, type-check and test."),
    DemoTask("Design database schema", "Done", _B, _B),
    DemoTask("Write onboarding guide", "Done", _C, _A, due_in_days=2),
    DemoTask("Implement login page", "In Progress", _A, _B, due_in_days=0),
    DemoTask("Drag-and-drop between columns", "In Progress", _B, _C, due_in_days=1),
    DemoTask("Add task filters", "In Progress", _C, _A, due_in_days=3),
    DemoTask("Rate-limit the auth endpoints", "In Progress", _A, _A, due_in_days=1),
    DemoTask("Fix flaky board test", "To Do", _B, _B, due_in_days=0),
    DemoTask("Email notifications for due tasks", "To Do", _A, _C, due_in_days=1),
    DemoTask("Mobile layout for the board", "To Do", _C, _C, due_in_days=7),
    DemoTask("Write API usage docs", "To Do", _B, _A, due_in_days=10),
    DemoTask("Accessibility audit", "To Do", _C, _B, due_in_days=14),
    DemoTask("Dark mode", "To Do", _A, None, description="Nice to have."),
    DemoTask("Archive old tasks", "To Do", _B, None, due_in_days=5),
    DemoTask("Investigate slow board load", "To Do", _C, None),
]


@dataclass(frozen=True, slots=True)
class SeedResult:
    users: int
    statuses: int
    tasks: int


async def seed(
    session: AsyncSession, *, password: str, hasher: PasswordHasher, clock: Clock
) -> SeedResult:
    uow = SqlAlchemyUnitOfWork(session)

    users: dict[str, UUID] = {}
    created_users = 0
    register = RegisterUserHandler(uow=uow, hasher=hasher, clock=clock)
    for email, full_name in DEMO_USERS:
        existing = await uow.users.get_by_email(Email(email))
        if existing is not None:
            users[email] = existing.id
            continue
        users[email] = await register.handle(
            RegisterUser(email=email, full_name=full_name, password=password)
        )
        created_users += 1

    statuses: dict[str, UUID] = {}
    created_statuses = 0
    create_status = CreateStatusHandler(uow=uow, clock=clock)
    for name, is_done in DEFAULT_STATUSES:
        existing_status = await uow.statuses.get_by_name(StatusName(name))
        if existing_status is not None:
            statuses[name] = existing_status.id
            continue
        statuses[name] = await create_status.handle(CreateStatus(name=name, is_done=is_done))
        created_statuses += 1

    titles = [t.title for t in DEMO_TASKS]
    existing_titles = set(
        (await session.scalars(select(TaskModel.title).where(TaskModel.title.in_(titles)))).all()
    )
    created_tasks = 0
    create_task = CreateTaskHandler(uow=uow, clock=clock, notifier=NullNotifier())
    today = clock().date()
    for task in DEMO_TASKS:
        if task.title in existing_titles:
            continue
        await create_task.handle(
            CreateTask(
                title=task.title,
                description=task.description,
                status_id=statuses[task.status],
                created_by_id=users[task.created_by],
                assignee_id=users[task.assignee] if task.assignee else None,
                due_date=today + timedelta(days=task.due_in_days)
                if task.due_in_days is not None
                else None,
            )
        )
        created_tasks += 1

    return SeedResult(users=created_users, statuses=created_statuses, tasks=created_tasks)


async def run(settings: Settings) -> None:
    if not settings.seed_demo_data:
        logger.info("SEED_DEMO_DATA is not true; skipping demo data")
        return
    if settings.demo_user_password is None:
        raise SystemExit("SEED_DEMO_DATA=true requires DEMO_USER_PASSWORD")

    engine = create_engine(settings)
    try:
        async with create_sessionmaker(engine)() as session:
            result = await seed(
                session,
                password=settings.demo_user_password.get_secret_value(),
                hasher=BcryptPasswordHasher(rounds=settings.bcrypt_rounds),
                clock=utc_now,
            )
    finally:
        await engine.dispose()
    logger.info(
        "Demo data: created %d users, %d statuses, %d tasks",
        result.users,
        result.statuses,
        result.tasks,
    )


if __name__ == "__main__":  # pragma: no cover
    settings = get_settings()
    configure_logging(settings.log_level)
    asyncio.run(run(settings))
