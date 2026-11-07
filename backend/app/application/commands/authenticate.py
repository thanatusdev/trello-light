"""Exchange credentials for tokens.

Documented exception to "commands return only an id": authentication goes through the
domain (user repository + password hasher) but its result is the issued token pair.
"""

from dataclasses import dataclass, field

from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.token_service import TokenPair, TokenService
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.errors import InvalidCredentials, ValidationError
from app.domain.users import Email


@dataclass(frozen=True, slots=True)
class Authenticate:
    email: str
    password: str = field(repr=False)


class AuthenticateHandler:
    def __init__(self, uow: UnitOfWork, hasher: PasswordHasher, tokens: TokenService) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens

    async def handle(self, command: Authenticate) -> TokenPair:
        try:
            user = await self._uow.users.get_by_email(Email(command.email))
        except ValidationError:
            user = None

        # Every failure path does the same hashing work and raises the same error,
        # so responses don't reveal which emails are registered.
        if user is None:
            self._hasher.verify_dummy(command.password)
            raise InvalidCredentials()
        if not self._hasher.verify(command.password, user.hashed_password):
            raise InvalidCredentials()
        if not user.is_active:
            raise InvalidCredentials()

        return self._tokens.issue_pair(user.id)
