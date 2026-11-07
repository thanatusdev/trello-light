from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.get_status import StatusRead
from app.application.queries.list_statuses import ListStatuses
from app.domain.statuses import Status, StatusName
from app.infrastructure.queries.statuses import SqlAlchemyListStatusesHandler
from app.infrastructure.repositories.status_repository import SqlAlchemyStatusRepository

CREATED = datetime(2026, 1, 1, tzinfo=UTC)
SEEDED = ["To Do", "In Progress", "Done"]


async def _add(session: AsyncSession, name: str, position: float) -> Status:
    status = Status.create(name=StatusName(name), is_done=False, position=position, now=CREATED)
    await SqlAlchemyStatusRepository(session).add(status)
    return status


async def test_list_statuses_in_board_order_with_pagination(db_session: AsyncSession) -> None:
    # Seeded columns sit at 1024, 2048, 3072.
    first = await _add(db_session, "Backlog", 10.0)
    last = await _add(db_session, "Archive", 9000.0)
    handler = SqlAlchemyListStatusesHandler(db_session)

    page1 = await handler.handle(ListStatuses(page=1, size=2))
    page3 = await handler.handle(ListStatuses(page=3, size=2))
    beyond = await handler.handle(ListStatuses(page=4, size=2))

    assert [s.name for s in page1.items] == ["Backlog", "To Do"]
    assert page1.items[0] == StatusRead(
        id=first.id, name="Backlog", position=10.0, is_done=False, created_at=CREATED
    )
    assert [s.id for s in page3.items] == [last.id]
    assert (page1.total, page1.pages) == (5, 3)
    assert beyond.items == []
    assert beyond.total == 5


async def test_list_statuses_breaks_position_ties_by_id(db_session: AsyncSession) -> None:
    a = await _add(db_session, "Tie A", 5000.0)
    b = await _add(db_session, "Tie B", 5000.0)

    result = await SqlAlchemyListStatusesHandler(db_session).handle(ListStatuses(size=100))

    tied = [s.id for s in result.items if s.position == 5000.0]
    assert tied == sorted([a.id, b.id])
