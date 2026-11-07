from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.task import TaskModel
from app.infrastructure.models.user import UserModel
from tests.api.helpers import TASKS_URL, create_task, register, validation_error
from tests.unit.application.fakes import FakeNotifier

TODAY = datetime.now(UTC).date()
UNKNOWN_ID = "00000000-0000-0000-0000-000000000000"


async def _me(client: AsyncClient, auth: dict[str, str]) -> dict[str, Any]:
    body: dict[str, Any] = (await client.get("/api/v1/auth/me", headers=auth)).json()
    return body


async def _user_id(client: AsyncClient, email: str) -> str:
    response = await register(client, email)
    assert response.status_code == 201
    user_id: str = response.json()["id"]
    return user_id


async def _column_titles(client: AsyncClient, auth: dict[str, str], status_id: str) -> list[str]:
    response = await client.get(
        TASKS_URL, params={"status_id": status_id, "size": 100}, headers=auth
    )
    items = sorted(response.json()["items"], key=lambda t: t["position"])
    return [t["title"] for t in items]


async def _fill(
    client: AsyncClient, auth: dict[str, str], status_id: str, count: int
) -> list[dict[str, Any]]:
    return [await create_task(client, auth, status_id, title=f"T{i}") for i in range(count)]


async def _move(
    client: AsyncClient, auth: dict[str, str], task_id: str, **body: Any
) -> dict[str, Any]:
    response = await client.post(f"{TASKS_URL}/{task_id}/move", json=body, headers=auth)
    assert response.status_code == 200, response.text
    moved: dict[str, Any] = response.json()
    return moved


# --- auth -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", ""),
        ("post", ""),
        ("get", f"/{UNKNOWN_ID}"),
        ("patch", f"/{UNKNOWN_ID}"),
        ("delete", f"/{UNKNOWN_ID}"),
        ("post", f"/{UNKNOWN_ID}/move"),
        ("put", f"/{UNKNOWN_ID}/assignee"),
    ],
)
async def test_task_endpoints_require_auth(client: AsyncClient, method: str, path: str) -> None:
    response = await client.request(method, TASKS_URL + path, json={})

    assert response.status_code == 401


# --- create ---------------------------------------------------------------------


async def test_create_task(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    me = await _me(client, auth)
    response = await client.post(
        TASKS_URL,
        json={
            "title": "  Write docs ",
            "description": "All of them",
            "status_id": columns["To Do"],
            "assignee_id": me["id"],
            "due_date": TODAY.isoformat(),
        },
        headers=auth,
    )

    assert response.status_code == 201
    task = response.json()
    assert task["title"] == "Write docs"
    assert task["description"] == "All of them"
    assert task["status_id"] == columns["To Do"]
    assert task["assignee"] == {"id": me["id"], "full_name": "Alice Smith"}
    assert task["created_by_id"] == me["id"]
    assert task["due_date"] == TODAY.isoformat()
    assert task["position"] == 1024.0
    assert task["completed_at"] is None
    assert task["created_at"] == task["updated_at"]


async def test_create_task_in_done_column_is_completed(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["Done"])

    assert task["completed_at"] is not None


async def test_create_task_appends_to_bottom(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    tasks = await _fill(client, auth, columns["To Do"], 3)

    assert [t["position"] for t in tasks] == [1024.0, 2048.0, 3072.0]


async def test_create_task_with_past_due_date_is_rejected(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    response = await client.post(
        TASKS_URL,
        json={
            "title": "Late",
            "status_id": columns["To Do"],
            "due_date": (TODAY - timedelta(days=1)).isoformat(),
        },
        headers=auth,
    )

    assert response.status_code == 422
    assert response.json() == validation_error("due_date cannot be in the past", "body", "due_date")


@pytest.mark.parametrize(
    ("field", "detail"),
    [
        ("status_id", "status_id does not reference an existing status"),
        ("assignee_id", "assignee_id must reference an active user"),
    ],
)
async def test_create_task_with_unknown_reference(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str], field: str, detail: str
) -> None:
    body = {"title": "X", "status_id": columns["To Do"], field: UNKNOWN_ID}

    response = await client.post(TASKS_URL, json=body, headers=auth)

    assert response.status_code == 422
    assert response.json() == validation_error(detail, "body", field)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"title": ""}, id="empty-title"),
        pytest.param({"title": "   "}, id="blank-title"),
        pytest.param({"title": "x" * 201}, id="long-title"),
        pytest.param({"title": None}, id="null-title"),
        pytest.param({}, id="missing-title"),
        pytest.param({"title": "ok", "status_id": "not-a-uuid"}, id="bad-uuid"),
        pytest.param({"title": "ok", "due_date": "tomorrow"}, id="bad-date"),
        pytest.param({"title": "ok", "position": 1}, id="unknown-field"),
    ],
)
async def test_create_task_validation(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str], body: dict[str, Any]
) -> None:
    response = await client.post(
        TASKS_URL, json={"status_id": columns["To Do"], **body}, headers=auth
    )

    assert response.status_code == 422


