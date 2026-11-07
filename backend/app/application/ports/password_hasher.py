from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, hashed_password: str) -> bool: ...

    def verify_dummy(self, password: str) -> None:
        """Spend the same time as ``verify`` so unknown emails can't be detected by timing."""
        ...
