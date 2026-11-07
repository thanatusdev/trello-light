from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StatusCreateRequest(BaseModel):
    """Name rules (trimmed, 1-50 chars, unique ignoring case) are enforced by the domain."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"name": "Review", "is_done": False}]}
    )

    name: str = Field(max_length=200)
    is_done: bool = Field(
        default=False,
        description="Tasks moved into a done column are marked completed. Fixed at creation.",
    )


class StatusRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=200)


class StatusMoveRequest(BaseModel):
    """Neighbours as the client currently sees them. Neither given moves the column last."""

    model_config = ConfigDict(extra="forbid")

    after_id: UUID | None = Field(default=None, description="Column that should end up before")
    before_id: UUID | None = Field(default=None, description="Column that should end up after")


class StatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    position: float
    is_done: bool
    created_at: datetime