async def test_create_task_title_at_max_length(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["To Do"], title="x" * 200)

    assert len(task["title"]) == 200


# --- get / list -----------------------------------------------------------------


async def test_get_task(client: AsyncClient, auth: dict[str, str], columns: dict[str, str]) -> None:
    task = await create_task(client, auth, columns["To Do"])

    response = await client.get(f"{TASKS_URL}/{task['id']}", headers=auth)

    assert response.status_code == 200
    assert response.json() == task


async def test_get_unknown_task(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.get(f"{TASKS_URL}/{UNKNOWN_ID}", headers=auth)

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


async def test_list_tasks_pagination(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    await _fill(client, auth, columns["To Do"], 5)

    page = (await client.get(TASKS_URL, params={"page": 2, "size": 2}, headers=auth)).json()
    beyond = (await client.get(TASKS_URL, params={"page": 9, "size": 2}, headers=auth)).json()
    default = (await client.get(TASKS_URL, headers=auth)).json()

    assert (page["total"], page["page"], page["size"], page["pages"]) == (5, 2, 2, 3)
    assert [t["title"] for t in page["items"]] == ["T2", "T1"]  # newest first
    assert beyond["items"] == [] and beyond["total"] == 5
    assert (default["page"], default["size"], len(default["items"])) == (1, 20, 5)


async def test_list_tasks_max_page_size(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.get(TASKS_URL, params={"size": 100}, headers=auth)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"size": 0},
        {"size": 101},
        {"status_id": "nope"},
        {"is_completed": "maybe"},
        {"due_before": "2026-13-01"},
    ],
)
async def test_list_tasks_rejects_bad_params(
    client: AsyncClient, auth: dict[str, str], params: dict[str, Any]
) -> None:
    response = await client.get(TASKS_URL, params=params, headers=auth)

    assert response.status_code == 422


async def test_list_tasks_rejects_inverted_due_range(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.get(
        TASKS_URL, params={"due_after": "2030-01-02", "due_before": "2030-01-01"}, headers=auth
    )

    assert response.status_code == 422
    assert response.json() == validation_error(
        "due_after must be on or before due_before", "query", "due_after"
    )


async def test_list_tasks_filter_combinations(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    bob = await _user_id(client, "bob@example.com")
    soon = TODAY + timedelta(days=3)
    later = TODAY + timedelta(days=30)
    await create_task(
        client,
        auth,
        columns["To Do"],
        title="Fix login bug",
        assignee_id=bob,
        due_date=soon.isoformat(),
    )
    await create_task(client, auth, columns["To Do"], title="Write README")
    await create_task(
        client,
        auth,
        columns["Done"],
        title="Fix CI bug",
        assignee_id=bob,
        due_date=later.isoformat(),
    )
    await create_task(
        client, auth, columns["In Progress"], title="Refactor", due_date=later.isoformat()
    )

    async def titles(**params: Any) -> list[str]:
        response = await client.get(TASKS_URL, params=params, headers=auth)
        assert response.status_code == 200, response.text
        return sorted(t["title"] for t in response.json()["items"])

    assert await titles(assignee_id=bob) == ["Fix CI bug", "Fix login bug"]
    assert await titles(assignee_id=bob, is_completed="false") == ["Fix login bug"]
    assert await titles(is_completed="true") == ["Fix CI bug"]
    assert await titles(search="BUG", status_id=columns["To Do"]) == ["Fix login bug"]
    assert await titles(due_before=soon.isoformat()) == ["Fix login bug"]
    assert await titles(due_after=soon.isoformat()) == ["Fix CI bug", "Fix login bug", "Refactor"]
    assert await titles(
        due_after=later.isoformat(), due_before=later.isoformat(), search="fix"
    ) == ["Fix CI bug"]
    assert await titles(search="nothing matches") == []


# --- update ---------------------------------------------------------------------


async def test_update_task_partially(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(
        client, auth, columns["To Do"], description="keep me", due_date=TODAY.isoformat()
    )

    response = await client.patch(
        f"{TASKS_URL}/{task['id']}", json={"title": "Renamed"}, headers=auth
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Renamed"
    assert updated["description"] == "keep me"
    assert updated["due_date"] == TODAY.isoformat()
    assert updated["updated_at"] >= task["updated_at"]


async def test_update_task_clears_with_null(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(
        client, auth, columns["To Do"], description="x", due_date=TODAY.isoformat()
    )

    response = await client.patch(
        f"{TASKS_URL}/{task['id']}", json={"description": None, "due_date": None}, headers=auth
    )

    assert (response.json()["description"], response.json()["due_date"]) == (None, None)


async def test_update_task_keeps_existing_overdue_date(
    client: AsyncClient,
    auth: dict[str, str],
    columns: dict[str, str],
    db_session: AsyncSession,
) -> None:
    task = await create_task(client, auth, columns["To Do"])
    overdue = TODAY - timedelta(days=3)
    await db_session.execute(
        update(TaskModel).where(TaskModel.id == task["id"]).values(due_date=overdue)
    )

    unchanged = await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"title": "Still late", "due_date": overdue.isoformat()},
        headers=auth,
    )
    changed = await client.patch(
        f"{TASKS_URL}/{task['id']}",
        json={"due_date": (overdue - timedelta(days=1)).isoformat()},
        headers=auth,
    )

    assert unchanged.status_code == 200
    assert changed.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"title": None}, id="null-title"),
        pytest.param({"title": " "}, id="blank-title"),
        pytest.param({"status_id": UNKNOWN_ID}, id="status-via-patch"),
        pytest.param({"assignee_id": UNKNOWN_ID}, id="assignee-via-patch"),
        pytest.param({"due_date": (TODAY - timedelta(days=1)).isoformat()}, id="past-due"),
    ],
)
async def test_update_task_validation(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str], body: dict[str, Any]
) -> None:
    task = await create_task(client, auth, columns["To Do"])

    response = await client.patch(f"{TASKS_URL}/{task['id']}", json=body, headers=auth)

    assert response.status_code == 422


