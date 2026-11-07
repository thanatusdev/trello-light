from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt

from app.application.ports.clock import Clock
from app.application.ports.token_service import RefreshClaims, TokenPair, TokenType
from app.domain.errors import InvalidToken

ALGORITHM = "HS256"


class JwtTokenService:
    def __init__(
        self, *, secret: str, access_ttl: timedelta, refresh_ttl: timedelta, clock: Clock
    ) -> None:
        self._secret = secret
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self._clock = clock

    def issue_pair(self, user_id: UUID) -> TokenPair:
        now = self._clock()
        return self._pair(user_id, session_id=str(uuid4()), refresh_exp=now + self._refresh_ttl)

    def rotate(self, claims: RefreshClaims) -> TokenPair:
        return self._pair(
            claims.user_id, session_id=claims.session_id, refresh_exp=claims.expires_at
        )

    def decode(self, token: str, expected_type: TokenType) -> UUID:
        return UUID(self._claims(token, expected_type)["sub"])

    def decode_refresh(self, token: str) -> RefreshClaims:
        claims = self._claims(token, TokenType.REFRESH, require=("jti", "sid"))
        return RefreshClaims(
            user_id=UUID(claims["sub"]),
            token_id=str(claims["jti"]),
            session_id=str(claims["sid"]),
            expires_at=datetime.fromtimestamp(int(claims["exp"]), UTC),
        )

    def _claims(
        self, token: str, expected_type: TokenType, require: tuple[str, ...] = ()
    ) -> dict[str, Any]:
        try:
            # Expiry is checked against the injected clock below, not pyjwt's wall clock.
            claims: dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                options={
                    "require": ["exp", "sub", "type", *require],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            if claims["type"] != expected_type.value:
                raise InvalidToken()
            if int(claims["exp"]) <= int(self._clock().timestamp()):
                raise InvalidToken()
            UUID(claims["sub"])
            return claims
        except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
            raise InvalidToken() from exc

    def _pair(self, user_id: UUID, *, session_id: str, refresh_exp: datetime) -> TokenPair:
        now = self._clock()
        access = {
            "sub": str(user_id),
            "type": TokenType.ACCESS.value,
            "iat": now,
            "exp": now + self._access_ttl,
            "jti": str(uuid4()),
        }
        refresh = {
            "sub": str(user_id),
            "type": TokenType.REFRESH.value,
            "iat": now,
            "exp": refresh_exp,
            "jti": str(uuid4()),
            "sid": session_id,
        }
        return TokenPair(
            access_token=jwt.encode(access, self._secret, algorithm=ALGORITHM),
            refresh_token=jwt.encode(refresh, self._secret, algorithm=ALGORITHM),
        )
