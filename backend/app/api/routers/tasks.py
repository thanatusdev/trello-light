from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    get_assign_task_handler,
    get_create_task_handler,
    get_delete_task_handler,
    get_list_tasks_handler,
    get_move_task_handler,
    get_task_handler,
    get_update_task_handler,
)
from app.api.filters import get_task_filters
from app.api.pagination import Page, PageParams, get_page_params
from app.api.schemas.tasks import (
    TaskAssignRequest,
    TaskCreateRequest,
    TaskMoveRequest,
    TaskResponse,
    TaskUpdateRequest,
)
from app.api.security import CurrentUser
from app.application.commands.assign_task import AssignTask, AssignTaskHandler
from app.application.commands.create_task import CreateTask, CreateTaskHandler
from app.application.commands.delete_task import DeleteTask, DeleteTaskHandler
from app.application.commands.move_task import MoveTask, MoveTaskHandler
from app.application.commands.update_task import UNSET, UpdateTask, UpdateTaskHandler
from app.application.queries.tasks import (
    GetTask,
    GetTaskHandler,
    ListTasks,
    ListTasksHandler,
    TaskFilters,
)
from app.domain.errors import TaskNotFound

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token"}},
)

GetTaskDep = Annotated[GetTaskHandler, Depends(get_task_handler)]

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "Task not found"}
}
_INVALID: dict[int | str, dict[str, Any]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "description": "Invalid field, unknown status/assignee, or due date in the past"
    }
}


async def _read(get_task: GetTaskHandler, task_id: UUID) -> TaskResponse:
    result = await get_task.handle(GetTask(task_id))
    if result is None:
        raise TaskNotFound()
    return TaskResponse.model_validate(result)


@router.post(
    "",
    summary="Create a task",
    description="The task goes to the bottom of its column. Creating it in a done column "
    "marks it completed.",
    status_code=status.HTTP_201_CREATED,
    response_model=TaskResponse,
    responses=_INVALID,
)
async def create_task(
    body: TaskCreateRequest,
    current_user: CurrentUser,
    handler: Annotated[CreateTaskHandler, Depends(get_create_task_handler)],
    get_task: GetTaskDep,
) -> TaskResponse:
    task_id = await handler.handle(
        CreateTask(
            title=body.title,
            description=body.description,
            status_id=body.status_id,
            created_by_id=current_user.id,
            assignee_id=body.assignee_id,
            due_date=body.due_date,
        )
    )
    return await _read(get_task, task_id)


@router.get(
    "",
    summary="List tasks",
    description="Filtered and paginated, newest first. Filters combine with AND.",
    response_model=Page[TaskResponse],
)
async def list_tasks(
    _: CurrentUser,
    params: Annotated[PageParams, Depends(get_page_params)],
    filters: Annotated[TaskFilters, Depends(get_task_filters)],
    handler: Annotated[ListTasksHandler, Depends(get_list_tasks_handler)],
) -> Page[TaskResponse]:
    result = await handler.handle(ListTasks(page=params.page, size=params.size, filters=filters))
    return Page[TaskResponse](
        items=[TaskResponse.model_validate(t) for t in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
    )


@router.get(
    "/{task_id}",
    summary="Get a task",
    response_model=TaskResponse,
    responses=_NOT_FOUND,
)
async def get_task(task_id: UUID, _: CurrentUser, get_task: GetTaskDep) -> TaskResponse:
    return await _read(get_task, task_id)


@router.patch(
    "/{task_id}",
    summary="Update a task's title, description or due date",
    description="Omitted fields are unchanged; `null` clears description or due date.",
    response_model=TaskResponse,
    responses=_NOT_FOUND | _INVALID,
)
async def update_task(
    task_id: UUID,
    body: TaskUpdateRequest,
    _: CurrentUser,
    handler: Annotated[UpdateTaskHandler, Depends(get_update_task_handler)],
    get_task: GetTaskDep,
) -> TaskResponse:
    sent = body.model_fields_set
    await handler.handle(
        UpdateTask(
            task_id=task_id,
            title=body.title if "title" in sent and body.title is not None else UNSET,
            description=body.description if "description" in sent else UNSET,
            due_date=body.due_date if "due_date" in sent else UNSET,
        )
    )
    return await _read(get_task, task_id)


@router.delete(
    "/{task_id}",
    summary="Delete a task",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_NOT_FOUND,
)
async def delete_task(
    task_id: UUID,
    _: CurrentUser,
    handler: Annotated[DeleteTaskHandler, Depends(get_delete_task_handler)],
) -> None:
    await handler.handle(DeleteTask(task_id=task_id))


@router.post(
    "/{task_id}/move",
    summary="Move a task to a column and position",
    description=(
        "Places the task in `status_id` between `after_id` and `before_id`. With neither, it "
        "goes to the bottom. Moving into a done column sets `completed_at`; moving out clears it."
    ),
    response_model=TaskResponse,
    responses=_NOT_FOUND
    | _INVALID
    | {status.HTTP_409_CONFLICT: {"description": "Neighbours are stale; refresh the board"}},
)
async def move_task(
    task_id: UUID,
    body: TaskMoveRequest,
    _: CurrentUser,
    handler: Annotated[MoveTaskHandler, Depends(get_move_task_handler)],
    get_task: GetTaskDep,
) -> TaskResponse:
    await handler.handle(
        MoveTask(
            task_id=task_id,
            status_id=body.status_id,
            after_id=body.after_id,
            before_id=body.before_id,
        )
    )
    return await _read(get_task, task_id)


@router.put(
    "/{task_id}/assignee",
    summary="Assign or unassign a task",
    description="A new assignee other than yourself is sent an email notification.",
    response_model=TaskResponse,
    responses=_NOT_FOUND
    | {status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Assignee unknown or inactive"}},
)
async def assign_task(
    task_id: UUID,
    body: TaskAssignRequest,
    current_user: CurrentUser,
    handler: Annotated[AssignTaskHandler, Depends(get_assign_task_handler)],
    get_task: GetTaskDep,
) -> TaskResponse:
    await handler.handle(
        AssignTask(task_id=task_id, assignee_id=body.assignee_id, assigned_by_id=current_user.id)
    )
    return await _read(get_task, task_id)
