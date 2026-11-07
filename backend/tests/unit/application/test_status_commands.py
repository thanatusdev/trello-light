from uuid import uuid4

import pytest

from app.application.commands.create_status import CreateStatus, CreateStatusHandler
from app.application.commands.delete_status import DeleteStatus, DeleteStatusHandler
from app.application.commands.rename_status import RenameStatus, RenameStatusHandler
from app.application.commands.reorder_status import ReorderStatus, ReorderStatusHandler
from app.domain.errors import (
    StaleOrdering,
    StatusHasTasks,
    StatusNameTaken,
    StatusNotFound,
    ValidationError,
)
from app.domain.ordering import STEP
from app.domain.statuses import Status, StatusName
from tests.unit.application.fakes import (
    FIXED_NOW,
    FakeUnitOfWork,
    fixed_clock,
    make_status,
    make_task,
)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


async def _seed(uow: FakeUnitOfWork, *names: str) -> list[Status]:
    statuses = [make_status(name, position=STEP * (i + 1)) for i, name in enumerate(names)]
    for status in statuses:
        await uow.statuses.add(status)
    return statuses


def _order(uow: FakeUnitOfWork) -> list[str]:
    return [s.name.value for s in sorted(uow.statuses.statuses.values(), key=lambda s: s.position)]


# --- CreateStatus ---------------------------------------------------------------


async def test_create_first_status(uow: FakeUnitOfWork) -> None:
    status_id = await CreateStatusHandler(uow, fixed_clock).handle(
        CreateStatus(name=" Done ", is_done=True)
    )

    status = uow.statuses.statuses[status_id]
    assert status.name == StatusName("Done")
    assert status.is_done is True
    assert status.position == STEP
    assert status.created_at == FIXED_NOW
    assert uow.commits == 1


async def test_create_status_appends_after_last(uow: FakeUnitOfWork) -> None:
    await _seed(uow, "To Do", "Doing")

    status_id = await CreateStatusHandler(uow, fixed_clock).handle(CreateStatus(name="Done"))

    assert uow.statuses.statuses[status_id].position == 3 * STEP
    assert uow.statuses.statuses[status_id].is_done is False


async def test_create_status_rejects_duplicate_name_case_insensitively(
    uow: FakeUnitOfWork,
) -> None:
    await _seed(uow, "Done")

    with pytest.raises(StatusNameTaken):
        await CreateStatusHandler(uow, fixed_clock).handle(CreateStatus(name="  DONE "))
    assert uow.commits == 0


async def test_create_status_rejects_blank_name(uow: FakeUnitOfWork) -> None:
    with pytest.raises(ValidationError):
        await CreateStatusHandler(uow, fixed_clock).handle(CreateStatus(name="  "))


# --- RenameStatus ---------------------------------------------------------------


async def test_rename_status(uow: FakeUnitOfWork) -> None:
    (status,) = await _seed(uow, "Todo")

    await RenameStatusHandler(uow).handle(RenameStatus(status_id=status.id, name="To Do"))

    assert uow.statuses.statuses[status.id].name == StatusName("To Do")
    assert uow.commits == 1


async def test_rename_status_to_different_casing_of_itself(uow: FakeUnitOfWork) -> None:
    (status,) = await _seed(uow, "todo")

    await RenameStatusHandler(uow).handle(RenameStatus(status_id=status.id, name="Todo"))

    assert uow.statuses.statuses[status.id].name == StatusName("Todo")


async def test_rename_status_to_existing_name_conflicts(uow: FakeUnitOfWork) -> None:
    todo, _ = await _seed(uow, "To Do", "Done")

    with pytest.raises(StatusNameTaken):
        await RenameStatusHandler(uow).handle(RenameStatus(status_id=todo.id, name="done"))


async def test_rename_unknown_status(uow: FakeUnitOfWork) -> None:
    with pytest.raises(StatusNotFound):
        await RenameStatusHandler(uow).handle(RenameStatus(status_id=uuid4(), name="X"))


# --- ReorderStatus --------------------------------------------------------------


