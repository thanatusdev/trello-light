"""End the session a refresh token belongs to, including every token rotated from it.

Idempotent, and silent for invalid or expired tokens: there is nothing left to revoke, and
the client clears its own tokens either way.
"""

from dataclasses import dataclass, field

from app.application.ports.refresh_token_store import RefreshTokenStore
from app.application.ports.token_service import TokenService
from app.domain.errors import InvalidToken


@dataclass(frozen=True, slots=True)
class Logout:
    refresh_token: str = field(repr=False)


class LogoutHandler:
    def __init__(self, tokens: TokenService, store: RefreshTokenStore) -> None:
        self._tokens = tokens
        self._store = store

    async def handle(self, command: Logout) -> None:
        try:
            claims = self._tokens.decode_refresh(command.refresh_token)
        except InvalidToken:
            return
        await self._store.revoke_session(claims.session_id, expires_at=claims.expires_at)
