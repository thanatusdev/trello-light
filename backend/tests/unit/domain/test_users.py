from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.domain.errors import ValidationError
from app.domain.users import Email, FullName, PlainPassword, User


class TestEmail:
    def test_normalises_case_and_whitespace(self) -> None:
        assert Email("  Alice@Example.COM ").value == "alice@example.com"

    @pytest.mark.parametrize(
        "raw", ["", "plainaddress", "@example.com", "alice@", "alice@example", "a b@example.com"]
    )
    def test_rejects_invalid_addresses(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            Email(raw)

    def test_rejects_overlong_address(self) -> None:
        with pytest.raises(ValidationError):
            Email("a" * 250 + "@example.com")

    def test_equal_after_normalisation(self) -> None:
        assert Email("BOB@example.com") == Email("bob@example.com")


class TestFullName:
    def test_trims_whitespace(self) -> None:
        assert FullName("  Alice Smith ").value == "Alice Smith"

    @pytest.mark.parametrize("raw", ["", "   ", "x" * 101])
    def test_rejects_empty_or_too_long(self, raw: str) -> None:
        with pytest.raises(ValidationError):
            FullName(raw)

    def test_accepts_100_characters(self) -> None:
        assert FullName("x" * 100).value == "x" * 100


class TestPlainPassword:
    def test_accepts_eight_characters(self) -> None:
        assert PlainPassword("12345678").value == "12345678"

    def test_rejects_shorter_than_eight(self) -> None:
        with pytest.raises(ValidationError):
            PlainPassword("1234567")

    def test_rejects_more_than_72_bytes(self) -> None:
        # 37 two-byte characters = 74 bytes, although only 37 characters.
        with pytest.raises(ValidationError):
            PlainPassword("é" * 37)

    def test_accepts_exactly_72_bytes(self) -> None:
        assert PlainPassword("a" * 72).value == "a" * 72

    def test_repr_does_not_leak_value(self) -> None:
        assert "s3cret-pass" not in repr(PlainPassword("s3cret-pass"))


class TestUser:
    def test_register_creates_active_user(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)

        user = User.register(
            email=Email("alice@example.com"),
            full_name=FullName("Alice"),
            hashed_password="hashed",
            now=now,
        )

        assert isinstance(user.id, UUID)
        assert user.email == Email("alice@example.com")
        assert user.full_name == FullName("Alice")
        assert user.hashed_password == "hashed"
        assert user.is_active is True
        assert user.created_at == now

    def test_register_generates_distinct_ids(self) -> None:
        kwargs = {
            "email": Email("a@example.com"),
            "full_name": FullName("A"),
            "hashed_password": "h",
            "now": datetime.now(UTC),
        }
        assert User.register(**kwargs).id != User.register(**kwargs).id  # type: ignore[arg-type]
