from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_refresh_token_store
from app.infrastructure.config import Settings
from app.infrastructure.models.user import UserModel
from app.infrastructure.security.jwt_token_service import JwtTokenService
from tests.api.helpers import (
    INVALID_LOGIN_BODY,
    PASSWORD,
    REGISTER_URL,
    assert_unauthorized,
    bearer,
    login,
    register,
    tokens_for,
    validation_error,
)
from tests.unit.application.fakes import FakeRefreshTokenStore

REFRESH_URL = "/api/v1/auth/refresh"
ME_URL = "/api/v1/auth/me"
LOGOUT_URL = "/api/v1/auth/logout"


# --- register -----------------------------------------------------------------


async def test_register_returns_created_user(client: AsyncClient) -> None:
    response = await register(client, " Alice@Example.com ")

    assert response.status_code == 201
    body = response.json()
    UUID(body["id"])
    datetime.fromisoformat(body["created_at"])
    assert body["email"] == "alice@example.com"
    assert body["full_name"] == "Alice Smith"
    assert body["is_active"] is True
    assert "password" not in str(body)


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    await register(client, "alice@example.com")

    response = await register(client, "ALICE@example.com")

    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already registered"}


@pytest.mark.parametrize(
    ("payload", "field", "detail"),
    [
        (
            {"email": "nope", "full_name": "A", "password": PASSWORD},
            "email",
            "Invalid email address",
        ),
        (
            {"email": "a@example.com", "full_name": "A", "password": "short"},
            "password",
            "Password must be at least 8 characters",
        ),
        (
            {"email": "a@example.com", "full_name": "A", "password": "x" * 73},
            "password",
            "Password must be at most 72 bytes",
        ),
        (
            # 37 characters but 74 bytes: the limit is bcrypt's, in bytes.
            {"email": "a@example.com", "full_name": "A", "password": "é" * 37},
            "password",
            "Password must be at most 72 bytes",
        ),
        (
            {"email": "a@example.com", "full_name": "  ", "password": PASSWORD},
            "full_name",
            "Full name must be 1-100 characters",
        ),
    ],
)
async def test_register_rejects_invalid_input(
    client: AsyncClient, payload: dict[str, str], field: str, detail: str
) -> None:
    response = await client.post(REGISTER_URL, json=payload)

    assert response.status_code == 422
    assert response.json() == validation_error(detail, "body", field)


async def test_register_missing_fields_is_422(client: AsyncClient) -> None:
    response = await client.post(REGISTER_URL, json={"email": "a@example.com"})

    assert response.status_code == 422


# --- login --------------------------------------------------------------------


async def test_login_returns_token_pair(client: AsyncClient) -> None:
    await register(client)

    response = await login(client, "ALICE@example.com")

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


async def test_wrong_password_and_unknown_email_are_indistinguishable(
    client: AsyncClient,
) -> None:
    await register(client)

    wrong_password = await login(client, password="wrong-horse")
    unknown_email = await login(client, email="nobody@example.com")

    assert_unauthorized(wrong_password, INVALID_LOGIN_BODY)
    assert_unauthorized(unknown_email, INVALID_LOGIN_BODY)


@pytest.mark.parametrize("password", ["x" * 73, "é" * 37], ids=["ascii", "multibyte"])
async def test_login_with_password_over_72_bytes_is_unauthorized(
    client: AsyncClient, password: str
) -> None:
    await register(client)

    assert_unauthorized(await login(client, password=password), INVALID_LOGIN_BODY)
    assert_unauthorized(
        await login(client, email="nobody@example.com", password=password), INVALID_LOGIN_BODY
    )


async def test_login_inactive_user_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await register(client)
    await deactivate(db_session, "alice@example.com")

    assert_unauthorized(await login(client), INVALID_LOGIN_BODY)


# --- me / get_current_user ----------------------------------------------------


