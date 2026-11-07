from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from itertools import count
from uuid import UUID, uuid4

from app.application.ports.token_service import RefreshClaims, TokenPair, TokenType
from app.domain.errors import (
    EmailAlreadyRegistered,
    InvalidToken,
    StatusNameTaken,
    TokenStoreUnavailable,
)
from app.domain.statuses import Status, StatusName
from app.domain.tasks import Task, TaskTitle
from app.domain.users import Email, FullName, User

FIXED_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def add(self, user: User) -> None:
        if any(u.email == user.email for u in self.users.values()):
            raise EmailAlreadyRegistered()
        self.users[user.id] = user

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: Email) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)


class FakeStatusRepository:
    """Stores copies so handlers must call ``save`` for changes to stick, like the real one."""

    def __init__(self, tasks: "FakeTaskRepository", lock_log: "LockLog") -> None:
        self.statuses: dict[UUID, Status] = {}
        self.locked: list[UUID] = []
        self._tasks = tasks  # so has_tasks can see the task store
        self._lock_log = lock_log

    def _ensure_unique_name(self, status: Status) -> None:
        if any(s.name.matches(status.name) and s.id != status.id for s in self.statuses.values()):
            raise StatusNameTaken()

    async def add(self, status: Status) -> None:
        self._ensure_unique_name(status)
        self.statuses[status.id] = replace(status)

    async def get(self, status_id: UUID) -> Status | None:
        status = self.statuses.get(status_id)
        return replace(status) if status else None

    async def lock_board(self) -> None:
        self._lock_log.append(("board", None))

    async def get_for_update(self, status_id: UUID) -> Status | None:
        self.locked.append(status_id)
        self._lock_log.append(("status", status_id))
        return await self.get(status_id)

    async def get_by_name(self, name: StatusName) -> Status | None:
        status = next((s for s in self.statuses.values() if s.name.matches(name)), None)
        return replace(status) if status else None

    async def list_for_update(self) -> list[Status]:
        self.locked.extend(self.statuses)
        self._lock_log.extend(("status", sid) for sid in sorted(self.statuses))
        return [replace(s) for s in sorted(self.statuses.values(), key=lambda s: s.position)]

    async def save(self, status: Status) -> None:
        self._ensure_unique_name(status)
        self.statuses[status.id] = replace(status)

    async def set_positions(self, positions: Mapping[UUID, float]) -> None:
        for status_id, position in positions.items():
            self.statuses[status_id].position = position

    async def has_tasks(self, status_id: UUID) -> bool:
        return any(t.status_id == status_id for t in self._tasks.tasks.values())

    async def delete(self, status_id: UUID) -> None:
        del self.statuses[status_id]


class FakeTaskRepository:
    def __init__(self, lock_log: "LockLog") -> None:
        self.tasks: dict[UUID, Task] = {}
        self.rebalanced_columns: list[UUID] = []
        # Test hook: simulate another transaction changing the task just before it is locked.
        self.before_lock: Callable[[Task], None] | None = None
        self._lock_log = lock_log

    async def add(self, task: Task) -> None:
        self.tasks[task.id] = replace(task)

    async def get(self, task_id: UUID) -> Task | None:
        task = self.tasks.get(task_id)
        return replace(task) if task else None

    async def get_for_update(self, task_id: UUID) -> Task | None:
        self._lock_log.append(("task", task_id))
        if self.before_lock and task_id in self.tasks:
            self.before_lock(self.tasks[task_id])
        return await self.get(task_id)

    async def save(self, task: Task) -> None:
        self.tasks[task.id] = replace(task)

    async def delete(self, task_id: UUID) -> None:
        del self.tasks[task_id]

    async def list_positions(self, status_id: UUID) -> list[tuple[UUID, float]]:
        column = [t for t in self.tasks.values() if t.status_id == status_id]
        return [(t.id, t.position) for t in sorted(column, key=lambda t: (t.position, t.id))]

    async def set_positions(self, status_id: UUID, positions: Mapping[UUID, float]) -> None:
        self.rebalanced_columns.append(status_id)
        for task_id, position in positions.items():
            if self.tasks[task_id].status_id == status_id:  # like the real WHERE status_id
                self.tasks[task_id].position = position

    def positions(self, status_id: UUID) -> list[float]:
        """Test helper: positions in a column, top to bottom."""
        return sorted(t.position for t in self.tasks.values() if t.status_id == status_id)


