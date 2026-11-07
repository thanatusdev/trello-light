from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from itertools import count
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.statuses import Status, StatusName
from app.domain.tasks import Task, TaskTitle
from app.domain.users import Email, FullName, User
from app.infrastructure import tasks as celery_tasks
from app.infrastructure.config import Settings
from app.infrastructure.notifications.email import EmailMessage
from app.infrastructure.notifications.jobs import (
    SessionFactory,
    send_due_soon_digests,
    send_task_assigned_email,
)
from app.infrastructure.repositories.status_repository import SqlAlchemyStatusRepository
from app.infrastructure.repositories.task_repository import SqlAlchemyTaskRepository
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository

NOW = datetime(2026, 3, 10, 9, 0, tzinfo=UTC)
TODAY = NOW.date()


class FakeEmailSender:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class Data:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._positions = count(1024, 1024)

    async def user(self, name: str, *, is_active: bool = True) -> User:
        user = User.register(
            email=Email(f"{name.lower()}@example.com"),
            full_name=FullName(name),
            hashed_password="h",
            now=NOW,
        )
        user.is_active = is_active
        await SqlAlchemyUserRepository(self.session).add(user)
        return user

    async def status(self, *, is_done: bool) -> Status:
        repo = SqlAlchemyStatusRepository(self.session)
        name = "Done" if is_done else "To Do"
        status = await repo.get_by_name(StatusName(name))
        assert status is not None, "seeded by migration 0002"
        return status

    async def task(
        self,
        title: str,
        *,
        creator: User,
        assignee: User | None,
        due: date | None,
        done: bool = False,
    ) -> Task:
        task = Task.create(
            title=TaskTitle(title),
            description=None,
            status=await self.status(is_done=done),
            position=float(next(self._positions)),
            created_by_id=creator.id,
            assignee_id=assignee.id if assignee else None,
            due_date=due,
            now=NOW,
        )
        await SqlAlchemyTaskRepository(self.session).add(task)
        await self.session.flush()
        return task


@pytest.fixture
def data(db_session: AsyncSession) -> Data:
    return Data(db_session)


@pytest.fixture
def sessions(db_session: AsyncSession) -> SessionFactory:
    return lambda: nullcontext(db_session)


@pytest.fixture
def sender() -> FakeEmailSender:
    return FakeEmailSender()


# --- assignment email -----------------------------------------------------------


async def test_assignment_email_reads_current_task_and_users(
    data: Data, sessions: SessionFactory, sender: FakeEmailSender
) -> None:
    alice, bob = await data.user("Alice"), await data.user("Bob")
    task = await data.task("Ship it", creator=alice, assignee=bob, due=TODAY)

    sent = await send_task_assigned_email(
        sessions, sender, task_id=task.id, assignee_id=bob.id, assigned_by_id=alice.id
    )

    assert sent is True
    assert sender.sent == [
        EmailMessage(
            to="bob@example.com",
            subject="You were assigned: Ship it",
            body=f'Hi Bob,\n\nAlice assigned you to "Ship it".\nDue: {TODAY.isoformat()}\n',
        )
    ]


async def test_assignment_email_skipped_when_task_was_reassigned(
    data: Data, sessions: SessionFactory, sender: FakeEmailSender
) -> None:
    alice, bob, carol = await data.user("Alice"), await data.user("Bob"), await data.user("Carol")
    task = await data.task("Ship it", creator=alice, assignee=carol, due=None)

    sent = await send_task_assigned_email(
        sessions, sender, task_id=task.id, assignee_id=bob.id, assigned_by_id=alice.id
    )

    assert sent is False
    assert sender.sent == []


