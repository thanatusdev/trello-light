from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.application.commands.assign_task import AssignTask, AssignTaskHandler
from app.application.commands.create_task import CreateTask, CreateTaskHandler
from app.application.commands.delete_task import DeleteTask, DeleteTaskHandler
from app.application.commands.move_task import MoveTask, MoveTaskHandler
from app.application.commands.update_task import UpdateTask, UpdateTaskHandler
from app.domain.errors import (
    DueDateInPast,
    InvalidAssignee,
    StaleOrdering,
    TaskNotFound,
    UnknownStatus,
    ValidationError,
)
from app.domain.ordering import MIN_GAP, STEP
from app.domain.statuses import Status
from app.domain.tasks import Task, TaskDescription, TaskTitle
from tests.unit.application.fakes import (
    FIXED_NOW,
    Assignment,
    FailingCommitUnitOfWork,
    FakeNotifier,
    FakeUnitOfWork,
    fixed_clock,
    make_status,
    make_task,
    make_user,
)

TODAY = FIXED_NOW.date()
CREATOR_ID = uuid4()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
async def todo(uow: FakeUnitOfWork) -> Status:
    status = make_status("To Do", position=STEP)
    await uow.statuses.add(status)
    return status


@pytest.fixture
async def done(uow: FakeUnitOfWork) -> Status:
    status = make_status("Done", position=2 * STEP, is_done=True)
    await uow.statuses.add(status)
    return status


async def _tasks(uow: FakeUnitOfWork, status: Status, count: int) -> list[Task]:
    tasks = [make_task(status, title=f"T{i}", position=STEP * (i + 1)) for i in range(count)]
    for task in tasks:
        await uow.tasks.add(task)
    return tasks


def _titles(uow: FakeUnitOfWork, status: Status) -> list[str]:
    column = [t for t in uow.tasks.tasks.values() if t.status_id == status.id]
    return [t.title.value for t in sorted(column, key=lambda t: t.position)]


def _create(status_id: object, **overrides: object) -> CreateTask:
    fields: dict[str, object] = {
        "title": "Write docs",
        "status_id": status_id,
        "created_by_id": CREATOR_ID,
    }
    return CreateTask(**(fields | overrides))  # type: ignore[arg-type]


# --- CreateTask -----------------------------------------------------------------


async def test_create_task_in_empty_column(uow: FakeUnitOfWork, todo: Status) -> None:
    task_id = await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
        _create(todo.id, description="  notes ", due_date=TODAY)
    )

    task = uow.tasks.tasks[task_id]
    assert task.title == TaskTitle("Write docs")
    assert task.description == TaskDescription("notes")
    assert task.status_id == todo.id
    assert task.created_by_id == CREATOR_ID
    assert task.assignee_id is None
    assert task.due_date == TODAY
    assert task.position == STEP
    assert task.completed_at is None
    assert uow.statuses.locked == [todo.id]
    assert uow.commits == 1


async def test_create_task_goes_to_bottom_of_column(uow: FakeUnitOfWork, todo: Status) -> None:
    await _tasks(uow, todo, 3)

    task_id = await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(_create(todo.id))

    assert uow.tasks.tasks[task_id].position == 4 * STEP


async def test_create_task_in_done_column_is_completed(uow: FakeUnitOfWork, done: Status) -> None:
    task_id = await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(_create(done.id))

    assert uow.tasks.tasks[task_id].completed_at == FIXED_NOW


async def test_create_task_with_active_assignee(uow: FakeUnitOfWork, todo: Status) -> None:
    user = make_user()
    await uow.users.add(user)

    task_id = await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
        _create(todo.id, assignee_id=user.id)
    )

    assert uow.tasks.tasks[task_id].assignee_id == user.id


async def test_create_task_with_unknown_status(uow: FakeUnitOfWork) -> None:
    with pytest.raises(UnknownStatus):
        await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(_create(uuid4()))
    assert uow.commits == 0


@pytest.mark.parametrize(
    "active", [pytest.param(None, id="unknown"), pytest.param(False, id="inactive")]
)
async def test_create_task_with_invalid_assignee(
    uow: FakeUnitOfWork, todo: Status, active: bool | None
) -> None:
    assignee_id = uuid4()
    if active is not None:
        user = make_user(is_active=active)
        await uow.users.add(user)
        assignee_id = user.id

    with pytest.raises(InvalidAssignee):
        await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
            _create(todo.id, assignee_id=assignee_id)
        )


async def test_create_task_with_past_due_date(uow: FakeUnitOfWork, todo: Status) -> None:
    with pytest.raises(DueDateInPast):
        await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
            _create(todo.id, due_date=TODAY - timedelta(days=1))
        )
    assert uow.tasks.tasks == {}


