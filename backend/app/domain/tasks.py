from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

from app.domain.errors import DueDateInPast, ValidationError
from app.domain.statuses import Status

TASK_TITLE_MAX_LENGTH = 200
TASK_DESCRIPTION_MAX_LENGTH = 5000


@dataclass(frozen=True, slots=True)
class TaskTitle:
    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if not 1 <= len(trimmed) <= TASK_TITLE_MAX_LENGTH:
            raise ValidationError(
                f"Title must be 1-{TASK_TITLE_MAX_LENGTH} characters", field="title"
            )
        object.__setattr__(self, "value", trimmed)


@dataclass(frozen=True, slots=True)
class TaskDescription:
    value: str

    def __post_init__(self) -> None:
        trimmed = self.value.strip()
        if len(trimmed) > TASK_DESCRIPTION_MAX_LENGTH:
            raise ValidationError(
                f"Description must be at most {TASK_DESCRIPTION_MAX_LENGTH} characters",
                field="description",
            )
        object.__setattr__(self, "value", trimmed)

    @classmethod
    def from_raw(cls, raw: str | None) -> "TaskDescription | None":
        """A blank description is stored as no description."""
        if raw is None or not raw.strip():
            return None
        return cls(raw)


def _ensure_not_past(due_date: date | None, now: datetime) -> None:
    # Rule: a due date may be today or later (UTC). See docs/DECISIONS.md.
    if due_date is not None and due_date < now.date():
        raise DueDateInPast()


@dataclass(slots=True)
class Task:
    id: UUID
    title: TaskTitle
    description: TaskDescription | None
    status_id: UUID
    assignee_id: UUID | None
    created_by_id: UUID
    due_date: date | None
    position: float
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        title: TaskTitle,
        description: TaskDescription | None,
        status: Status,
        position: float,
        created_by_id: UUID,
        assignee_id: UUID | None,
        due_date: date | None,
        now: datetime,
    ) -> "Task":
        _ensure_not_past(due_date, now)
        return cls(
            id=uuid4(),
            title=title,
            description=description,
            status_id=status.id,
            assignee_id=assignee_id,
            created_by_id=created_by_id,
            due_date=due_date,
            position=position,
            completed_at=now if status.is_done else None,
            created_at=now,
            updated_at=now,
        )

    def rename(self, title: TaskTitle, *, now: datetime) -> None:
        self.title = title
        self.updated_at = now

    def describe(self, description: TaskDescription | None, *, now: datetime) -> None:
        self.description = description
        self.updated_at = now

    def reschedule(self, due_date: date | None, *, now: datetime) -> None:
        # Re-sending an unchanged (possibly now overdue) date is not a change.
        if due_date != self.due_date:
            _ensure_not_past(due_date, now)
        self.due_date = due_date
        self.updated_at = now

    def move_to(self, status: Status, *, position: float, now: datetime) -> None:
        if status.is_done:
            # Moving between two done columns keeps the original completion time.
            self.completed_at = self.completed_at or now
        else:
            self.completed_at = None
        self.status_id = status.id
        self.position = position
        self.updated_at = now

    def assign(self, assignee_id: UUID | None, *, now: datetime) -> bool:
        """Returns whether the assignee actually changed."""
        changed = assignee_id != self.assignee_id
        self.assignee_id = assignee_id
        self.updated_at = now
        return changed
