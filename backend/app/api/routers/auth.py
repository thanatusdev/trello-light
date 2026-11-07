from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import (
    get_authenticate_handler,
    get_logout_handler,
    get_refresh_tokens_handler,
    get_register_user_handler,
    get_user_by_id_handler,
)
from app.api.rate_limit import ip_rate_limit, rate_limited_response
from app.api.schemas.auth import RefreshRequest, RegisterRequest, TokenResponse
from app.api.schemas.users import UserResponse
from app.api.security import CurrentUser
from app.application.commands.authenticate import Authenticate, AuthenticateHandler
from app.application.commands.logout import Logout, LogoutHandler
from app.application.commands.refresh_tokens import RefreshTokens, RefreshTokensHandler
from app.application.commands.register_user import RegisterUser, RegisterUserHandler
from app.application.queries.get_user import GetUserById, GetUserByIdHandler
from app.domain.errors import UserNotFound

router = APIRouter(prefix="/auth", tags=["auth"])

_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials or token"}
}
_STORE_UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Session store is unavailable"}
}
_RATE_LIMITED = rate_limited_response(
    "Too many attempts from this IP; see the `Retry-After` header"
)


@router.post(
    "/register",
    summary="Register a new user",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    responses={
        status.HTTP_409_CONFLICT: {"description": "Email is already registered"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "Invalid email, name or password"},
        **_RATE_LIMITED,
    },
    dependencies=[Depends(ip_rate_limit(lambda s: s.rate_limit_register))],
)
async def register(
    body: RegisterRequest,
    handler: Annotated[RegisterUserHandler, Depends(get_register_user_handler)],
    get_user: Annotated[GetUserByIdHandler, Depends(get_user_by_id_handler)],
) -> UserResponse:
    user_id = await handler.handle(
        RegisterUser(email=body.email, full_name=body.full_name, password=body.password)
    )
    user = await get_user.handle(GetUserById(user_id))
    if user is None:  # pragma: no cover - just committed in the same session
        raise UserNotFound()
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    summary="Log in with email and password",
    description=(
        "OAuth2 password flow: send the email as `username`. "
        "Returns an access token and a refresh token."
    ),
    response_model=TokenResponse,
    responses=_UNAUTHORIZED | _RATE_LIMITED,
    dependencies=[Depends(ip_rate_limit(lambda s: s.rate_limit_login))],
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    handler: Annotated[AuthenticateHandler, Depends(get_authenticate_handler)],
) -> TokenResponse:
    pair = await handler.handle(Authenticate(email=form.username, password=form.password))
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post(
    "/refresh",
    summary="Exchange a refresh token for a new token pair",
    description=(
        "Each refresh token works once. Replaying a spent token rejects it, and after a short "
        "grace period also ends the whole session it came from."
    ),
    response_model=TokenResponse,
    responses=_UNAUTHORIZED | _STORE_UNAVAILABLE,
)
async def refresh(
    body: RefreshRequest,
    handler: Annotated[RefreshTokensHandler, Depends(get_refresh_tokens_handler)],
) -> TokenResponse:
    pair = await handler.handle(RefreshTokens(refresh_token=body.refresh_token))
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post(
    "/logout",
    summary="End the session a refresh token belongs to",
    description=(
        "Revokes the refresh token and every token rotated from it. Needs no access token, so "
        "a client whose access token expired can still log out. Invalid tokens are ignored."
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_STORE_UNAVAILABLE,
)
async def logout(
    body: RefreshRequest,
    handler: Annotated[LogoutHandler, Depends(get_logout_handler)],
) -> None:
    await handler.handle(Logout(refresh_token=body.refresh_token))


@router.get(
    "/me",
    summary="Get the authenticated user",
    response_model=UserResponse,
    responses=_UNAUTHORIZED,
)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
