from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.get_status import GetStatus, StatusRead
from app.application.queries.list_statuses import ListStatuses
from app.application.queries.pagination import PageResult
from app.infrastructure.models.status import StatusModel


def _status_select() -> Select[tuple[UUID, str, float, bool, datetime]]:
    return select(
        StatusModel.id,
        StatusModel.name,
        StatusModel.position,
        StatusModel.is_done,
        StatusModel.created_at,
    )


class SqlAlchemyGetStatusHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: GetStatus) -> StatusRead | None:
        stmt = _status_select().where(StatusModel.id == query.status_id)
        row = (await self._session.execute(stmt)).one_or_none()
        return StatusRead(**row._mapping) if row else None


class SqlAlchemyListStatusesHandler:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def handle(self, query: ListStatuses) -> PageResult[StatusRead]:
        total = await self._session.scalar(select(func.count()).select_from(StatusModel)) or 0
        stmt = (
            _status_select()
            .order_by(StatusModel.position, StatusModel.id)
            .offset(query.offset)
            .limit(query.size)
        )
        rows = (await self._session.execute(stmt)).all()
        return PageResult(
            items=[StatusRead(**row._mapping) for row in rows],
            total=total,
            page=query.page,
            size=query.size,
        )
