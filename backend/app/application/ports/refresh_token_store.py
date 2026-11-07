from datetime import datetime
from typing import Protocol


class RefreshTokenStore(Protocol):
    """Server-side memory for refresh tokens: which were spent, which sessions ended.

    Entries only need to live until ``expires_at``; after that the token is rejected anyway.
    Implementations raise ``TokenStoreUnavailable`` when they can't answer, so callers fail closed.
    """

    async def mark_used(
        self, token_id: str, *, at: datetime, expires_at: datetime
    ) -> datetime | None:
        """Record the token as spent. Atomic: returns when it was first used if it already was."""
        ...

    async def revoke_session(self, session_id: str, *, expires_at: datetime) -> None: ...

    async def is_revoked(self, session_id: str) -> bool: ...
