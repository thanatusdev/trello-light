from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure import seed as seed_module
from app.infrastructure.config import Settings
from app.infrastructure.models.status import StatusModel
from app.infrastructure.models.task import TaskModel
from app.infrastructure.models.user import UserModel
from app.infrastructure.seed import DEMO_TASKS, DEMO_USERS, SeedResult, seed
from tests.unit.application.fakes import FakePasswordHasher

NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)
TODAY = NOW.date()
PASSWORD = "Demo1234!"


async def _seed(session: AsyncSession) -> SeedResult:
    return await seed(session, password=PASSWORD, hasher=FakePasswordHasher(), clock=lambda: NOW)


async def _count(session: AsyncSession, model: type) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def test_seed_creates_demo_users_statuses_and_tasks(db_session: AsyncSession) -> None:
    result = await _seed(db_session)

    assert result == SeedResult(users=3, statuses=0, tasks=len(DEMO_TASKS))
    assert 12 <= len(DEMO_TASKS) <= 18
    users = (await db_session.execute(select(UserModel.email, UserModel.hashed_password))).all()
    assert {(u.email, u.hashed_password) for u in users} == {
        (email, f"hashed:{PASSWORD}") for email, _ in DEMO_USERS
    }


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await _seed(db_session)
    counts = [await _count(db_session, m) for m in (UserModel, StatusModel, TaskModel)]

    second = await _seed(db_session)

    assert second == SeedResult(users=0, statuses=0, tasks=0)
    assert [await _count(db_session, m) for m in (UserModel, StatusModel, TaskModel)] == counts


async def test_seed_recreates_a_missing_default_status(db_session: AsyncSession) -> None:
    await db_session.execute(delete(StatusModel).where(StatusModel.name == "In Progress"))

    result = await _seed(db_session)

    assert result.statuses == 1
    done = await db_session.scalar(select(StatusModel.is_done).where(StatusModel.name == "Done"))
    assert done is True


async def test_seed_tasks_are_varied(db_session: AsyncSession) -> None:
    await _seed(db_session)

    rows = (
        await db_session.execute(
            select(
                TaskModel.assignee_id,
                TaskModel.due_date,
                TaskModel.completed_at,
                StatusModel.name,
                StatusModel.is_done,
            ).join(StatusModel, StatusModel.id == TaskModel.status_id)
        )
    ).all()

    assignees = {r.assignee_id for r in rows}
    assert None in assignees
    assert len(assignees - {None}) == 3
    assert {r.name for r in rows} == {"To Do", "In Progress", "Done"}
    due = {r.due_date for r in rows}
    assert {None, TODAY, TODAY + timedelta(days=1)} <= due
    assert all(d is None or d >= TODAY for d in due)
    assert all((r.completed_at is not None) == r.is_done for r in rows)


async def test_run_does_nothing_unless_enabled(
    test_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = False

    async def fake_seed(*_: object, **__: object) -> SeedResult:
        nonlocal called
        called = True
        return SeedResult(0, 0, 0)

    monkeypatch.setattr(seed_module, "seed", fake_seed)

    await seed_module.run(test_settings.model_copy(update={"seed_demo_data": False}))

    assert called is False


async def test_run_requires_a_demo_password(test_settings: Settings) -> None:
    settings = test_settings.model_copy(update={"seed_demo_data": True, "demo_user_password": None})

    with pytest.raises(SystemExit, match="DEMO_USER_PASSWORD"):
        await seed_module.run(settings)


async def test_run_seeds_with_its_own_engine(
    test_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, object] = {}

    async def fake_seed(session: AsyncSession, *, password: str, **_: object) -> SeedResult:
        seen["password"] = password
        seen["db"] = await session.scalar(select(func.current_database()))
        return SeedResult(0, 0, 0)

    monkeypatch.setattr(seed_module, "seed", fake_seed)
    settings = test_settings.model_copy(
        update={"seed_demo_data": True, "demo_user_password": SecretStr(PASSWORD)}
    )

    await seed_module.run(settings)

    assert seen == {"password": PASSWORD, "db": test_settings.postgres_db}
