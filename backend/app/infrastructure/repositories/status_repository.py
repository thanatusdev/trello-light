from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import delete, exists, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import StatusHasTasks, StatusNameTaken
from app.domain.statuses import Status, StatusName
from app.infrastructure.models.status import StatusModel
from app.infrastructure.models.task import TaskModel

# Fixed key for pg_advisory_xact_lock; any constant bigint unique to this app works.
BOARD_LOCK_KEY = 0x7472656C6C6F  # "trello"


def _to_entity(model: StatusModel) -> Status:
    return Status(
        id=model.id,
        name=StatusName(model.name),
        position=model.position,
        is_done=model.is_done,
        created_at=model.created_at,
    )


class SqlAlchemyStatusRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, status: Status) -> None:
        model = StatusModel(
            id=status.id,
            name=status.name.value,
            position=status.position,
            is_done=status.is_done,
            created_at=status.created_at,
        )
        # The unique index on lower(name) catches a concurrent create that raced past the
        # handler's own name check. Adding inside the savepoint means a failed insert is
        # expunged on rollback instead of lingering in the session.
        try:
            async with self._session.begin_nested():
                self._session.add(model)
                await self._session.flush()
        except IntegrityError as exc:
            raise StatusNameTaken() from exc

    async def get(self, status_id: UUID) -> Status | None:
        model = await self._session.get(StatusModel, status_id)
        return _to_entity(model) if model else None

    async def lock_board(self) -> None:
        # Transaction-scoped: released automatically on commit or rollback.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:key)").bindparams(key=BOARD_LOCK_KEY)
        )

    async def get_for_update(self, status_id: UUID) -> Status | None:
        stmt = (
            select(StatusModel)
            .where(StatusModel.id == status_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = await self._session.scalar(stmt)
        return _to_entity(model) if model else None

    async def get_by_name(self, name: StatusName) -> Status | None:
        stmt = select(StatusModel).where(func.lower(StatusModel.name) == name.value.lower())
        model = await self._session.scalar(stmt)
        return _to_entity(model) if model else None

    async def list_for_update(self) -> list[Status]:
        # Rows are locked in id order (the lock order shared with task moves, see
        # domain/repositories.py), then sorted into board order here.
        stmt = (
            select(StatusModel)
            .order_by(StatusModel.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        statuses = [_to_entity(m) for m in await self._session.scalars(stmt)]
        return sorted(statuses, key=lambda s: (s.position, s.id))

    async def save(self, status: Status) -> None:
        try:
            async with self._session.begin_nested():
                await self._session.execute(
                    update(StatusModel)
                    .where(StatusModel.id == status.id)
                    .values(name=status.name.value, position=status.position)
                )
        except IntegrityError as exc:
            raise StatusNameTaken() from exc

    async def set_positions(self, positions: Mapping[UUID, float]) -> None:
        if positions:
            await self._session.execute(
                update(StatusModel),
                [{"id": status_id, "position": pos} for status_id, pos in positions.items()],
            )

    async def has_tasks(self, status_id: UUID) -> bool:
        stmt = select(exists().where(TaskModel.status_id == status_id))
        return bool(await self._session.scalar(stmt))

    async def delete(self, status_id: UUID) -> None:
        # The RESTRICT foreign key is the last line of defence against orphaning tasks.
        try:
            async with self._session.begin_nested():
                await self._session.execute(delete(StatusModel).where(StatusModel.id == status_id))
        except IntegrityError as exc:
            raise StatusHasTasks() from exc
