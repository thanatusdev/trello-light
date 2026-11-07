from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.application.queries.board import GetBoard
from app.application.queries.get_status import GetStatus, StatusRead
from app.application.queries.tasks import AssigneeRead, GetTask, ListTasks, TaskFilters
from app.domain.errors import InvalidDueDateRange
from app.domain.statuses import Status, StatusName
from app.domain.tasks import Task, TaskDescription, TaskTitle
from app.domain.users import Email, FullName, User
from app.infrastructure.models.status import StatusModel
from app.infrastructure.queries.board import SqlAlchemyGetBoardHandler
from app.infrastructure.queries.statuses import SqlAlchemyGetStatusHandler
from app.infrastructure.queries.tasks import SqlAlchemyGetTaskHandler, SqlAlchemyListTasksHandler
from app.infrastructure.repositories.status_repository import SqlAlchemyStatusRepository
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository

NOW = datetime(2026, 1, 1, tzinfo=UTC)
TODAY = NOW.date()


class Board:
    """A small known board: two open columns and a done column, three users."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.statuses: dict[str, Status] = {}
        self.users: dict[str, User] = {}
        self.tasks: dict[str, Task] = {}

    async def status(self, name: str, position: float, *, is_done: bool = False) -> Status:
        status = Status.create(name=StatusName(name), is_done=is_done, position=position, now=NOW)
        await SqlAlchemyStatusRepository(self.session).add(status)
        self.statuses[name] = status
        return status

    async def user(self, name: str) -> User:
        user = User.register(
            email=Email(f"{name.lower()}@example.com"),
            full_name=FullName(name),
            hashed_password="h",
            now=NOW,
        )
        await SqlAlchemyUserRepository(self.session).add(user)
        self.users[name] = user
        return user

    async def task(
        self,
        title: str,
        status: str,
        position: float,
        *,
        assignee: str | None = None,
        due: date | None = None,
        created_offset: int = 0,
    ) -> Task:
        task = Task.create(
            title=TaskTitle(title),
            description=TaskDescription(f"about {title}"),
            status=self.statuses[status],
            position=position,
            created_by_id=self.users["Alice"].id,
            assignee_id=self.users[assignee].id if assignee else None,
            due_date=due,
            now=NOW + timedelta(minutes=created_offset),
        )
        await SqlAlchemyTaskRepository(self.session).add(task)
        self.tasks[title] = task
        return task


@pytest.fixture
async def board(db_session: AsyncSession) -> Board:
    await db_session.execute(delete(StatusModel))  # start without the seeded columns
    b = Board(db_session)
    await b.status("Todo", 1.0)
    await b.status("Doing", 2.0)
    await b.status("Shipped", 3.0, is_done=True)
    await b.status("Empty", 0.5)
    await b.user("Alice")
    await b.user("Bob")
    await b.task("Write spec", "Todo", 2.0, assignee="Alice", due=TODAY, created_offset=1)
    await b.task("Fix 100% bug", "Todo", 1.0, assignee="Bob", created_offset=2)
    await b.task("Review_PR", "Doing", 1.0, due=TODAY + timedelta(days=5), created_offset=3)
    await b.task(
        "Deploy", "Shipped", 1.0, assignee="Bob", due=TODAY + timedelta(days=10), created_offset=4
    )
    return b


@pytest.fixture
def sql_log(engine: AsyncEngine) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    yield statements
    event.remove(engine.sync_engine, "before_cursor_execute", record)


async def _titles(session: AsyncSession, filters: TaskFilters) -> list[str]:
    result = await SqlAlchemyListTasksHandler(session).handle(ListTasks(filters=filters, size=100))
    return [t.title for t in result.items]


# --- GetStatus ------------------------------------------------------------------


async def test_get_status(board: Board, db_session: AsyncSession) -> None:
    shipped = board.statuses["Shipped"]

    result = await SqlAlchemyGetStatusHandler(db_session).handle(GetStatus(shipped.id))

    assert result == StatusRead(
        id=shipped.id, name="Shipped", position=3.0, is_done=True, created_at=NOW
    )
    assert await SqlAlchemyGetStatusHandler(db_session).handle(GetStatus(uuid4())) is None


# --- GetTask --------------------------------------------------------------------


async def test_get_task_embeds_assignee(board: Board, db_session: AsyncSession) -> None:
    task = board.tasks["Write spec"]
    alice = board.users["Alice"]

    result = await SqlAlchemyGetTaskHandler(db_session).handle(GetTask(task.id))

    assert result is not None
    assert result.id == task.id
    assert result.title == "Write spec"
    assert result.description == "about Write spec"
    assert result.status_id == board.statuses["Todo"].id
    assert result.assignee == AssigneeRead(id=alice.id, full_name="Alice")
    assert result.created_by_id == alice.id
    assert result.due_date == TODAY
    assert result.position == 2.0
    assert result.completed_at is None
    assert result.created_at == result.updated_at == NOW + timedelta(minutes=1)


async def test_get_unassigned_task_and_missing_task(board: Board, db_session: AsyncSession) -> None:
    handler = SqlAlchemyGetTaskHandler(db_session)

    unassigned = await handler.handle(GetTask(board.tasks["Review_PR"].id))

    assert unassigned is not None and unassigned.assignee is None
    assert await handler.handle(GetTask(uuid4())) is None


# --- ListTasks ------------------------------------------------------------------


async def test_list_tasks_newest_first_and_paginated(
    board: Board, db_session: AsyncSession
) -> None:
    handler = SqlAlchemyListTasksHandler(db_session)

    first = await handler.handle(ListTasks(page=1, size=3))
    second = await handler.handle(ListTasks(page=2, size=3))
    beyond = await handler.handle(ListTasks(page=5, size=3))

    assert [t.title for t in first.items] == ["Deploy", "Review_PR", "Fix 100% bug"]
    assert [t.title for t in second.items] == ["Write spec"]
    assert (first.total, first.pages) == (4, 2)
    assert beyond.items == [] and beyond.total == 4


async def test_filter_by_status_and_assignee(board: Board, db_session: AsyncSession) -> None:
    todo = board.statuses["Todo"].id
    bob = board.users["Bob"].id

    assert await _titles(db_session, TaskFilters(status_id=todo)) == ["Fix 100% bug", "Write spec"]
    assert await _titles(db_session, TaskFilters(assignee_id=bob)) == ["Deploy", "Fix 100% bug"]
    assert await _titles(db_session, TaskFilters(status_id=todo, assignee_id=bob)) == [
        "Fix 100% bug"
    ]


async def test_filter_by_completion(board: Board, db_session: AsyncSession) -> None:
    assert await _titles(db_session, TaskFilters(is_completed=True)) == ["Deploy"]
    assert await _titles(db_session, TaskFilters(is_completed=False)) == [
        "Review_PR",
        "Fix 100% bug",
        "Write spec",
    ]


async def test_due_date_filters_are_inclusive_and_skip_undated(
    board: Board, db_session: AsyncSession
) -> None:
    in_5 = TODAY + timedelta(days=5)

    assert await _titles(db_session, TaskFilters(due_before=in_5)) == ["Review_PR", "Write spec"]
    assert await _titles(db_session, TaskFilters(due_after=in_5)) == ["Deploy", "Review_PR"]
    assert await _titles(db_session, TaskFilters(due_after=in_5, due_before=in_5)) == ["Review_PR"]


def test_due_after_later_than_due_before_is_rejected() -> None:
    with pytest.raises(InvalidDueDateRange):
        TaskFilters(due_after=TODAY, due_before=TODAY - timedelta(days=1))


async def test_search_is_case_insensitive_and_escapes_wildcards(
    board: Board, db_session: AsyncSession
) -> None:
    assert await _titles(db_session, TaskFilters(search="SPEC")) == ["Write spec"]
    assert await _titles(db_session, TaskFilters(search="100%")) == ["Fix 100% bug"]
    assert await _titles(db_session, TaskFilters(search="w_p")) == ["Review_PR"]
    # Unescaped, "_" would match the space in "Fix 100% bug".
    assert await _titles(db_session, TaskFilters(search="x_1")) == []
    assert await _titles(db_session, TaskFilters(search="%")) == ["Fix 100% bug"]
    assert await _titles(db_session, TaskFilters(search="   ")) == [
        "Deploy",
        "Review_PR",
        "Fix 100% bug",
        "Write spec",
    ]


async def test_combined_filters(board: Board, db_session: AsyncSession) -> None:
    filters = TaskFilters(
        assignee_id=board.users["Bob"].id,
        is_completed=False,
        search="bug",
    )

    assert await _titles(db_session, filters) == ["Fix 100% bug"]
    assert await _titles(db_session, TaskFilters(is_completed=True, search="bug")) == []


async def test_list_counts_only_matching_tasks(board: Board, db_session: AsyncSession) -> None:
    result = await SqlAlchemyListTasksHandler(db_session).handle(
        ListTasks(filters=TaskFilters(assignee_id=board.users["Bob"].id), size=1)
    )

    assert (result.total, result.pages, len(result.items)) == (2, 2, 1)


# --- GetBoard -------------------------------------------------------------------


async def test_board_columns_and_tasks_are_ordered(board: Board, db_session: AsyncSession) -> None:
    result = await SqlAlchemyGetBoardHandler(db_session).handle(GetBoard())

    assert [(c.name, c.is_done) for c in result.columns] == [
        ("Empty", False),
        ("Todo", False),
        ("Doing", False),
        ("Shipped", True),
    ]
    assert [[t.title for t in c.tasks] for c in result.columns] == [
        [],
        ["Fix 100% bug", "Write spec"],
        ["Review_PR"],
        ["Deploy"],
    ]
    deploy = result.columns[3].tasks[0]
    assert deploy.completed_at == NOW + timedelta(minutes=4)
    assert deploy.assignee == AssigneeRead(id=board.users["Bob"].id, full_name="Bob")


async def test_board_applies_filters_but_keeps_all_columns(
    board: Board, db_session: AsyncSession
) -> None:
    result = await SqlAlchemyGetBoardHandler(db_session).handle(
        GetBoard(TaskFilters(assignee_id=board.users["Bob"].id))
    )

    assert [[t.title for t in c.tasks] for c in result.columns] == [
        [],
        ["Fix 100% bug"],
        [],
        ["Deploy"],
    ]


async def test_board_runs_exactly_two_queries(
    board: Board, db_session: AsyncSession, sql_log: list[str]
) -> None:
    # Pile on tasks so an N+1 would show up as extra statements.
    for i in range(20):
        await board.task(f"Extra {i}", "Doing", 10.0 + i, assignee="Bob")
    sql_log.clear()

    await SqlAlchemyGetBoardHandler(db_session).handle(
        GetBoard(TaskFilters(search="extra", is_completed=False))
    )

    assert len(sql_log) == 2, sql_log
    assert "FROM statuses" in sql_log[0]
    assert "FROM tasks LEFT OUTER JOIN users" in sql_log[1]