# ("board" | "status" | "task", id) in the order locks were taken.
type LockLog = list[tuple[str, UUID | None]]


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.lock_log: LockLog = []
        self.users = FakeUserRepository()
        self.tasks = FakeTaskRepository(self.lock_log)
        self.statuses = FakeStatusRepository(self.tasks, self.lock_log)
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FailingCommitUnitOfWork(FakeUnitOfWork):
    async def commit(self) -> None:
        raise RuntimeError("commit failed")


@dataclass(frozen=True, slots=True)
class Assignment:
    task_id: UUID
    assignee_id: UUID
    assigned_by_id: UUID
    commits_before: int


class FakeNotifier:
    """Records assignments, plus how many commits had happened when each was sent."""

    def __init__(self, uow: FakeUnitOfWork | None = None) -> None:
        self._uow = uow
        self.assignments: list[Assignment] = []

    async def task_assigned(
        self, *, task_id: UUID, assignee_id: UUID, assigned_by_id: UUID
    ) -> None:
        commits = self._uow.commits if self._uow else 0
        self.assignments.append(Assignment(task_id, assignee_id, assigned_by_id, commits))


class FakePasswordHasher:
    def __init__(self) -> None:
        self.dummy_calls = 0

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, hashed_password: str) -> bool:
        return hashed_password == f"hashed:{password}"

    def verify_dummy(self, password: str) -> None:
        self.dummy_calls += 1


class FakeTokenService:
    """Access tokens are readable strings like ``access:<uuid>``; refresh tokens are opaque
    ``refresh:<n>`` strings whose claims are kept in ``claims``."""

    REFRESH_TTL = timedelta(days=7)

    def __init__(self) -> None:
        self.claims: dict[str, RefreshClaims] = {}
        self._ids = count(1)

    def issue_pair(self, user_id: UUID) -> TokenPair:
        return self._pair(user_id, f"session-{next(self._ids)}", FIXED_NOW + self.REFRESH_TTL)

    def rotate(self, claims: RefreshClaims) -> TokenPair:
        return self._pair(claims.user_id, claims.session_id, claims.expires_at)

    def decode(self, token: str, expected_type: TokenType) -> UUID:
        if expected_type is TokenType.REFRESH:
            return self.decode_refresh(token).user_id
        kind, _, raw_id = token.partition(":")
        if kind != expected_type.value:
            raise InvalidToken()
        try:
            return UUID(raw_id)
        except ValueError as exc:
            raise InvalidToken() from exc

    def decode_refresh(self, token: str) -> RefreshClaims:
        try:
            return self.claims[token]
        except KeyError as exc:
            raise InvalidToken() from exc

    def _pair(self, user_id: UUID, session_id: str, expires_at: datetime) -> TokenPair:
        n = next(self._ids)
        refresh = f"refresh:{n}"
        self.claims[refresh] = RefreshClaims(
            user_id=user_id, token_id=f"jti-{n}", session_id=session_id, expires_at=expires_at
        )
        return TokenPair(access_token=f"access:{user_id}", refresh_token=refresh)


class FakeRefreshTokenStore:
    def __init__(self) -> None:
        self.used: dict[str, tuple[datetime, datetime]] = {}
        self.revoked: dict[str, datetime] = {}
        self.available = True

    async def mark_used(
        self, token_id: str, *, at: datetime, expires_at: datetime
    ) -> datetime | None:
        self._check()
        if token_id in self.used:
            return self.used[token_id][0]
        self.used[token_id] = (at, expires_at)
        return None

    async def revoke_session(self, session_id: str, *, expires_at: datetime) -> None:
        self._check()
        self.revoked[session_id] = expires_at

    async def is_revoked(self, session_id: str) -> bool:
        self._check()
        return session_id in self.revoked

    def _check(self) -> None:
        if not self.available:
            raise TokenStoreUnavailable()


class MutableClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def fixed_clock() -> datetime:
    return FIXED_NOW


def make_user(
    email: str = "alice@example.com", password: str = "correct-horse", *, is_active: bool = True
) -> User:
    user = User.register(
        email=Email(email),
        full_name=FullName("Alice"),
        hashed_password=f"hashed:{password}",
        now=FIXED_NOW,
    )
    user.is_active = is_active
    return user


def make_status(name: str = "To Do", *, position: float = 1024.0, is_done: bool = False) -> Status:
    return Status.create(name=StatusName(name), is_done=is_done, position=position, now=FIXED_NOW)


def make_task(
    status: Status,
    *,
    title: str = "Task",
    position: float = 1024.0,
    created_by_id: UUID | None = None,
    due_date: date | None = None,
) -> Task:
    return Task.create(
        title=TaskTitle(title),
        description=None,
        status=status,
        position=position,
        created_by_id=created_by_id or uuid4(),
        assignee_id=None,
        due_date=due_date,
        now=FIXED_NOW,
    )
