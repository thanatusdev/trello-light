from uuid import UUID, uuid4

import pytest

from app.domain.errors import StaleOrdering
from app.domain.ordering import MIN_GAP, STEP, place, position_between


def _ids(n: int) -> list[UUID]:
    return [uuid4() for _ in range(n)]


# --- position_between ---------------------------------------------------------


def test_empty_column_starts_at_step() -> None:
    assert position_between(None, None) == STEP


def test_bottom_appends_one_step_after_last() -> None:
    assert position_between(3000.0, None) == 3000.0 + STEP


def test_top_halves_first_position() -> None:
    assert position_between(None, 1024.0) == 512.0


def test_between_is_midpoint() -> None:
    assert position_between(1024.0, 2048.0) == 1536.0


def test_returns_none_when_gap_too_small() -> None:
    assert position_between(1.0, 1.0 + MIN_GAP / 2) is None


def test_returns_none_when_top_gap_too_small() -> None:
    assert position_between(None, MIN_GAP / 2) is None


# --- place ----------------------------------------------------------------------


def test_place_with_no_neighbours_goes_to_bottom() -> None:
    a, b, moving = _ids(3)
    placement = place([(a, 1024.0), (b, 2048.0)], moving)

    assert placement.position == 2048.0 + STEP
    assert placement.rebalanced == {}


def test_place_in_empty_column() -> None:
    placement = place([], uuid4())

    assert placement.position == STEP


def test_place_before_first_goes_to_top() -> None:
    a, b, moving = _ids(3)
    placement = place([(a, 1024.0), (b, 2048.0)], moving, before_id=a)

    assert placement.position == 512.0


def test_place_after_last_goes_to_bottom() -> None:
    a, b, moving = _ids(3)
    placement = place([(a, 1024.0), (b, 2048.0)], moving, after_id=b)

    assert placement.position == 2048.0 + STEP


def test_place_between_adjacent_neighbours() -> None:
    a, b, c, moving = _ids(4)
    siblings = [(a, 1024.0), (b, 2048.0), (c, 3072.0)]

    assert place(siblings, moving, after_id=a, before_id=b).position == 1536.0
    assert place(siblings, moving, after_id=b).position == 2560.0
    assert place(siblings, moving, before_id=c).position == 2560.0


def test_place_ignores_the_moving_item_among_siblings() -> None:
    a, b, moving = _ids(3)
    # Moving within its own column: its current slot must not count as a neighbour.
    siblings = [(a, 1024.0), (moving, 2048.0), (b, 3072.0)]

    assert place(siblings, moving, after_id=a, before_id=b).position == 2048.0


@pytest.mark.parametrize(
    ("after", "before"),
    [
        pytest.param("unknown", None, id="unknown-after"),
        pytest.param(None, "unknown", id="unknown-before"),
        pytest.param("b", "a", id="reversed"),
        pytest.param("a", "c", id="not-adjacent"),
        pytest.param("moving", None, id="after-itself"),
        pytest.param(None, "moving", id="before-itself"),
    ],
)
def test_place_rejects_stale_neighbours(after: str | None, before: str | None) -> None:
    ids = {"a": uuid4(), "b": uuid4(), "c": uuid4(), "moving": uuid4(), "unknown": uuid4()}
    siblings = [(ids["a"], 1024.0), (ids["b"], 2048.0), (ids["c"], 3072.0)]

    with pytest.raises(StaleOrdering):
        place(
            siblings,
            ids["moving"],
            after_id=ids[after] if after else None,
            before_id=ids[before] if before else None,
        )


def test_place_rebalances_column_when_gap_is_exhausted() -> None:
    a, b, c, moving = _ids(4)
    siblings = [(a, 1.0), (b, 1.0 + MIN_GAP / 2), (c, 5.0)]

    placement = place(siblings, moving, after_id=a, before_id=b)

    assert placement.rebalanced == {a: STEP, b: 2 * STEP, c: 3 * STEP}
    assert placement.position == 1.5 * STEP


def test_place_rebalances_when_top_gap_is_exhausted() -> None:
    a, moving = _ids(2)

    placement = place([(a, MIN_GAP / 2)], moving, before_id=a)

    assert placement.rebalanced == {a: STEP}
    assert placement.position == STEP / 2
