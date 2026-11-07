"""Single place where domain errors become HTTP responses."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.errors import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    UnavailableError,
    ValidationError,
)

_STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (ValidationError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (AuthenticationError, status.HTTP_401_UNAUTHORIZED),
    (UnavailableError, status.HTTP_503_SERVICE_UNAVAILABLE),
]


def _status_for(exc: DomainError) -> int:
    for error_type, status_code in _STATUS_BY_ERROR:
        if isinstance(exc, error_type):
            return status_code
    return status.HTTP_400_BAD_REQUEST


def _validation_body(request: Request, exc: ValidationError) -> dict[str, Any]:
    """Same shape as FastAPI's own 422s, so clients parse one format.

    Query-string filters are only read on GET; everything else validates the JSON body.
    """
    loc = ["query" if request.method == "GET" else "body"]
    if exc.field:
        loc.append(exc.field)
    return {"detail": [{"loc": loc, "msg": exc.message, "type": "value_error"}]}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):  # pragma: no cover - only registered for DomainError
        raise exc
    status_code = _status_for(exc)
    if isinstance(exc, ValidationError):
        return JSONResponse(_validation_body(request, exc), status_code=status_code)
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
    return JSONResponse({"detail": exc.message}, status_code=status_code, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
