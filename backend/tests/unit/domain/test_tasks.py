from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.domain.errors import DueDateInPast, ValidationError
from app.domain.statuses import Status, StatusName
from app.domain.tasks import (
    TASK_DESCRIPTION_MAX_LENGTH,
    TASK_TITLE_MAX_LENGTH,
    Task,
    TaskDescription,
    TaskTitle,
)
from tests.unit.application.fakes import FIXED_NOW

TODAY = FIXED_NOW.date()
LATER = FIXED_NOW + timedelta(hours=1)


def _status(*, is_done: bool = False) -> Status:
    return Status.create(
        name=StatusName("Done" if is_done else "Todo"), is_done=is_done, position=1.0, now=FIXED_NOW
    )


def _task(*, status: Status | None = None, due_date: date | None = TODAY) -> Task:
    return Task.create(
        title=TaskTitle("Write tests"),
        description=None,
        status=status or _status(),
        position=1024.0,
        created_by_id=uuid4(),
        assignee_id=None,
        due_date=due_date,
        now=FIXED_NOW,
    )


# --- value objects --------------------------------------------------------------


def test_title_is_trimmed() -> None:
    assert TaskTitle("  Ship it  ").value == "Ship it"


@pytest.mark.parametrize("raw", ["", "   ", "x" * (TASK_TITLE_MAX_LENGTH + 1)])
def test_title_rejects_invalid_length(raw: str) -> None:
    with pytest.raises(ValidationError, match="Title"):
        TaskTitle(raw)


def test_title_accepts_boundaries() -> None:
    assert TaskTitle("x").value == "x"
    assert TaskTitle("x" * TASK_TITLE_MAX_LENGTH).value == "x" * TASK_TITLE_MAX_LENGTH


def test_description_rejects_too_long() -> None:
    with pytest.raises(ValidationError, match="Description"):
        TaskDescription("x" * (TASK_DESCRIPTION_MAX_LENGTH + 1))


def test_blank_description_normalises_to_none() -> None:
    assert TaskDescription.from_raw("   ") is None
    assert TaskDescription.from_raw(None) is None
    assert TaskDescription.from_raw(" notes ") == TaskDescription("notes")


# --- create -------------------------------------------------------------------


def test_create_task_in_open_column() -> None:
    task = _task()

    assert task.title == TaskTitle("Write tests")
    assert task.completed_at is None
    assert task.created_at == task.updated_at == FIXED_NOW


def test_create_task_in_done_column_is_completed() -> None:
    assert _task(status=_status(is_done=True)).completed_at == FIXED_NOW


def test_create_task_due_today_is_allowed() -> None:
    assert _task(due_date=TODAY).due_date == TODAY


def test_create_task_due_in_past_is_rejected() -> None:
    with pytest.raises(DueDateInPast):
        _task(due_date=TODAY - timedelta(days=1))


# --- updates ------------------------------------------------------------------


def test_rename_bumps_updated_at() -> None:
    task = _task()

    task.rename(TaskTitle("New"), now=LATER)

    assert task.title == TaskTitle("New")
    assert task.updated_at == LATER


def test_describe_sets_and_clears_description() -> None:
    task = _task()

    task.describe(TaskDescription("details"), now=LATER)
    assert task.description == TaskDescription("details")

    task.describe(None, now=LATER)
    assert task.description is None


def test_reschedule_to_past_is_rejected() -> None:
    task = _task()

    with pytest.raises(DueDateInPast):
        task.reschedule(TODAY - timedelta(days=1), now=LATER)


def test_reschedule_keeping_existing_past_date_is_allowed() -> None:
    task = _task()
    # Time passes and the task becomes overdue.
    next_week = FIXED_NOW + timedelta(days=7)

    task.reschedule(TODAY, now=next_week)

    assert task.due_date == TODAY


def test_reschedule_can_clear_due_date() -> None:
    task = _task()

    task.reschedule(None, now=LATER)

    assert task.due_date is None
    assert task.updated_at == LATER


# --- move ---------------------------------------------------------------------


def test_move_into_done_column_sets_completed_at() -> None:
    task = _task()

    task.move_to(_status(is_done=True), position=5.0, now=LATER)

    assert task.completed_at == LATER
    assert task.position == 5.0
    assert task.updated_at == LATER


def test_move_out_of_done_column_clears_completed_at() -> None:
    task = _task(status=_status(is_done=True))
    target = _status()

    task.move_to(target, position=5.0, now=LATER)

    assert task.completed_at is None
    assert task.status_id == target.id


def test_move_between_done_columns_keeps_original_completion_time() -> None:
    task = _task(status=_status(is_done=True))

    task.move_to(_status(is_done=True), position=5.0, now=LATER)

    assert task.completed_at == FIXED_NOW


# --- assign -------------------------------------------------------------------


def test_assign_and_unassign() -> None:
    task = _task()
    user_id = uuid4()

    task.assign(user_id, now=LATER)
    assert task.assignee_id == user_id
    assert task.updated_at == LATER

    task.assign(None, now=LATER)
    assert task.assignee_id is None


def test_assign_reports_whether_the_assignee_changed() -> None:
    task = _task()
    user_id = uuid4()

    assert task.assign(user_id, now=LATER) is True
    assert task.assign(user_id, now=LATER) is False
    assert task.assign(None, now=LATER) is True
    assert task.assign(None, now=LATER) is False
