from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Body of 401, 404, 409, 429 and 503 errors. (422s use FastAPI's validation-error list.)"""

    detail: str
