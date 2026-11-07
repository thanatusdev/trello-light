from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import StatusHasTasks, StatusNameTaken
from app.domain.statuses import Status, StatusName
from app.domain.tasks import Task, TaskDescription, TaskTitle
from app.domain.users import Email, FullName, User
from app.infrastructure.repositories.status_repository import SqlAlchemyStatusRepository
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork

NOW = datetime(2026, 1, 1, tzinfo=UTC)
SEEDED = ["To Do", "In Progress", "Done"]


def _status(name: str, position: float = 10_000.0, *, is_done: bool = False) -> Status:
    return Status.create(name=StatusName(name), is_done=is_done, position=position, now=NOW)


async def _user(session: AsyncSession) -> User:
    user = User.register(
        email=Email(f"{uuid4().hex}@example.com"),
        full_name=FullName("Alice"),
        hashed_password="h",
        now=NOW,
    )
    await SqlAlchemyUserRepository(session).add(user)
    return user


async def _task(session: AsyncSession, status: Status, position: float, user: User) -> Task:
    task = Task.create(
        title=TaskTitle(f"Task {position}"),
        description=None,
        status=status,
        position=position,
        created_by_id=user.id,
        assignee_id=None,
        due_date=None,
        now=NOW,
    )
    await SqlAlchemyTaskRepository(session).add(task)
    return task


# --- statuses -------------------------------------------------------------------


async def test_migration_seeds_default_columns(db_session: AsyncSession) -> None:
    statuses = await SqlAlchemyStatusRepository(db_session).list_for_update()

    assert [(s.name.value, s.is_done) for s in statuses] == [
        ("To Do", False),
        ("In Progress", False),
        ("Done", True),
    ]


async def test_status_roundtrip(db_session: AsyncSession) -> None:
    repo = SqlAlchemyStatusRepository(db_session)
    status = _status("Backlog", is_done=True)

    await repo.add(status)
    db_session.expunge_all()

    assert await repo.get(status.id) == status
    assert await repo.get_for_update(status.id) == status
    assert await repo.get_by_name(StatusName("BACKLOG")) == status
    assert await repo.get(uuid4()) is None
    assert await repo.get_for_update(uuid4()) is None
    assert await repo.get_by_name(StatusName("Nope")) is None


async def test_status_name_unique_index_is_case_insensitive(db_session: AsyncSession) -> None:
    repo = SqlAlchemyStatusRepository(db_session)

    with pytest.raises(StatusNameTaken):
        await repo.add(_status("DONE"))

    # The failed insert must not poison the session.
    assert len(await repo.list_for_update()) == len(SEEDED)


async def test_save_rename_to_taken_name_raises(db_session: AsyncSession) -> None:
    repo = SqlAlchemyStatusRepository(db_session)
    status = _status("Backlog")
    await repo.add(status)

    status.rename(StatusName("to do"))
    with pytest.raises(StatusNameTaken):
        await repo.save(status)


async def test_save_and_set_positions(db_session: AsyncSession) -> None:
    repo = SqlAlchemyStatusRepository(db_session)
    a, b = _status("A", 1.0), _status("B", 2.0)
    await repo.add(a)
    await repo.add(b)

    a.rename(StatusName("Alpha"))
    a.position = 0.5
    await repo.save(a)
    await repo.set_positions({b.id: 0.25})
    db_session.expunge_all()

    names = [s.name.value for s in await repo.list_for_update()]
    assert names[:2] == ["B", "Alpha"]


async def test_has_tasks_and_delete(db_session: AsyncSession) -> None:
    repo = SqlAlchemyStatusRepository(db_session)
    status = _status("Backlog")
    await repo.add(status)
    assert await repo.has_tasks(status.id) is False

    task = await _task(db_session, status, 1.0, await _user(db_session))
    assert await repo.has_tasks(status.id) is True

    await SqlAlchemyTaskRepository(db_session).delete(task.id)
    await repo.delete(status.id)
    assert await repo.get(status.id) is None


async def test_delete_with_tasks_is_blocked_by_foreign_key(db_session: AsyncSession) -> None:
    # The handler checks has_tasks first; this is the backstop if a task slips in anyway.
    repo = SqlAlchemyStatusRepository(db_session)
    status = _status("Backlog")
    await repo.add(status)
    await _task(db_session, status, 1.0, await _user(db_session))

    with pytest.raises(StatusHasTasks):
        await repo.delete(status.id)
    assert await repo.get(status.id) == status


async def test_set_positions_with_nothing_to_change(db_session: AsyncSession) -> None:
    repo = SqlAlchemyStatusRepository(db_session)

    await repo.set_positions({})

    assert len(await repo.list_for_update()) == len(SEEDED)


# --- tasks ----------------------------------------------------------------------


async def test_task_roundtrip_and_save(db_session: AsyncSession) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    status = _status("Backlog")
    done = _status("Shipped", 20_000.0, is_done=True)
    await SqlAlchemyStatusRepository(db_session).add(status)
    await SqlAlchemyStatusRepository(db_session).add(done)
    user = await _user(db_session)
    task = await _task(db_session, status, 1.0, user)
    db_session.expunge_all()

    assert await repo.get(task.id) == task
    assert await repo.get(uuid4()) is None

    later = datetime(2026, 1, 2, tzinfo=UTC)
    task.rename(TaskTitle("Renamed"), now=later)
    task.describe(TaskDescription("notes"), now=later)
    task.reschedule(date(2026, 2, 1), now=later)
    task.assign(user.id, now=later)
    task.move_to(done, position=7.0, now=later)
    await repo.save(task)
    db_session.expunge_all()

    assert await repo.get(task.id) == task


async def test_list_and_set_positions(db_session: AsyncSession) -> None:
    repo = SqlAlchemyTaskRepository(db_session)
    status = _status("Backlog")
    await SqlAlchemyStatusRepository(db_session).add(status)
    user = await _user(db_session)
    t2 = await _task(db_session, status, 2.0, user)
    t1 = await _task(db_session, status, 1.0, user)

    assert await repo.list_positions(status.id) == [(t1.id, 1.0), (t2.id, 2.0)]

    await repo.set_positions(status.id, {t1.id: 3.0, t2.id: 1.5})

    assert await repo.list_positions(status.id) == [(t2.id, 1.5), (t1.id, 3.0)]
    assert await repo.list_positions(uuid4()) == []
    await repo.set_positions(status.id, {})


async def test_unit_of_work_exposes_repositories(db_session: AsyncSession) -> None:
    uow = SqlAlchemyUnitOfWork(db_session)

    assert isinstance(uow.statuses, SqlAlchemyStatusRepository)
    assert isinstance(uow.tasks, SqlAlchemyTaskRepository)
