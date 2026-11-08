from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.errors import ValidationError

STATUS_NAME_MAX_LENGTH = 50


@dataclass(frozen=True, slots=True)
class StatusName:
    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not 1 <= len(trimmed) <= STATUS_NAME_MAX_LENGTH:
            raise ValidationError(
                f"Status name must be 1-{STATUS_NAME_MAX_LENGTH} characters", field="name"
            )
        object.__setattr__(self, "value", trimmed)

    def matches(self, other: "StatusName") -> bool:
        """Names are unique case-insensitively, but stored with the casing the user typed.
        Uses ``lower()`` to match the database's unique index on ``lower(name)``."""
        return self.value.lower() == other.value.lower()


@dataclass(slots=True)
class Status:
    id: UUID
    name: StatusName
    position: float
    is_done: bool
    created_at: datetime

    @classmethod
    def create(cls, *, name: StatusName, is_done: bool, position: float, now: datetime) -> "Status":
        return cls(id=uuid4(), name=name, position=position, is_done=is_done, created_at=now)

    def rename(self, name: StatusName) -> None:
        self.name = name