@pytest.mark.parametrize("title", ["", "   ", "x" * 201])
async def test_create_task_with_invalid_title(
    uow: FakeUnitOfWork, todo: Status, title: str
) -> None:
    with pytest.raises(ValidationError, match="Title"):
        await CreateTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
            _create(todo.id, title=title)
        )


# --- UpdateTask -----------------------------------------------------------------


async def test_update_only_given_fields(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    later = FIXED_NOW + timedelta(hours=1)

    await UpdateTaskHandler(uow, lambda: later).handle(
        UpdateTask(task_id=task.id, title=" Renamed ")
    )

    stored = uow.tasks.tasks[task.id]
    assert stored.title == TaskTitle("Renamed")
    assert stored.description == task.description
    assert stored.due_date == task.due_date
    assert stored.updated_at == later
    assert uow.commits == 1


async def test_update_sets_and_clears_optional_fields(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    handler = UpdateTaskHandler(uow, fixed_clock)

    await handler.handle(UpdateTask(task_id=task.id, description="details", due_date=TODAY))
    stored = uow.tasks.tasks[task.id]
    assert (stored.description, stored.due_date) == (TaskDescription("details"), TODAY)

    await handler.handle(UpdateTask(task_id=task.id, description=None, due_date=None))
    stored = uow.tasks.tasks[task.id]
    assert (stored.description, stored.due_date) == (None, None)


async def test_update_rejects_past_due_date(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)

    with pytest.raises(DueDateInPast):
        await UpdateTaskHandler(uow, fixed_clock).handle(
            UpdateTask(task_id=task.id, due_date=TODAY - timedelta(days=1))
        )


async def test_update_keeps_existing_overdue_date(uow: FakeUnitOfWork, todo: Status) -> None:
    task = make_task(todo, due_date=TODAY)
    await uow.tasks.add(task)
    next_week = FIXED_NOW + timedelta(days=7)

    await UpdateTaskHandler(uow, lambda: next_week).handle(
        UpdateTask(task_id=task.id, title="Still overdue", due_date=TODAY)
    )

    assert uow.tasks.tasks[task.id].due_date == TODAY


async def test_update_rejects_blank_title(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)

    with pytest.raises(ValidationError):
        await UpdateTaskHandler(uow, fixed_clock).handle(UpdateTask(task_id=task.id, title=" "))


async def test_update_unknown_task(uow: FakeUnitOfWork) -> None:
    with pytest.raises(TaskNotFound):
        await UpdateTaskHandler(uow, fixed_clock).handle(UpdateTask(task_id=uuid4(), title="X"))


# --- DeleteTask -----------------------------------------------------------------


async def test_delete_task(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)

    await DeleteTaskHandler(uow).handle(DeleteTask(task_id=task.id))

    assert uow.tasks.tasks == {}
    assert uow.commits == 1


async def test_delete_unknown_task(uow: FakeUnitOfWork) -> None:
    with pytest.raises(TaskNotFound):
        await DeleteTaskHandler(uow).handle(DeleteTask(task_id=uuid4()))


# --- MoveTask -------------------------------------------------------------------


async def test_move_to_empty_column(uow: FakeUnitOfWork, todo: Status, done: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)

    await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=task.id, status_id=done.id))

    moved = uow.tasks.tasks[task.id]
    assert moved.status_id == done.id
    assert moved.position == STEP
    assert moved.completed_at == FIXED_NOW
    assert uow.statuses.locked == sorted([todo.id, done.id])
    assert uow.commits == 1


async def test_move_to_top_of_full_column(uow: FakeUnitOfWork, todo: Status, done: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    first, *_ = await _tasks(uow, done, 50)

    await MoveTaskHandler(uow, fixed_clock).handle(
        MoveTask(task_id=task.id, status_id=done.id, before_id=first.id)
    )

    assert uow.tasks.tasks[task.id].position == STEP / 2
    top_two = [task_id for task_id, _ in await uow.tasks.list_positions(done.id)][:2]
    assert top_two == [task.id, first.id]


async def test_move_to_bottom_of_full_column(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    (task,) = await _tasks(uow, todo, 1)
    *_, last = await _tasks(uow, done, 50)

    await MoveTaskHandler(uow, fixed_clock).handle(
        MoveTask(task_id=task.id, status_id=done.id, after_id=last.id)
    )

    assert uow.tasks.tasks[task.id].position == last.position + STEP


async def test_move_to_top_of_empty_column_without_neighbours(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    (task,) = await _tasks(uow, todo, 1)

    await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=task.id, status_id=done.id))

    assert uow.tasks.positions(done.id) == [STEP]


async def test_move_within_same_column(uow: FakeUnitOfWork, todo: Status) -> None:
    a, b, c = await _tasks(uow, todo, 3)

    await MoveTaskHandler(uow, fixed_clock).handle(
        MoveTask(task_id=c.id, status_id=todo.id, after_id=a.id, before_id=b.id)
    )

    assert _titles(uow, todo) == ["T0", "T2", "T1"]
    assert uow.tasks.tasks[c.id].completed_at is None


async def test_move_out_of_done_column_clears_completion(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    task = make_task(done)
    await uow.tasks.add(task)

    await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=task.id, status_id=todo.id))

    assert uow.tasks.tasks[task.id].completed_at is None


