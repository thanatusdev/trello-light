from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# Repo-root .env (used when running tools from the host). Inside containers the
# variables come from the environment and this file simply does not exist.
_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV_FILE, extra="ignore")

    app_env: Literal["local", "test", "production"] = "local"

    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    test_postgres_db: str = "kanban_test"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # HS256 needs a key of at least 256 bits (RFC 7518 3.2): 32+ random characters.
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_expire_minutes: int = 15
    # Overrides the minutes setting when set (e2e uses a few seconds to exercise refresh).
    access_token_expire_seconds: int | None = Field(default=None, gt=0)
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12

    health_check_timeout_seconds: float = 2.0

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # slowapi limit strings. Storage defaults to the app's Redis.
    rate_limit_enabled: bool = True
    rate_limit_default: str = "100/minute"
    rate_limit_login: str = "5/minute"
    rate_limit_register: str = "3/minute"
    rate_limit_storage_uri: str | None = None

    # Hour (UTC) of the daily "due soon" digest.
    due_soon_hour_utc: int = Field(default=8, ge=0, le=23)

    # Demo data, created at startup by `python -m app.infrastructure.seed` when enabled.
    seed_demo_data: bool = False
    demo_user_password: SecretStr | None = None

    def _postgres_url(self, database: str) -> str:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=database,
        ).render_as_string(hide_password=False)

    @property
    def database_url(self) -> str:
        return self._postgres_url(self.postgres_db)

    @property
    def test_database_url(self) -> str:
        return self._postgres_url(self.test_postgres_db)

    @property
    def access_token_ttl(self) -> timedelta:
        if self.access_token_expire_seconds is not None:
            return timedelta(seconds=self.access_token_expire_seconds)
        return timedelta(minutes=self.access_token_expire_minutes)

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def rate_limit_storage(self) -> str:
        return self.rate_limit_storage_uri or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
