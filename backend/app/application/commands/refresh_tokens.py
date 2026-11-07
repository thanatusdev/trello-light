"""Exchange a valid refresh token for a new token pair, rotating it within its session.

Each refresh token can be spent once. Presenting a spent token again means either a benign
race (two tabs refreshing at once) or a stolen token being replayed:

- within ``REUSE_GRACE`` of the first use it is only rejected, so the tab that won the race
  keeps the session;
- after that the whole session is revoked, signing out both the thief and the real user.

The store is consulted on every refresh and failures propagate, so an outage fails closed.
Like ``authenticate``, this returns tokens rather than an id.
"""

from dataclasses import dataclass, field
from datetime import timedelta

from app.application.ports.clock import Clock
from app.application.ports.refresh_token_store import RefreshTokenStore
from app.application.ports.token_service import TokenPair, TokenService
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import InvalidToken

REUSE_GRACE = timedelta(seconds=10)


@dataclass(frozen=True, slots=True)
class RefreshTokens:
    refresh_token: str = field(repr=False)


class RefreshTokensHandler:
    def __init__(
        self, uow: UnitOfWork, tokens: TokenService, store: RefreshTokenStore, clock: Clock
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._store = store
        self._clock = clock

    async def handle(self, command: RefreshTokens) -> TokenPair:
        claims = self._tokens.decode_refresh(command.refresh_token)
        if await self._store.is_revoked(claims.session_id):
            raise InvalidToken()

        now = self._clock()
        first_used_at = await self._store.mark_used(
            claims.token_id, at=now, expires_at=claims.expires_at
        )
        if first_used_at is not None:
            if now - first_used_at > REUSE_GRACE:
                await self._store.revoke_session(claims.session_id, expires_at=claims.expires_at)
            raise InvalidToken()

        user = await self._uow.users.get_by_id(claims.user_id)
        if user is None or not user.is_active:
            raise InvalidToken()
        return self._tokens.rotate(claims)
