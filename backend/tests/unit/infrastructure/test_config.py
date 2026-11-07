from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.infrastructure.config import Settings

LONG_SECRET = "x" * 32


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "postgres_user": "u",
        "postgres_password": "p",
        "postgres_db": "d",
        "jwt_secret": LONG_SECRET,
        **overrides,
    }
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_access_token_ttl_defaults_to_minutes() -> None:
    assert make_settings(access_token_expire_minutes=7).access_token_ttl == timedelta(minutes=7)


def test_access_token_ttl_seconds_override_minutes() -> None:
    settings = make_settings(access_token_expire_minutes=7, access_token_expire_seconds=5)

    assert settings.access_token_ttl == timedelta(seconds=5)


def test_jwt_secret_shorter_than_32_characters_is_rejected() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        make_settings(jwt_secret="x" * 31)


def test_jwt_secret_of_32_characters_is_accepted() -> None:
    assert make_settings(jwt_secret=LONG_SECRET).jwt_secret.get_secret_value() == LONG_SECRET
