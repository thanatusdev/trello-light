"""Shared helpers for API tests: register/login a user and build auth headers."""

from typing import Any

from httpx import AsyncClient, Response

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

PASSWORD = "correct-horse"
INVALID_TOKEN_BODY = {"detail": "Could not validate credentials"}
INVALID_LOGIN_BODY = {"detail": "Incorrect email or password"}


async def register(
    client: AsyncClient, email: str = "alice@example.com", password: str = PASSWORD
) -> Response:
    return await client.post(
        REGISTER_URL, json={"email": email, "full_name": "Alice Smith", "password": password}
    )


async def login(
    client: AsyncClient, email: str = "alice@example.com", password: str = PASSWORD
) -> Response:
    return await client.post(LOGIN_URL, data={"username": email, "password": password})


async def tokens_for(client: AsyncClient, email: str = "alice@example.com") -> dict[str, Any]:
    await register(client, email)
    response = await login(client, email)
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def validation_error(msg: str, *loc: str) -> dict[str, Any]:
    """Body of a 422 raised by the domain: the same list shape FastAPI uses for its own 422s."""
    return {"detail": [{"loc": list(loc), "msg": msg, "type": "value_error"}]}


def assert_unauthorized(response: Response, body: dict[str, str] = INVALID_TOKEN_BODY) -> None:
    assert response.status_code == 401
    assert response.json() == body
    assert response.headers["www-authenticate"] == "Bearer"


BOARD_URL = "/api/v1/board"
STATUSES_URL = "/api/v1/statuses"
TASKS_URL = "/api/v1/tasks"


async def seeded_status_ids(client: AsyncClient, headers: dict[str, str]) -> dict[str, str]:
    """Column name -> id for the columns currently on the board (seeded by the migration)."""
    response = await client.get(BOARD_URL, headers=headers)
    assert response.status_code == 200
    return {column["name"]: column["id"] for column in response.json()["columns"]}


async def create_task(
    client: AsyncClient, headers: dict[str, str], status_id: str, **fields: Any
) -> dict[str, Any]:
    response = await client.post(
        TASKS_URL, json={"title": "Task", "status_id": status_id, **fields}, headers=headers
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body