@pytest.mark.parametrize("case", ["missing_task", "inactive_assignee"])
async def test_assignment_email_skipped_when_no_longer_valid(
    case: str, data: Data, sessions: SessionFactory, sender: FakeEmailSender
) -> None:
    alice = await data.user("Alice")
    bob = await data.user("Bob", is_active=case != "inactive_assignee")
    task = await data.task("Ship it", creator=alice, assignee=bob, due=None)
    task_id = uuid4() if case == "missing_task" else task.id

    sent = await send_task_assigned_email(
        sessions, sender, task_id=task_id, assignee_id=bob.id, assigned_by_id=alice.id
    )

    assert sent is False


async def test_assignment_email_without_due_date_or_known_assigner(
    data: Data, sessions: SessionFactory, sender: FakeEmailSender
) -> None:
    alice, bob = await data.user("Alice"), await data.user("Bob")
    task = await data.task("Ship it", creator=alice, assignee=bob, due=None)

    await send_task_assigned_email(
        sessions, sender, task_id=task.id, assignee_id=bob.id, assigned_by_id=uuid4()
    )

    assert sender.sent[0].body == 'Hi Bob,\n\nSomeone assigned you to "Ship it".\n'


# --- due-soon digests -----------------------------------------------------------


async def test_due_soon_digest_per_assignee_for_today_and_tomorrow(
    data: Data, sessions: SessionFactory, sender: FakeEmailSender
) -> None:
    alice, bob = await data.user("Alice"), await data.user("Bob")
    gone = await data.user("Gone", is_active=False)
    tomorrow, later = TODAY + timedelta(days=1), TODAY + timedelta(days=2)
    await data.task("B today", creator=alice, assignee=bob, due=TODAY)
    await data.task("B tomorrow", creator=alice, assignee=bob, due=tomorrow)
    await data.task("B later", creator=alice, assignee=bob, due=later)
    await data.task("B done", creator=alice, assignee=bob, due=TODAY, done=True)
    await data.task("A tomorrow", creator=alice, assignee=alice, due=tomorrow)
    await data.task("Nobody", creator=alice, assignee=None, due=TODAY)
    await data.task("Inactive", creator=alice, assignee=gone, due=TODAY)
    await data.task("No date", creator=alice, assignee=bob, due=None)

    count = await send_due_soon_digests(sessions, sender, today=TODAY)

    assert count == 2
    assert sender.sent == [
        EmailMessage(
            to="alice@example.com",
            subject="1 task due soon",
            body="Hi Alice,\n\nThis task is due within the next day:\n"
            f"- A tomorrow (due {tomorrow.isoformat()})\n",
        ),
        EmailMessage(
            to="bob@example.com",
            subject="2 tasks due soon",
            body="Hi Bob,\n\nThese tasks are due within the next day:\n"
            f"- B today (due {TODAY.isoformat()})\n"
            f"- B tomorrow (due {tomorrow.isoformat()})\n",
        ),
    ]


async def test_due_soon_digest_sends_nothing_when_nothing_is_due(
    sessions: SessionFactory, sender: FakeEmailSender
) -> None:
    assert await send_due_soon_digests(sessions, sender, today=date(1999, 1, 1)) == 0
    assert sender.sent == []


# --- Celery task wrappers -------------------------------------------------------


@pytest.fixture
def worker_settings(test_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr(celery_tasks, "get_settings", lambda: test_settings)
    return test_settings


def test_send_task_assigned_task_runs_the_job(worker_settings: Settings) -> None:
    # Its own engine sees no uncommitted test data, so the assignment does not exist.
    ids = [str(uuid4()) for _ in range(3)]

    assert celery_tasks.send_task_assigned.run(*ids) is False


def test_send_due_soon_digests_task_runs_the_job(
    worker_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(celery_tasks, "utc_now", lambda: datetime(1999, 1, 1, tzinfo=UTC))

    assert celery_tasks.send_due_soon_digests.run() == 0


def test_task_names_match_the_beat_schedule() -> None:
    schedule = celery_tasks.celery_app.conf.beat_schedule
    assert schedule["due-soon-digests"]["task"] == celery_tasks.send_due_soon_digests.name
