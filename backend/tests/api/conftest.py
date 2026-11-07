import pytest
from httpx import AsyncClient

from tests.api.helpers import bearer, seeded_status_ids, tokens_for


@pytest.fixture
async def auth(client: AsyncClient) -> dict[str, str]:
    """Authorization headers for a freshly registered alice@example.com."""
    tokens = await tokens_for(client, "alice@example.com")
    return bearer(tokens["access_token"])


@pytest.fixture
async def columns(client: AsyncClient, auth: dict[str, str]) -> dict[str, str]:
    return await seeded_status_ids(client, auth)