async def test_move_rebalances_column_when_gap_exhausted(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    (task,) = await _tasks(uow, todo, 1)
    a, b, _ = await _tasks(uow, done, 3)
    uow.tasks.tasks[b.id].position = a.position + MIN_GAP / 2

    await MoveTaskHandler(uow, fixed_clock).handle(
        MoveTask(task_id=task.id, status_id=done.id, after_id=a.id, before_id=b.id)
    )

    assert uow.tasks.positions(done.id) == [STEP, 1.5 * STEP, 2 * STEP, 3 * STEP]
    assert uow.tasks.tasks[task.id].position == 1.5 * STEP


async def test_move_with_neighbour_from_other_column_is_stale(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    task, other = await _tasks(uow, todo, 2)

    with pytest.raises(StaleOrdering):
        await MoveTaskHandler(uow, fixed_clock).handle(
            MoveTask(task_id=task.id, status_id=done.id, before_id=other.id)
        )
    assert uow.commits == 0


async def test_move_to_unknown_status(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)

    with pytest.raises(UnknownStatus):
        await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=task.id, status_id=uuid4()))


async def test_move_unknown_task(uow: FakeUnitOfWork, todo: Status) -> None:
    with pytest.raises(TaskNotFound):
        await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=uuid4(), status_id=todo.id))


# --- AssignTask -----------------------------------------------------------------


async def test_assign_and_unassign_task(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    user = make_user()
    await uow.users.add(user)
    handler = AssignTaskHandler(uow, fixed_clock, FakeNotifier())

    await handler.handle(
        AssignTask(task_id=task.id, assignee_id=user.id, assigned_by_id=CREATOR_ID)
    )
    assert uow.tasks.tasks[task.id].assignee_id == user.id

    await handler.handle(AssignTask(task_id=task.id, assignee_id=None, assigned_by_id=CREATOR_ID))
    assert uow.tasks.tasks[task.id].assignee_id is None
    assert uow.commits == 2


async def test_assign_inactive_user(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    user = make_user(is_active=False)
    await uow.users.add(user)

    with pytest.raises(InvalidAssignee):
        await AssignTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
            AssignTask(task_id=task.id, assignee_id=user.id, assigned_by_id=CREATOR_ID)
        )


async def test_assign_unknown_user(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)

    with pytest.raises(InvalidAssignee):
        await AssignTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
            AssignTask(task_id=task.id, assignee_id=uuid4(), assigned_by_id=CREATOR_ID)
        )


async def test_assign_unknown_task(uow: FakeUnitOfWork) -> None:
    with pytest.raises(TaskNotFound):
        await AssignTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
            AssignTask(task_id=uuid4(), assignee_id=None, assigned_by_id=CREATOR_ID)
        )


# --- assignment notifications ---------------------------------------------------


async def _assignable(uow: FakeUnitOfWork, email: str = "bob@example.com") -> UUID:
    user = make_user(email)
    await uow.users.add(user)
    return user.id


