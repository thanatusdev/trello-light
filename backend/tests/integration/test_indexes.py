from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _index_definitions(session: AsyncSession) -> dict[str, str]:
    rows = await session.execute(
        text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'tasks'")
    )
    return {row.indexname: row.indexdef for row in rows}


async def test_task_list_ordering_is_indexed(db_session: AsyncSession) -> None:
    indexes = await _index_definitions(db_session)

    # GET /tasks orders by created_at DESC, id and pages with LIMIT/OFFSET.
    assert "(created_at DESC, id)" in indexes["ix_tasks_created_at_desc_id"]


async def test_due_date_filters_are_indexed(db_session: AsyncSession) -> None:
    indexes = await _index_definitions(db_session)

    assert "(due_date)" in indexes["ix_tasks_due_date"]
