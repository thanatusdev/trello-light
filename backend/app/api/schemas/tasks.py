from datetime import date, datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

_DUE_DATE_DOC = "ISO date. Must be today (UTC) or later when set or changed."


class TaskCreateRequest(BaseModel):
    """Title/description limits and the due-date rule are enforced by the domain."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "title": "Write the README",
                    "description": "Setup, architecture, decisions",
                    "status_id": "8d4c3c1e-7a39-4f8a-9d55-0b1c9d1f4a10",
                    "assignee_id": None,
                    "due_date": "2030-01-31",
                }
            ]
        },
    )

    title: str = Field(max_length=1000)
    description: str | None = Field(default=None, max_length=20_000)
    status_id: UUID = Field(description="Column to create the task in; it goes to the bottom")
    assignee_id: UUID | None = Field(default=None, description="Must be an active user")
    due_date: date | None = Field(default=None, description=_DUE_DATE_DOC)


class TaskUpdateRequest(BaseModel):
    """Partial update: omitted fields are unchanged, ``null`` clears description/due_date.

    Use the move and assignee endpoints to change the column or the assignee.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=1000)
    description: str | None = Field(default=None, max_length=20_000)
    due_date: date | None = Field(default=None, description=_DUE_DATE_DOC)

    @model_validator(mode="after")
    def _title_not_null(self) -> Self:
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title cannot be null")
        return self


class TaskMoveRequest(BaseModel):
    """Target column plus the neighbours the client sees there.

    Neither neighbour: bottom of the column. ``before_id`` only: directly above it.
    ``after_id`` only: directly below it. Stale or non-adjacent neighbours return 409.
    """

    model_config = ConfigDict(extra="forbid")

    status_id: UUID
    after_id: UUID | None = None
    before_id: UUID | None = None


class TaskAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_id: UUID | None = Field(description="Active user to assign, or null to unassign")


class AssigneeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    status_id: UUID
    assignee: AssigneeResponse | None
    created_by_id: UUID
    due_date: date | None
    position: float
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
