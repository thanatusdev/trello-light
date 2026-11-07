from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterRequest(BaseModel):
    """Email, name and password rules are enforced by the domain value objects."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "alice@example.com",
                    "full_name": "Alice Smith",
                    "password": "s3cret-pass",
                }
            ]
        }
    )

    email: str = Field(max_length=320)
    full_name: str = Field(max_length=200)
    password: str = Field(max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth2 token type, not a secret
