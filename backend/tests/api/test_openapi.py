from typing import Any

from httpx import AsyncClient

OPENAPI_URL = "/api/v1/openapi.json"
HEALTH_PATH = "/api/v1/health"


async def _operations(client: AsyncClient) -> list[tuple[str, str, dict[str, Any]]]:
    spec = (await client.get(OPENAPI_URL)).json()
    return [
        (path, method, operation)
        for path, item in spec["paths"].items()
        for method, operation in item.items()
    ]


async def test_every_rate_limited_operation_documents_429(client: AsyncClient) -> None:
    operations = [op for op in await _operations(client) if op[0] != HEALTH_PATH]
    assert operations

    for path, method, operation in operations:
        response = operation["responses"].get("429")
        assert response is not None, f"{method.upper()} {path} does not document 429"
        content = response["content"]["application/json"]["schema"]
        assert content == {"$ref": "#/components/schemas/ErrorResponse"}, (method, path)
        assert "Retry-After" in response["headers"], (method, path)


async def test_health_is_not_rate_limited_so_does_not_document_429(client: AsyncClient) -> None:
    health = [op for op in await _operations(client) if op[0] == HEALTH_PATH]

    assert health
    assert all("429" not in operation["responses"] for _, _, operation in health)
