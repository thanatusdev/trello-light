class DomainError(Exception):
    """Base class for errors raised by the domain and application layers."""

    message: str = "Domain error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message


class ValidationError(DomainError):
    message = "Invalid value"
    # The input field at fault, when there is one; the API reports it in the error location.
    field: str | None = None

    def __init__(self, message: str | None = None, *, field: str | None = None) -> None:
        super().__init__(message)
        if field is not None:
            self.field = field


class NotFoundError(DomainError):
    message = "Resource not found"


class ConflictError(DomainError):
    message = "Conflict"


class UnavailableError(DomainError):
    """A backing service the use case depends on is down; the request may be retried."""

    message = "Service temporarily unavailable"


class AuthenticationError(DomainError):
    message = "Authentication failed"


class UserNotFound(NotFoundError):
    message = "User not found"


class EmailAlreadyRegistered(ConflictError):
    message = "Email is already registered"


class InvalidCredentials(AuthenticationError):
    message = "Incorrect email or password"


class InvalidToken(AuthenticationError):
    message = "Could not validate credentials"


class TokenStoreUnavailable(UnavailableError):
    message = "Session store is unavailable; try again shortly"


class StatusNotFound(NotFoundError):
    message = "Status not found"


class TaskNotFound(NotFoundError):
    message = "Task not found"


class StatusNameTaken(ConflictError):
    message = "A status with this name already exists"


class StatusHasTasks(ConflictError):
    message = "Status still has tasks; move or delete them first"


class StaleOrdering(ConflictError):
    message = "Neighbours do not match the current order; refresh and retry"


class UnknownStatus(ValidationError):
    message = "status_id does not reference an existing status"
    field = "status_id"


class InvalidAssignee(ValidationError):
    message = "assignee_id must reference an active user"
    field = "assignee_id"


class DueDateInPast(ValidationError):
    message = "due_date cannot be in the past"
    field = "due_date"


class InvalidDueDateRange(ValidationError):
    message = "due_after must be on or before due_before"
    field = "due_after"