async def test_me_returns_current_user(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    response = await client.get(ME_URL, headers=bearer(tokens["access_token"]))

    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


async def test_me_without_token_is_unauthorized(client: AsyncClient) -> None:
    assert_unauthorized(await client.get(ME_URL))


async def test_me_with_non_bearer_scheme_is_unauthorized(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    response = await client.get(
        ME_URL, headers={"Authorization": f"Basic {tokens['access_token']}"}
    )

    assert_unauthorized(response)


async def test_me_with_refresh_token_is_unauthorized(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    assert_unauthorized(await client.get(ME_URL, headers=bearer(tokens["refresh_token"])))


async def test_me_with_tampered_token_is_unauthorized(client: AsyncClient) -> None:
    tokens = await tokens_for(client)
    header, payload, signature = tokens["access_token"].split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}AAAA"

    assert_unauthorized(await client.get(ME_URL, headers=bearer(tampered)))


async def test_me_with_expired_token_is_unauthorized(
    client: AsyncClient, test_settings: Settings
) -> None:
    await register(client)
    user_id = UUID(await client_me_id(client))
    issued_long_ago = datetime.now(UTC) - timedelta(minutes=16)
    stale = JwtTokenService(
        secret=test_settings.jwt_secret.get_secret_value(),
        access_ttl=test_settings.access_token_ttl,
        refresh_ttl=timedelta(days=test_settings.refresh_token_expire_days),
        clock=lambda: issued_long_ago,
    ).issue_pair(user_id)

    assert_unauthorized(await client.get(ME_URL, headers=bearer(stale.access_token)))


async def test_me_for_deactivated_user_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await tokens_for(client)
    await deactivate(db_session, "alice@example.com")

    assert_unauthorized(await client.get(ME_URL, headers=bearer(tokens["access_token"])))


# --- refresh ------------------------------------------------------------------


async def test_refresh_issues_working_token_pair(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    response = await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 200
    new_tokens = response.json()
    assert new_tokens["token_type"] == "bearer"
    me = await client.get(ME_URL, headers=bearer(new_tokens["access_token"]))
    assert me.status_code == 200


async def test_refresh_with_access_token_is_unauthorized(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    response = await client.post(REFRESH_URL, json={"refresh_token": tokens["access_token"]})

    assert_unauthorized(response)


async def test_refresh_with_garbage_is_unauthorized(client: AsyncClient) -> None:
    assert_unauthorized(await client.post(REFRESH_URL, json={"refresh_token": "garbage"}))


async def test_refresh_for_deactivated_user_is_unauthorized(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tokens = await tokens_for(client)
    await deactivate(db_session, "alice@example.com")

    response = await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})

    assert_unauthorized(response)


async def test_refresh_token_is_single_use(client: AsyncClient) -> None:
    tokens = await tokens_for(client)
    body = {"refresh_token": tokens["refresh_token"]}

    assert (await client.post(REFRESH_URL, json=body)).status_code == 200
    assert_unauthorized(await client.post(REFRESH_URL, json=body))


async def test_refresh_when_session_store_is_down_is_503(client: AsyncClient, app: FastAPI) -> None:
    tokens = await tokens_for(client)
    store = FakeRefreshTokenStore()
    store.available = False
    app.dependency_overrides[get_refresh_token_store] = lambda: store

    response = await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 503
    assert response.json() == {"detail": "Session store is unavailable; try again shortly"}


# --- logout -------------------------------------------------------------------


async def test_logout_ends_the_session(client: AsyncClient) -> None:
    tokens = await tokens_for(client)
    rotated = (
        await client.post(REFRESH_URL, json={"refresh_token": tokens["refresh_token"]})
    ).json()

    response = await client.post(LOGOUT_URL, json={"refresh_token": rotated["refresh_token"]})

    assert response.status_code == 204
    assert response.content == b""
    assert_unauthorized(
        await client.post(REFRESH_URL, json={"refresh_token": rotated["refresh_token"]})
    )


async def test_logout_leaves_other_sessions_alone(client: AsyncClient) -> None:
    first = await tokens_for(client)
    second = (await login(client)).json()

    await client.post(LOGOUT_URL, json={"refresh_token": first["refresh_token"]})

    response = await client.post(REFRESH_URL, json={"refresh_token": second["refresh_token"]})
    assert response.status_code == 200


async def test_logout_with_garbage_token_is_no_content(client: AsyncClient) -> None:
    response = await client.post(LOGOUT_URL, json={"refresh_token": "garbage"})

    assert response.status_code == 204


# --- helpers ------------------------------------------------------------------


async def deactivate(session: AsyncSession, email: str) -> None:
    await session.execute(update(UserModel).where(UserModel.email == email).values(is_active=False))


async def client_me_id(client: AsyncClient) -> str:
    tokens = (await login(client)).json()
    response = await client.get(ME_URL, headers=bearer(tokens["access_token"]))
    user_id: str = response.json()["id"]
    return user_id
