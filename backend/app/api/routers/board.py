from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_board_handler
from app.api.filters import get_task_filters
from app.api.schemas.board import BoardResponse
from app.api.security import get_current_user
from app.application.queries.board import GetBoard, GetBoardHandler
from app.application.queries.tasks import TaskFilters

router = APIRouter(
    prefix="/board",
    tags=["board"],
    dependencies=[Depends(get_current_user)],
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token"}},
)


@router.get(
    "",
    summary="Get the board",
    description=(
        "Every column ordered by position, each with its tasks ordered by position. Accepts the "
        "same filters as `GET /tasks`; filters narrow tasks but never hide columns."
    ),
    response_model=BoardResponse,
)
async def get_board(
    filters: Annotated[TaskFilters, Depends(get_task_filters)],
    handler: Annotated[GetBoardHandler, Depends(get_board_handler)],
) -> BoardResponse:
    return BoardResponse.model_validate(await handler.handle(GetBoard(filters)))
