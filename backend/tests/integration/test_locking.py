"""Row and advisory locks, checked with two real connections.

These tests need data that other connections can see, so they commit it and clean it up
afterwards instead of using the rolled-back ``db_session``.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.application.commands.assign_task import AssignTask, AssignTaskHandler
from app.application.commands.rename_status import RenameStatus, RenameStatusHandler
from app.domain.statuses import Status, StatusName
from app.domain.tasks import Task, TaskTitle
from app.domain.users import Email, FullName, User
from app.infrastructure.models.status import StatusModel
from app.infrastructure.models.task import TaskModel
from app.infrastructure.models.user import UserModel
from app.infrastructure.repositories.status_repository import BOARD_LOCK_KEY
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork
from tests.unit.application.fakes import FakeNotifier

NOW = datetime(2026, 1, 1, tzinfo=UTC)
# Long enough for the blocked transaction to reach its lock; it must still be waiting after.
SETTLE_SECONDS = 0.3


@dataclass(frozen=True)
class Committed:
    user_id: UUID
    status: Status
    task_ids: list[UUID]


@pytest.fixture
def sessions(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def committed(sessions: async_sessionmaker[AsyncSession]) -> AsyncIterator[Committed]:
    """A user, a column of its own and two tasks in it, committed for real."""
    user = User.register(
        email=Email(f"{uuid4().hex}@example.com"),
        full_name=FullName("Locker"),
        hashed_password="h",
        now=NOW,
    )
    status = Status.create(
        name=StatusName(f"Lock {uuid4().hex[:8]}"), is_done=False, position=99_999.0, now=NOW
    )
    tasks = [
        Task.create(
            title=TaskTitle(f"T{i}"),
            description=None,
            status=status,
            position=1024.0 * (i + 1),
            created_by_id=user.id,
            assignee_id=None,
            due_date=None,
            now=NOW,
        )
        for i in range(2)
    ]
    async with sessions() as session:
        uow = SqlAlchemyUnitOfWork(session)
        await uow.users.add(user)
        await uow.statuses.add(status)
        for task in tasks:
            await uow.tasks.add(task)
        await uow.commit()
    try:
        yield Committed(user.id, status, [t.id for t in tasks])
    finally:
        async with sessions() as session:
            await session.execute(delete(TaskModel).where(TaskModel.status_id == status.id))
            await session.execute(delete(StatusModel).where(StatusModel.id == status.id))
            await session.execute(delete(UserModel).where(UserModel.id == user.id))
            await session.commit()


async def test_concurrent_task_writes_do_not_lose_updates(
    sessions: async_sessionmaker[AsyncSession], committed: Committed
) -> None:
    task_id = committed.task_ids[0]
    async with sessions() as first, sessions() as second:
        first_uow = SqlAlchemyUnitOfWork(first)
        task = await first_uow.tasks.get_for_update(task_id)
        assert task is not None

        assign = asyncio.create_task(
            AssignTaskHandler(SqlAlchemyUnitOfWork(second), lambda: NOW, FakeNotifier()).handle(
                AssignTask(
                    task_id=task_id,
                    assignee_id=committed.user_id,
                    assigned_by_id=committed.user_id,
                )
            )
        )
        await asyncio.sleep(SETTLE_SECONDS)
        assert not assign.done(), "assign did not wait for the task row lock"

        task.rename(TaskTitle("Renamed"), now=NOW)
        await first_uow.tasks.save(task)
        await first_uow.commit()
        await assign

    async with sessions() as check:
        row = (
            await check.execute(
                select(TaskModel.title, TaskModel.assignee_id).where(TaskModel.id == task_id)
            )
        ).one()
    assert (row.title, row.assignee_id) == ("Renamed", committed.user_id)


async def test_rename_waits_for_a_concurrent_reorder_and_keeps_its_position(
    sessions: async_sessionmaker[AsyncSession], committed: Committed
) -> None:
    status_id = committed.status.id
    new_name = f"Renamed {uuid4().hex[:8]}"
    async with sessions() as first, sessions() as second:
        first_uow = SqlAlchemyUnitOfWork(first)
        await first_uow.statuses.lock_board()
        statuses = await first_uow.statuses.list_for_update()
        status = next(s for s in statuses if s.id == status_id)

        rename = asyncio.create_task(
            RenameStatusHandler(SqlAlchemyUnitOfWork(second)).handle(
                RenameStatus(status_id=status_id, name=new_name)
            )
        )
        await asyncio.sleep(SETTLE_SECONDS)
        assert not rename.done(), "rename did not wait for the status row lock"

        status.position = 12_345.0
        await first_uow.statuses.save(status)
        await first_uow.commit()
        await rename

    async with sessions() as check:
        row = (
            await check.execute(
                select(StatusModel.name, StatusModel.position).where(StatusModel.id == status_id)
            )
        ).one()
    assert (row.name, row.position) == (new_name, 12_345.0)


async def test_get_for_update_locks_the_task_row(
    sessions: async_sessionmaker[AsyncSession], committed: Committed
) -> None:
    task_id = committed.task_ids[0]
    async with sessions() as first, sessions() as second:
        assert await SqlAlchemyUnitOfWork(first).tasks.get_for_update(task_id) is not None

        with pytest.raises(DBAPIError, match="could not obtain lock"):
            await second.execute(
                select(TaskModel.id).where(TaskModel.id == task_id).with_for_update(nowait=True)
            )
        assert await SqlAlchemyUnitOfWork(first).tasks.get_for_update(uuid4()) is None


async def test_lock_board_takes_the_transaction_advisory_lock(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    probe = text("SELECT pg_try_advisory_xact_lock(:key)").bindparams(key=BOARD_LOCK_KEY)
    async with sessions() as first, sessions() as second:
        await SqlAlchemyUnitOfWork(first).statuses.lock_board()

        assert await second.scalar(probe) is False

        await first.commit()  # released at the end of the transaction
        assert await second.scalar(probe) is True


async def test_rebalance_only_touches_tasks_still_in_the_column(
    committed: Committed, db_session: AsyncSession
) -> None:
    # ``committed`` first, so its cleanup runs after db_session's rollback releases the row.
    uow = SqlAlchemyUnitOfWork(db_session)
    in_column, _ = committed.task_ids
    other_column = uuid4()

    await uow.tasks.set_positions(other_column, {in_column: 1.0})
    position_after_wrong_column = await db_session.scalar(
        select(TaskModel.position).where(TaskModel.id == in_column)
    )
    await uow.tasks.set_positions(committed.status.id, {in_column: 2.0})
    position_after_right_column = await db_session.scalar(
        select(TaskModel.position).where(TaskModel.id == in_column)
    )

    assert position_after_wrong_column == 1024.0
    assert position_after_right_column == 2.0
