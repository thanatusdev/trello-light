from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.api.schemas.tasks import TaskResponse


class BoardColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    position: float
    is_done: bool
    tasks: list[TaskResponse]


class BoardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    columns: list[BoardColumnResponse]
