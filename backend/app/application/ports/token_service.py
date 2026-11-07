from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(frozen=True, slots=True)
class RefreshClaims:
    """What a valid refresh token says.

    ``session_id`` is shared by every refresh token descended from one login;
    ``expires_at`` is that login's absolute end, carried forward on rotation.
    """

    user_id: UUID
    token_id: str
    session_id: str
    expires_at: datetime


class TokenService(Protocol):
    def issue_pair(self, user_id: UUID) -> TokenPair:
        """Start a new session (on login)."""
        ...

    def rotate(self, claims: RefreshClaims) -> TokenPair:
        """New pair in the same session; the refresh token keeps ``claims.expires_at``."""
        ...

    def decode(self, token: str, expected_type: TokenType) -> UUID:
        """Return the subject's user id, or raise ``InvalidToken``."""
        ...

    def decode_refresh(self, token: str) -> RefreshClaims:
        """Validate a refresh token and return its claims, or raise ``InvalidToken``."""
        ...
