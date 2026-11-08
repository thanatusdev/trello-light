import pytest

from app.domain.errors import ValidationError
from app.domain.statuses import STATUS_NAME_MAX_LENGTH, Status, StatusName
from tests.unit.application.fakes import FIXED_NOW


def test_status_name_is_trimmed() -> None:
    assert StatusName("  In Progress ").value == "In Progress"


@pytest.mark.parametrize("raw", ["", "   ", "x" * (STATUS_NAME_MAX_LENGTH + 1)])
def test_status_name_rejects_invalid_length(raw: str) -> None:
    with pytest.raises(ValidationError):
        StatusName(raw)


def test_status_name_accepts_max_length() -> None:
    assert StatusName("x" * STATUS_NAME_MAX_LENGTH).value == "x" * STATUS_NAME_MAX_LENGTH


def test_status_name_matches_case_insensitively() -> None:
    assert StatusName("Done").matches(StatusName(" done "))
    assert not StatusName("Done").matches(StatusName("Doing"))


def test_status_name_matching_follows_the_database_lower() -> None:
    # The unique index is on lower(name); casefold() would treat these as equal, lower() doesn't.
    assert not StatusName("Straße").matches(StatusName("STRASSE"))


def test_create_status() -> None:
    status = Status.create(name=StatusName("Done"), is_done=True, position=1024.0, now=FIXED_NOW)

    assert status.name == StatusName("Done")
    assert status.is_done is True
    assert status.position == 1024.0
    assert status.created_at == FIXED_NOW


def test_rename_status() -> None:
    status = Status.create(name=StatusName("Todo"), is_done=False, position=1.0, now=FIXED_NOW)

    status.rename(StatusName("To Do"))

    assert status.name == StatusName("To Do")