async def test_reorder_status_to_top(uow: FakeUnitOfWork) -> None:
    a, _, c = await _seed(uow, "A", "B", "C")

    await ReorderStatusHandler(uow).handle(ReorderStatus(status_id=c.id, before_id=a.id))

    assert _order(uow) == ["C", "A", "B"]
    assert uow.commits == 1
    assert set(uow.statuses.locked) == {s for s in uow.statuses.statuses}


async def test_reorder_status_to_bottom(uow: FakeUnitOfWork) -> None:
    a, _, _ = await _seed(uow, "A", "B", "C")

    await ReorderStatusHandler(uow).handle(ReorderStatus(status_id=a.id))

    assert _order(uow) == ["B", "C", "A"]


async def test_reorder_status_between(uow: FakeUnitOfWork) -> None:
    a, b, c = await _seed(uow, "A", "B", "C")

    await ReorderStatusHandler(uow).handle(
        ReorderStatus(status_id=c.id, after_id=a.id, before_id=b.id)
    )

    assert _order(uow) == ["A", "C", "B"]


async def test_reorder_status_rebalances_when_gap_exhausted(uow: FakeUnitOfWork) -> None:
    a, b, c = await _seed(uow, "A", "B", "C")
    uow.statuses.statuses[b.id].position = a.position + 1e-7

    await ReorderStatusHandler(uow).handle(
        ReorderStatus(status_id=c.id, after_id=a.id, before_id=b.id)
    )

    assert _order(uow) == ["A", "C", "B"]
    assert sorted(s.position for s in uow.statuses.statuses.values()) == [
        STEP,
        1.5 * STEP,
        2 * STEP,
    ]


async def test_reorder_status_with_stale_neighbours(uow: FakeUnitOfWork) -> None:
    a, _, c = await _seed(uow, "A", "B", "C")

    with pytest.raises(StaleOrdering):
        await ReorderStatusHandler(uow).handle(
            ReorderStatus(status_id=c.id, after_id=a.id, before_id=c.id)
        )
    assert uow.commits == 0


async def test_reorder_unknown_status(uow: FakeUnitOfWork) -> None:
    with pytest.raises(StatusNotFound):
        await ReorderStatusHandler(uow).handle(ReorderStatus(status_id=uuid4()))


# --- DeleteStatus ---------------------------------------------------------------


async def test_delete_empty_status(uow: FakeUnitOfWork) -> None:
    (status,) = await _seed(uow, "A")

    await DeleteStatusHandler(uow).handle(DeleteStatus(status_id=status.id))

    assert uow.statuses.statuses == {}
    assert uow.statuses.locked == [status.id]
    assert uow.commits == 1


async def test_delete_status_with_tasks_conflicts(uow: FakeUnitOfWork) -> None:
    (status,) = await _seed(uow, "A")
    await uow.tasks.add(make_task(status))

    with pytest.raises(StatusHasTasks):
        await DeleteStatusHandler(uow).handle(DeleteStatus(status_id=status.id))
    assert status.id in uow.statuses.statuses
    assert uow.commits == 0


async def test_delete_unknown_status(uow: FakeUnitOfWork) -> None:
    with pytest.raises(StatusNotFound):
        await DeleteStatusHandler(uow).handle(DeleteStatus(status_id=uuid4()))


# --- Board lock -----------------------------------------------------------------


async def test_create_status_takes_board_lock_before_reading_columns(uow: FakeUnitOfWork) -> None:
    await _seed(uow, "A")

    await CreateStatusHandler(uow, fixed_clock).handle(CreateStatus(name="B"))

    assert uow.lock_log[0] == ("board", None)
    assert len(uow.lock_log) == 2  # then the existing column row


async def test_reorder_status_takes_board_lock_before_reading_columns(
    uow: FakeUnitOfWork,
) -> None:
    a, b = await _seed(uow, "A", "B")

    await ReorderStatusHandler(uow).handle(ReorderStatus(status_id=b.id, before_id=a.id))

    assert uow.lock_log[0] == ("board", None)
    assert sorted(uow.lock_log[1:]) == sorted(("status", s) for s in (a.id, b.id))
