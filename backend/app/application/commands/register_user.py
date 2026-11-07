from dataclasses import dataclass, field
from uuid import UUID

from app.application.ports.clock import Clock
from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import EmailAlreadyRegistered
from app.domain.users import Email, FullName, PlainPassword, User


@dataclass(frozen=True, slots=True)
class RegisterUser:
    email: str
    full_name: str
    password: str = field(repr=False)


class RegisterUserHandler:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def handle(self, command: RegisterUser) -> UUID:
        email = Email(command.email)
        full_name = FullName(command.full_name)
        password = PlainPassword(command.password)

        if await self._uow.users.get_by_email(email) is not None:
            raise EmailAlreadyRegistered()

        user = User.register(
            email=email,
            full_name=full_name,
            hashed_password=self._hasher.hash(password.value),
            now=self._clock(),
        )
        await self._uow.users.add(user)
        await self._uow.commit()
        return user.id