async def test_update_unknown_task(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.patch(f"{TASKS_URL}/{UNKNOWN_ID}", json={"title": "X"}, headers=auth)

    assert response.status_code == 404


# --- delete ---------------------------------------------------------------------


async def test_delete_task(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["To Do"])

    response = await client.delete(f"{TASKS_URL}/{task['id']}", headers=auth)

    assert response.status_code == 204
    assert (await client.get(f"{TASKS_URL}/{task['id']}", headers=auth)).status_code == 404


async def test_delete_unknown_task(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.delete(f"{TASKS_URL}/{UNKNOWN_ID}", headers=auth)

    assert response.status_code == 404


# --- move -----------------------------------------------------------------------


async def test_move_into_done_and_back(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["To Do"])

    done = await _move(client, auth, task["id"], status_id=columns["Done"])
    assert done["status_id"] == columns["Done"]
    assert done["completed_at"] is not None
    assert done["position"] == 1024.0  # empty column

    reopened = await _move(client, auth, task["id"], status_id=columns["In Progress"])
    assert reopened["completed_at"] is None


async def test_move_to_top_of_empty_column(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["To Do"])

    moved = await _move(client, auth, task["id"], status_id=columns["In Progress"])

    assert await _column_titles(client, auth, columns["In Progress"]) == [task["title"]]
    assert moved["position"] == 1024.0


async def test_move_to_top_and_bottom_of_full_column(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    column = await _fill(client, auth, columns["In Progress"], 10)
    top = await create_task(client, auth, columns["To Do"], title="Top")
    bottom = await create_task(client, auth, columns["To Do"], title="Bottom")

    await _move(
        client, auth, top["id"], status_id=columns["In Progress"], before_id=column[0]["id"]
    )
    await _move(
        client, auth, bottom["id"], status_id=columns["In Progress"], after_id=column[-1]["id"]
    )

    titles = await _column_titles(client, auth, columns["In Progress"])
    assert titles == ["Top", *[f"T{i}" for i in range(10)], "Bottom"]


async def test_move_within_column(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    a, b, c = await _fill(client, auth, columns["To Do"], 3)

    await _move(
        client, auth, c["id"], status_id=columns["To Do"], after_id=a["id"], before_id=b["id"]
    )

    assert await _column_titles(client, auth, columns["To Do"]) == ["T0", "T2", "T1"]


async def test_move_rebalances_crowded_column(
    client: AsyncClient,
    auth: dict[str, str],
    columns: dict[str, str],
    db_session: AsyncSession,
) -> None:
    a, b = await _fill(client, auth, columns["In Progress"], 2)
    await db_session.execute(
        update(TaskModel).where(TaskModel.id == b["id"]).values(position=1024.0 + 1e-7)
    )
    task = await create_task(client, auth, columns["To Do"], title="Squeezed")

    moved = await _move(
        client,
        auth,
        task["id"],
        status_id=columns["In Progress"],
        after_id=a["id"],
        before_id=b["id"],
    )

    assert moved["position"] == 1536.0
    assert await _column_titles(client, auth, columns["In Progress"]) == ["T0", "Squeezed", "T1"]
    b_after = (await client.get(f"{TASKS_URL}/{b['id']}", headers=auth)).json()
    assert b_after["position"] == 2048.0


async def test_move_with_stale_neighbours_conflicts(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task, other = await _fill(client, auth, columns["To Do"], 2)

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/move",
        json={"status_id": columns["Done"], "before_id": other["id"]},
        headers=auth,
    )

    assert response.status_code == 409


async def test_move_to_unknown_status(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["To Do"])

    response = await client.post(
        f"{TASKS_URL}/{task['id']}/move", json={"status_id": UNKNOWN_ID}, headers=auth
    )

    assert response.status_code == 422


async def test_move_unknown_task(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    response = await client.post(
        f"{TASKS_URL}/{UNKNOWN_ID}/move", json={"status_id": columns["Done"]}, headers=auth
    )

    assert response.status_code == 404


async def test_move_requires_status_id(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["To Do"])

    response = await client.post(f"{TASKS_URL}/{task['id']}/move", json={}, headers=auth)

    assert response.status_code == 422


# --- assign ---------------------------------------------------------------------


async def test_assign_and_unassign(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    bob = await _user_id(client, "bob@example.com")
    task = await create_task(client, auth, columns["To Do"])
    url = f"{TASKS_URL}/{task['id']}/assignee"

    assigned = await client.put(url, json={"assignee_id": bob}, headers=auth)
    assert assigned.status_code == 200
    assert assigned.json()["assignee"] == {"id": bob, "full_name": "Alice Smith"}

    unassigned = await client.put(url, json={"assignee_id": None}, headers=auth)
    assert unassigned.json()["assignee"] is None


async def test_assign_notifies_assignee_with_current_user_as_assigner(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str], notifier: FakeNotifier
) -> None:
    me = await _me(client, auth)
    bob = await _user_id(client, "bob@example.com")
    task = await create_task(client, auth, columns["To Do"])

    await client.put(f"{TASKS_URL}/{task['id']}/assignee", json={"assignee_id": bob}, headers=auth)
    await client.put(
        f"{TASKS_URL}/{task['id']}/assignee", json={"assignee_id": me["id"]}, headers=auth
    )

    assert [
        (str(a.task_id), str(a.assignee_id), str(a.assigned_by_id)) for a in notifier.assignments
    ] == [(task["id"], bob, me["id"])]


async def test_create_with_assignee_notifies(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str], notifier: FakeNotifier
) -> None:
    bob = await _user_id(client, "bob@example.com")

    task = await create_task(client, auth, columns["To Do"], assignee_id=bob)

    assert [str(a.task_id) for a in notifier.assignments] == [task["id"]]


async def test_assign_inactive_user(
    client: AsyncClient,
    auth: dict[str, str],
    columns: dict[str, str],
    db_session: AsyncSession,
) -> None:
    bob = await _user_id(client, "bob@example.com")
    await db_session.execute(update(UserModel).where(UserModel.id == bob).values(is_active=False))
    task = await create_task(client, auth, columns["To Do"])

    response = await client.put(
        f"{TASKS_URL}/{task['id']}/assignee", json={"assignee_id": bob}, headers=auth
    )

    assert response.status_code == 422
    assert response.json() == validation_error(
        "assignee_id must reference an active user", "body", "assignee_id"
    )


async def test_assign_unknown_user_and_task(
    client: AsyncClient, auth: dict[str, str], columns: dict[str, str]
) -> None:
    task = await create_task(client, auth, columns["To Do"])

    unknown_user = await client.put(
        f"{TASKS_URL}/{task['id']}/assignee", json={"assignee_id": UNKNOWN_ID}, headers=auth
    )
    unknown_task = await client.put(
        f"{TASKS_URL}/{UNKNOWN_ID}/assignee", json={"assignee_id": None}, headers=auth
    )
    missing_field = await client.put(f"{TASKS_URL}/{task['id']}/assignee", json={}, headers=auth)

    assert unknown_user.status_code == 422
    assert unknown_task.status_code == 404
    assert missing_field.status_code == 422
