from typing import Any

import pytest
from httpx import AsyncClient

from tests.api.helpers import BOARD_URL, STATUSES_URL, create_task, validation_error


async def _names(client: AsyncClient, auth: dict[str, str]) -> list[str]:
    response = await client.get(BOARD_URL, headers=auth)
    return [c["name"] for c in response.json()["columns"]]


async def _create(client: AsyncClient, auth: dict[str, str], **body: Any) -> dict[str, Any]:
    response = await client.post(STATUSES_URL, json=body, headers=auth)
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", ""),
        ("patch", "/00000000-0000-0000-0000-000000000000"),
        ("post", "/00000000-0000-0000-0000-000000000000/move"),
        ("delete", "/00000000-0000-0000-0000-000000000000"),
    ],
)
async def test_status_endpoints_require_auth(client: AsyncClient, method: str, path: str) -> None:
    response = await client.request(method, STATUSES_URL + path, json={})

    assert response.status_code == 401


async def test_seeded_columns(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.get(BOARD_URL, headers=auth)

    columns = [(c["name"], c["is_done"]) for c in response.json()["columns"]]
    assert columns == [("To Do", False), ("In Progress", False), ("Done", True)]


async def test_create_status_appends_column(client: AsyncClient, auth: dict[str, str]) -> None:
    created = await _create(client, auth, name="  QA  ", is_done=False)

    assert created["name"] == "QA"
    assert created["is_done"] is False
    assert created["position"] == 4096.0
    assert set(created) == {"id", "name", "position", "is_done", "created_at"}
    assert await _names(client, auth) == ["To Do", "In Progress", "Done", "QA"]


async def test_create_done_status(client: AsyncClient, auth: dict[str, str]) -> None:
    assert (await _create(client, auth, name="Archived", is_done=True))["is_done"] is True


async def test_create_duplicate_status_name_conflicts(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.post(STATUSES_URL, json={"name": "done"}, headers=auth)

    assert response.status_code == 409
    assert response.json() == {"detail": "A status with this name already exists"}


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
async def test_create_status_with_invalid_name(
    client: AsyncClient, auth: dict[str, str], name: str
) -> None:
    response = await client.post(STATUSES_URL, json={"name": name}, headers=auth)

    assert response.status_code == 422
    assert response.json() == validation_error(
        "Status name must be 1-50 characters", "body", "name"
    )


async def test_create_status_rejects_unknown_fields(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.post(STATUSES_URL, json={"name": "QA", "position": 1}, headers=auth)

    assert response.status_code == 422


async def test_rename_status(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    response = await client.patch(
        f"{STATUSES_URL}/{columns['To Do']}", json={"name": "Backlog"}, headers=auth
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Backlog"
    assert await _names(client, auth) == ["Backlog", "In Progress", "Done"]


async def test_rename_status_to_taken_name_conflicts(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    response = await client.patch(
        f"{STATUSES_URL}/{columns['To Do']}", json={"name": "DONE"}, headers=auth
    )

    assert response.status_code == 409


async def test_rename_unknown_status(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.patch(
        f"{STATUSES_URL}/00000000-0000-0000-0000-000000000000", json={"name": "X"}, headers=auth
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Status not found"}


async def test_move_status_to_top(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    response = await client.post(
        f"{STATUSES_URL}/{columns['Done']}/move", json={"before_id": columns["To Do"]}, headers=auth
    )

    assert response.status_code == 200
    assert response.json()["position"] == 512.0
    assert await _names(client, auth) == ["Done", "To Do", "In Progress"]


async def test_move_status_between_and_to_bottom(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    await client.post(
        f"{STATUSES_URL}/{columns['Done']}/move",
        json={"after_id": columns["To Do"], "before_id": columns["In Progress"]},
        headers=auth,
    )
    assert await _names(client, auth) == ["To Do", "Done", "In Progress"]

    await client.post(f"{STATUSES_URL}/{columns['To Do']}/move", json={}, headers=auth)
    assert await _names(client, auth) == ["Done", "In Progress", "To Do"]


async def test_move_status_with_stale_neighbours_conflicts(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    response = await client.post(
        f"{STATUSES_URL}/{columns['Done']}/move",
        json={"after_id": columns["In Progress"], "before_id": columns["To Do"]},
        headers=auth,
    )

    assert response.status_code == 409


async def test_move_unknown_status(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.post(
        f"{STATUSES_URL}/00000000-0000-0000-0000-000000000000/move", json={}, headers=auth
    )

    assert response.status_code == 404


async def test_delete_empty_status(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    response = await client.delete(f"{STATUSES_URL}/{columns['In Progress']}", headers=auth)

    assert response.status_code == 204
    assert response.content == b""
    assert await _names(client, auth) == ["To Do", "Done"]


async def test_delete_status_with_tasks_conflicts(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    await create_task(client, auth, columns["To Do"])

    response = await client.delete(f"{STATUSES_URL}/{columns['To Do']}", headers=auth)

    assert response.status_code == 409
    assert response.json() == {"detail": "Status still has tasks; move or delete them first"}
    assert "To Do" in await _names(client, auth)


async def test_delete_unknown_status(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.delete(
        f"{STATUSES_URL}/00000000-0000-0000-0000-000000000000", headers=auth
    )

    assert response.status_code == 404


# --- list -----------------------------------------------------------------------


async def test_list_statuses_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(STATUSES_URL)

    assert response.status_code == 401


async def test_list_statuses_returns_columns_in_board_order(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    created = await _create(client, auth, name="Review")

    response = await client.get(STATUSES_URL, headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert [s["name"] for s in body["items"]] == ["To Do", "In Progress", "Done", "Review"]
    assert body["items"][-1] == created
    assert {k: body[k] for k in ("total", "page", "size", "pages")} == {
        "total": 4,
        "page": 1,
        "size": 100,
        "pages": 1,
    }


async def test_list_statuses_is_paginated(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.get(STATUSES_URL, params={"page": 2, "size": 2}, headers=auth)

    body = response.json()
    assert [s["name"] for s in body["items"]] == ["Done"]
    assert (body["total"], body["page"], body["size"], body["pages"]) == (3, 2, 2, 2)


@pytest.mark.parametrize("params", [{"size": 101}, {"size": 0}, {"page": 0}])
async def test_list_statuses_rejects_bad_page_params(
    client: AsyncClient, auth: dict[str, str], params: dict[str, int]
) -> None:
    response = await client.get(STATUSES_URL, params=params, headers=auth)

    assert response.status_code == 422
