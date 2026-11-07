from typing import Any

from httpx import AsyncClient

from tests.api.helpers import BOARD_URL, create_task, register


async def test_board_requires_auth(client: AsyncClient) -> None:
    assert (await client.get(BOARD_URL)).status_code == 401


async def test_board_groups_tasks_by_column_in_order(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    first = await create_task(client, auth, columns["To Do"], title="First")
    await create_task(client, auth, columns["To Do"], title="Second")
    await create_task(client, auth, columns["Done"], title="Shipped")
    await client.post(
        f"/api/v1/tasks/{first['id']}/move", json={"status_id": columns["To Do"]}, headers=auth
    )

    response = await client.get(BOARD_URL, headers=auth)

    assert response.status_code == 200
    board = response.json()
    assert [(c["name"], [t["title"] for t in c["tasks"]]) for c in board["columns"]] == [
        ("To Do", ["Second", "First"]),
        ("In Progress", []),
        ("Done", ["Shipped"]),
    ]
    column = board["columns"][0]
    assert set(column) == {"id", "name", "position", "is_done", "tasks"}
    assert set(column["tasks"][0]) == {
        "id",
        "title",
        "description",
        "status_id",
        "assignee",
        "created_by_id",
        "due_date",
        "position",
        "completed_at",
        "created_at",
        "updated_at",
    }


async def test_board_applies_filters_and_keeps_empty_columns(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    bob: str = (await register(client, "bob@example.com")).json()["id"]
    await create_task(client, auth, columns["To Do"], title="Bob's", assignee_id=bob)
    await create_task(client, auth, columns["To Do"], title="Nobody's")
    await create_task(client, auth, columns["Done"], title="Bob's done", assignee_id=bob)

    async def board(**params: Any) -> list[list[str]]:
        response = await client.get(BOARD_URL, params=params, headers=auth)
        assert response.status_code == 200, response.text
        return [[t["title"] for t in c["tasks"]] for c in response.json()["columns"]]

    assert await board(assignee_id=bob) == [["Bob's"], [], ["Bob's done"]]
    assert await board(assignee_id=bob, is_completed="false") == [["Bob's"], [], []]
    assert await board(search="nobody") == [["Nobody's"], [], []]
    assert await board(status_id=columns["Done"]) == [[], [], ["Bob's done"]]


async def test_board_rejects_inverted_due_range(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.get(
        BOARD_URL, params={"due_after": "2030-01-02", "due_before": "2030-01-01"}, headers=auth
    )

    assert response.status_code == 422
