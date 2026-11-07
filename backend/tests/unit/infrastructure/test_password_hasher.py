from app.infrastructure.security.password_hasher import BcryptPasswordHasher


def test_hash_and_verify() -> None:
    hasher = BcryptPasswordHasher(rounds=4)

    hashed = hasher.hash("correct-horse")

    assert hashed != "correct-horse"
    assert hashed.startswith("$2b$04$")
    assert hasher.verify("correct-horse", hashed) is True
    assert hasher.verify("wrong-horse", hashed) is False


def test_verify_dummy_does_not_raise() -> None:
    BcryptPasswordHasher(rounds=4).verify_dummy("anything")


LONG_PASSWORD = "x" * 73  # bcrypt rejects anything over 72 bytes


def test_verify_rejects_password_over_72_bytes_instead_of_raising() -> None:
    hasher = BcryptPasswordHasher(rounds=4)
    hashed = hasher.hash("correct-horse")

    assert hasher.verify(LONG_PASSWORD, hashed) is False
    assert hasher.verify("é" * 37, hashed) is False  # 37 characters, 74 bytes


def test_verify_dummy_with_password_over_72_bytes_does_not_raise() -> None:
    BcryptPasswordHasher(rounds=4).verify_dummy(LONG_PASSWORD)


def test_verify_against_malformed_hash_is_false() -> None:
    assert BcryptPasswordHasher(rounds=4).verify("correct-horse", "$2b$04$truncated") is False
