from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.bcrypt import BcryptHasher

# bcrypt only reads the first 72 bytes and the bcrypt package raises ValueError beyond that.
BCRYPT_MAX_BYTES = 72
# Hashed in place of an over-long password so a rejected attempt still costs one bcrypt run.
_TIMING_PLACEHOLDER = "placeholder-for-an-over-long-password"


def _too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > BCRYPT_MAX_BYTES


class BcryptPasswordHasher:
    def __init__(self, rounds: int = 12) -> None:
        self._hash = PasswordHash((BcryptHasher(rounds=rounds),))
        # Real hash with the same cost, so a dummy verify takes as long as a real one.
        self._dummy_hash = self._hash.hash("dummy-password-for-timing")

    def hash(self, password: str) -> str:
        return self._hash.hash(password)

    def verify(self, password: str, hashed_password: str) -> bool:
        """Never raises: an over-long password or a malformed hash is simply not a match.

        An over-long password can never match (registration caps passwords at 72 bytes),
        but it still pays for one bcrypt run so the response time gives nothing away.
        """
        if _too_long(password):
            self.verify_dummy(password)
            return False
        try:
            return self._hash.verify(password, hashed_password)
        except (ValueError, UnknownHashError):
            return False

    def verify_dummy(self, password: str) -> None:
        candidate = _TIMING_PLACEHOLDER if _too_long(password) else password
        self._hash.verify(candidate, self._dummy_hash)