async def test_assign_notifies_new_assignee_after_commit(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    bob_id = await _assignable(uow)
    notifier = FakeNotifier(uow)

    await AssignTaskHandler(uow, fixed_clock, notifier).handle(
        AssignTask(task_id=task.id, assignee_id=bob_id, assigned_by_id=CREATOR_ID)
    )

    assert notifier.assignments == [
        Assignment(task_id=task.id, assignee_id=bob_id, assigned_by_id=CREATOR_ID, commits_before=1)
    ]


async def test_assign_does_not_notify_when_unchanged(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    bob_id = await _assignable(uow)
    command = AssignTask(task_id=task.id, assignee_id=bob_id, assigned_by_id=CREATOR_ID)
    await AssignTaskHandler(uow, fixed_clock, FakeNotifier()).handle(command)
    notifier = FakeNotifier()

    await AssignTaskHandler(uow, fixed_clock, notifier).handle(command)

    assert notifier.assignments == []


async def test_assign_does_not_notify_on_unassign(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    bob_id = await _assignable(uow)
    handler = AssignTaskHandler(uow, fixed_clock, FakeNotifier())
    await handler.handle(AssignTask(task_id=task.id, assignee_id=bob_id, assigned_by_id=CREATOR_ID))
    notifier = FakeNotifier()

    await AssignTaskHandler(uow, fixed_clock, notifier).handle(
        AssignTask(task_id=task.id, assignee_id=None, assigned_by_id=CREATOR_ID)
    )

    assert notifier.assignments == []


async def test_assign_does_not_notify_self_assignment(uow: FakeUnitOfWork, todo: Status) -> None:
    (task,) = await _tasks(uow, todo, 1)
    bob_id = await _assignable(uow)
    notifier = FakeNotifier()

    await AssignTaskHandler(uow, fixed_clock, notifier).handle(
        AssignTask(task_id=task.id, assignee_id=bob_id, assigned_by_id=bob_id)
    )

    assert notifier.assignments == []


async def test_assign_does_not_notify_when_commit_fails() -> None:
    uow = FailingCommitUnitOfWork()
    status = make_status("To Do")
    await uow.statuses.add(status)
    (task,) = await _tasks(uow, status, 1)
    bob_id = await _assignable(uow)
    notifier = FakeNotifier()

    with pytest.raises(RuntimeError):
        await AssignTaskHandler(uow, fixed_clock, notifier).handle(
            AssignTask(task_id=task.id, assignee_id=bob_id, assigned_by_id=CREATOR_ID)
        )

    assert notifier.assignments == []


async def test_create_with_assignee_notifies_after_commit(
    uow: FakeUnitOfWork, todo: Status
) -> None:
    bob_id = await _assignable(uow)
    notifier = FakeNotifier(uow)

    task_id = await CreateTaskHandler(uow, fixed_clock, notifier).handle(
        _create(todo.id, assignee_id=bob_id)
    )

    assert notifier.assignments == [
        Assignment(task_id=task_id, assignee_id=bob_id, assigned_by_id=CREATOR_ID, commits_before=1)
    ]


async def test_create_without_assignee_or_for_self_does_not_notify(
    uow: FakeUnitOfWork, todo: Status
) -> None:
    creator_id = await _assignable(uow)
    notifier = FakeNotifier()
    handler = CreateTaskHandler(uow, fixed_clock, notifier)

    await handler.handle(_create(todo.id, created_by_id=creator_id))
    await handler.handle(_create(todo.id, created_by_id=creator_id, assignee_id=creator_id))

    assert notifier.assignments == []


# --- Locking (lost updates, lock order) -------------------------------------------


async def test_update_assign_and_delete_lock_the_task_row(
    uow: FakeUnitOfWork, todo: Status
) -> None:
    (task,) = await _tasks(uow, todo, 1)
    await uow.users.add(user := make_user())

    await UpdateTaskHandler(uow, fixed_clock).handle(UpdateTask(task_id=task.id, title="New"))
    await AssignTaskHandler(uow, fixed_clock, FakeNotifier()).handle(
        AssignTask(task_id=task.id, assignee_id=user.id, assigned_by_id=CREATOR_ID)
    )
    await DeleteTaskHandler(uow).handle(DeleteTask(task_id=task.id))

    assert uow.lock_log == [("task", task.id)] * 3


async def test_move_across_columns_locks_both_columns_in_id_order_then_the_task(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    (task,) = await _tasks(uow, todo, 1)

    await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=task.id, status_id=done.id))

    first, second = sorted([todo.id, done.id])
    assert uow.lock_log == [("status", first), ("status", second), ("task", task.id)]


async def test_move_within_a_column_locks_it_once(uow: FakeUnitOfWork, todo: Status) -> None:
    task, _ = await _tasks(uow, todo, 2)

    await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=task.id, status_id=todo.id))

    assert uow.lock_log == [("status", todo.id), ("task", task.id)]


async def test_move_is_stale_if_task_changed_column_before_it_was_locked(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    (task,) = await _tasks(uow, todo, 1)
    other = make_status("Other", position=3 * STEP)
    await uow.statuses.add(other)
    # Another transaction moves the task to "Other" between the read and the lock.
    uow.tasks.before_lock = lambda t: setattr(t, "status_id", other.id)

    with pytest.raises(StaleOrdering):
        await MoveTaskHandler(uow, fixed_clock).handle(MoveTask(task_id=task.id, status_id=done.id))
    assert uow.commits == 0


async def test_move_rebalance_only_renumbers_the_target_column(
    uow: FakeUnitOfWork, todo: Status, done: Status
) -> None:
    (task,) = await _tasks(uow, todo, 1)
    a, b, _ = await _tasks(uow, done, 3)
    uow.tasks.tasks[b.id].position = a.position + MIN_GAP / 2

    await MoveTaskHandler(uow, fixed_clock).handle(
        MoveTask(task_id=task.id, status_id=done.id, after_id=a.id, before_id=b.id)
    )

    assert uow.tasks.rebalanced_columns == [done.id]
