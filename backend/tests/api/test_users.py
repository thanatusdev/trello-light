from httpx import AsyncClient

from tests.api.helpers import bearer, register, tokens_for

USERS_URL = "/api/v1/users"


async def test_list_users_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(USERS_URL)

    assert response.status_code == 401


async def test_list_users_is_paginated(client: AsyncClient) -> None:
    tokens = await tokens_for(client, "alice@example.com")
    await register(client, "bob@example.com")
    await register(client, "carol@example.com")

    response = await client.get(
        USERS_URL, params={"page": 2, "size": 2}, headers=bearer(tokens["access_token"])
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["page"] == 2
    assert body["size"] == 2
    assert body["pages"] == 2
    assert len(body["items"]) == 1
    assert set(body["items"][0]) == {"id", "email", "full_name"}


async def test_list_users_defaults(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    body = (await client.get(USERS_URL, headers=bearer(tokens["access_token"]))).json()

    assert (body["page"], body["size"], body["total"]) == (1, 20, 1)


async def test_list_users_rejects_size_over_100(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    response = await client.get(
        USERS_URL, params={"size": 101}, headers=bearer(tokens["access_token"])
    )

    assert response.status_code == 422


async def test_list_users_rejects_page_zero(client: AsyncClient) -> None:
    tokens = await tokens_for(client)

    response = await client.get(
        USERS_URL, params={"page": 0}, headers=bearer(tokens["access_token"])
    )

    assert response.status_code == 422
