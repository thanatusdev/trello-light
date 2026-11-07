from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.api.dependencies import TokenServiceDep, get_user_by_id_handler
from app.application.ports.token_service import TokenType
from app.application.queries.get_user import GetUserById, GetUserByIdHandler, UserRead
from app.domain.errors import InvalidToken

# auto_error=False so a missing token produces the same 401 body as any other bad token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    tokens: TokenServiceDep,
    get_user: Annotated[GetUserByIdHandler, Depends(get_user_by_id_handler)],
) -> UserRead:
    if not token:
        raise InvalidToken()
    user_id = tokens.decode(token, TokenType.ACCESS)
    user = await get_user.handle(GetUserById(user_id))
    if user is None or not user.is_active:
        raise InvalidToken()
    return user


CurrentUser = Annotated[UserRead, Depends(get_current_user)]
