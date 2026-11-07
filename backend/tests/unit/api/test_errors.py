import json

from fastapi import Request

from app.api.errors import domain_error_handler
from app.domain.errors import (
    DomainError,
    EmailAlreadyRegistered,
    InvalidToken,
    UnknownStatus,
    ValidationError,
)

REQUEST = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
REQUEST_POST = Request({"type": "http", "method": "POST", "path": "/", "headers": []})


async def test_uncategorised_domain_error_is_400() -> None:
    response = await domain_error_handler(REQUEST, DomainError("Something odd"))

    assert response.status_code == 400
    assert json.loads(response.body) == {"detail": "Something odd"}
    assert "www-authenticate" not in response.headers


async def test_authentication_error_sets_bearer_challenge() -> None:
    response = await domain_error_handler(REQUEST, InvalidToken())

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_conflict_maps_to_409() -> None:
    response = await domain_error_handler(REQUEST, EmailAlreadyRegistered())

    assert response.status_code == 409


async def test_validation_error_uses_fastapi_list_shape_with_field() -> None:
    response = await domain_error_handler(REQUEST_POST, UnknownStatus())

    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": [
            {
                "loc": ["body", "status_id"],
                "msg": "status_id does not reference an existing status",
                "type": "value_error",
            }
        ]
    }


async def test_validation_error_without_field_points_at_body() -> None:
    response = await domain_error_handler(REQUEST_POST, ValidationError("Bad value"))

    assert json.loads(response.body) == {
        "detail": [{"loc": ["body"], "msg": "Bad value", "type": "value_error"}]
    }


async def test_validation_error_on_get_points_at_query() -> None:
    response = await domain_error_handler(REQUEST, ValidationError("Bad filter", field="due_after"))

    assert json.loads(response.body)["detail"][0]["loc"] == ["query", "due_after"]
