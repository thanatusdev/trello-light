import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.errors import ValidationError

EMAIL_MAX_LENGTH = 254
FULL_NAME_MAX_LENGTH = 100
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_BYTES = 72  # bcrypt only uses the first 72 bytes.

# Deliberately simple: one "@", no whitespace, a dot in the domain part.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalised = self.value.strip().lower()
        if len(normalised) > EMAIL_MAX_LENGTH or not _EMAIL_PATTERN.match(normalised):
            raise ValidationError("Invalid email address", field="email")
        object.__setattr__(self, "value", normalised)


@dataclass(frozen=True, slots=True)
class FullName:
    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not 1 <= len(trimmed) <= FULL_NAME_MAX_LENGTH:
            raise ValidationError(
                f"Full name must be 1-{FULL_NAME_MAX_LENGTH} characters", field="full_name"
            )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True, slots=True)
class PlainPassword:
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if len(self.value) < PASSWORD_MIN_LENGTH:
            raise ValidationError(
                f"Password must be at least {PASSWORD_MIN_LENGTH} characters", field="password"
            )
        if len(self.value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValidationError(
                f"Password must be at most {PASSWORD_MAX_BYTES} bytes", field="password"
            )


@dataclass(slots=True)
class User:
    id: UUID
    email: Email
    full_name: FullName
    hashed_password: str
    is_active: bool
    created_at: datetime

    @classmethod
    def register(
        cls, *, email: Email, full_name: FullName, hashed_password: str, now: datetime
    ) -> "User":
        return cls(
            id=uuid4(),
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            is_active=True,
            created_at=now,
        )
