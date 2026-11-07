from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Query

from app.application.queries.tasks import TaskFilters


def get_task_filters(
    status_id: Annotated[UUID | None, Query(description="Only tasks in this column")] = None,
    assignee_id: Annotated[
        UUID | None, Query(description="Only tasks assigned to this user")
    ] = None,
    due_before: Annotated[date | None, Query(description="Due on or before (inclusive)")] = None,
    due_after: Annotated[date | None, Query(description="Due on or after (inclusive)")] = None,
    is_completed: Annotated[
        bool | None, Query(description="true: in a done column; false: not")
    ] = None,
    search: Annotated[
        str | None, Query(max_length=200, description="Case-insensitive title substring")
    ] = None,
) -> TaskFilters:
    # TaskFilters rejects due_after > due_before with a domain ValidationError (422).
    return TaskFilters(
        status_id=status_id,
        assignee_id=assignee_id,
        due_before=due_before,
        due_after=due_after,
        is_completed=is_completed,
        search=search,
    )
