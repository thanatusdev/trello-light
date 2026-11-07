from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_list_users_handler
from app.api.pagination import Page, PageParams, get_page_params
from app.api.schemas.users import UserSummaryResponse
from app.api.security import get_current_user
from app.application.queries.list_users import ListUsers, ListUsersHandler

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid token"}},
)


@router.get(
    "",
    summary="List active users",
    description="Active users ordered by name, for the assignee picker.",
    response_model=Page[UserSummaryResponse],
)
async def list_users(
    params: Annotated[PageParams, Depends(get_page_params)],
    handler: Annotated[ListUsersHandler, Depends(get_list_users_handler)],
) -> Page[UserSummaryResponse]:
    result = await handler.handle(ListUsers(page=params.page, size=params.size))
    return Page[UserSummaryResponse](
        items=[UserSummaryResponse.model_validate(u) for u in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
    )
