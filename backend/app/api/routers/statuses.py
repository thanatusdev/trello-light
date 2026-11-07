from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    get_create_status_handler,
    get_delete_status_handler,
    get_list_statuses_handler,
    get_rename_status_handler,
    get_reorder_status_handler,
    get_status_handler,
)
from app.api.pagination import Page, PageParams, page_params
from app.api.schemas.statuses import (
    StatusCreateRequest,
    StatusMoveRequest,
    StatusRenameRequest,
    StatusResponse,
)
from app.api.security import get_current_user
from app.application.commands.create_status import CreateStatus, CreateStatusHandler
from app.application.commands.delete_status import DeleteStatus, DeleteStatusHandler
from app.application.commands.rename_status import RenameStatus, RenameStatusHandler
from app.application.commands.reorder_status import ReorderStatus, ReorderStatusHandler
from app.application.queries.get_status import GetStatus, GetStatusHandler
from app.application.queries.list_statuses import (
    DEFAULT_STATUS_PAGE_SIZE,
    ListStatuses,
    ListStatusesHandler,
)
from app.domain.errors import StatusNotFound

router = APIRouter(
    prefix="/statuses",
    tags=["statuses"],
    dependencies=[Depends(get_current_user)],
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token"}},
)

GetStatusDep = Annotated[GetStatusHandler, Depends(get_status_handler)]

_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": "Status not found"}
}
_NAME_TAKEN: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {"description": "Another status already has this name"}
}


async def _read(get_status: GetStatusHandler, status_id: UUID) -> StatusResponse:
    result = await get_status.handle(GetStatus(status_id))
    if result is None:  # pragma: no cover - just written in the same session
        raise StatusNotFound()
    return StatusResponse.model_validate(result)


@router.get(
    "",
    summary="List columns",
    description=(
        "Columns in board order (left to right), without their tasks. "
        f"`size` defaults to {DEFAULT_STATUS_PAGE_SIZE} so one page is usually the whole board."
    ),
    response_model=Page[StatusResponse],
)
async def list_statuses(
    params: Annotated[PageParams, Depends(page_params(DEFAULT_STATUS_PAGE_SIZE))],
    handler: Annotated[ListStatusesHandler, Depends(get_list_statuses_handler)],
) -> Page[StatusResponse]:
    result = await handler.handle(ListStatuses(page=params.page, size=params.size))
    return Page[StatusResponse](
        items=[StatusResponse.model_validate(s) for s in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
    )


@router.post(
    "",
    summary="Create a column",
    description="Adds a column at the right end of the board. Names are unique ignoring case.",
    status_code=status.HTTP_201_CREATED,
    response_model=StatusResponse,
    responses=_NAME_TAKEN,
)
async def create_status(
    body: StatusCreateRequest,
    handler: Annotated[CreateStatusHandler, Depends(get_create_status_handler)],
    get_status: GetStatusDep,
) -> StatusResponse:
    status_id = await handler.handle(CreateStatus(name=body.name, is_done=body.is_done))
    return await _read(get_status, status_id)


@router.patch(
    "/{status_id}",
    summary="Rename a column",
    response_model=StatusResponse,
    responses=_NOT_FOUND | _NAME_TAKEN,
)
async def rename_status(
    status_id: UUID,
    body: StatusRenameRequest,
    handler: Annotated[RenameStatusHandler, Depends(get_rename_status_handler)],
    get_status: GetStatusDep,
) -> StatusResponse:
    await handler.handle(RenameStatus(status_id=status_id, name=body.name))
    return await _read(get_status, status_id)


@router.post(
    "/{status_id}/move",
    summary="Reorder a column",
    description=(
        "Places the column between `after_id` and `before_id` (as the client sees the board). "
        "With neither, the column moves to the right end."
    ),
    response_model=StatusResponse,
    responses=_NOT_FOUND
    | {status.HTTP_409_CONFLICT: {"description": "Neighbours are stale; refresh the board"}},
)
async def move_status(
    status_id: UUID,
    body: StatusMoveRequest,
    handler: Annotated[ReorderStatusHandler, Depends(get_reorder_status_handler)],
    get_status: GetStatusDep,
) -> StatusResponse:
    await handler.handle(
        ReorderStatus(status_id=status_id, after_id=body.after_id, before_id=body.before_id)
    )
    return await _read(get_status, status_id)


@router.delete(
    "/{status_id}",
    summary="Delete an empty column",
    description="Fails with 409 while the column still has tasks; tasks are never deleted.",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_NOT_FOUND
    | {status.HTTP_409_CONFLICT: {"description": "The column still has tasks"}},
)
async def delete_status(
    status_id: UUID,
    handler: Annotated[DeleteStatusHandler, Depends(get_delete_status_handler)],
) -> None:
    await handler.handle(DeleteStatus(status_id=status_id))
