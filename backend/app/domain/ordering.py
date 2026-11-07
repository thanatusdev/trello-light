"""Fractional indexing for ordered items (tasks within a column, columns on the board).

Positions are floats. A moved item gets the midpoint between its new neighbours; the
top of a list is bounded by 0 and the bottom is open-ended. When two neighbours get
closer than ``MIN_GAP`` the whole list is renumbered to evenly spaced positions.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from app.domain.errors import StaleOrdering

STEP = 1024.0
MIN_GAP = 1e-6


@dataclass(frozen=True, slots=True)
class Placement:
    position: float
    # Positions of other items that had to be renumbered; empty when no rebalance happened.
    rebalanced: dict[UUID, float] = field(default_factory=dict)


def position_between(prev: float | None, next_: float | None) -> float | None:
    """Position between two neighbours, or ``None`` if the gap is too small."""
    if next_ is None:
        return STEP if prev is None else prev + STEP
    lower = 0.0 if prev is None else prev
    gap = next_ - lower
    if gap < MIN_GAP:
        return None
    return lower + gap / 2


def evenly_spaced(count: int) -> list[float]:
    return [STEP * (i + 1) for i in range(count)]


def _insert_index(sibling_ids: list[UUID], after_id: UUID | None, before_id: UUID | None) -> int:
    def index_of(item_id: UUID) -> int:
        try:
            return sibling_ids.index(item_id)
        except ValueError:
            raise StaleOrdering() from None

    if after_id is None and before_id is None:
        return len(sibling_ids)
    if before_id is None:
        assert after_id is not None  # noqa: S101 - narrowed by the branch above
        return index_of(after_id) + 1
    before_index = index_of(before_id)
    if after_id is not None and index_of(after_id) + 1 != before_index:
        raise StaleOrdering()
    return before_index


def place(
    siblings: Sequence[tuple[UUID, float]],
    item_id: UUID,
    *,
    after_id: UUID | None = None,
    before_id: UUID | None = None,
) -> Placement:
    """Work out where ``item_id`` goes among ``siblings`` (ordered by position).

    ``after_id``/``before_id`` name the neighbours the client saw; with neither the item
    goes to the bottom. Neighbours that are unknown, not adjacent, or the item itself mean
    the client's view is stale.
    """
    if item_id in (after_id, before_id):
        raise StaleOrdering()
    others = [(sid, pos) for sid, pos in siblings if sid != item_id]
    index = _insert_index([sid for sid, _ in others], after_id, before_id)

    def neighbours(positions: list[float]) -> tuple[float | None, float | None]:
        prev = positions[index - 1] if index > 0 else None
        next_ = positions[index] if index < len(positions) else None
        return prev, next_

    position = position_between(*neighbours([pos for _, pos in others]))
    if position is not None:
        return Placement(position)

    renumbered = evenly_spaced(len(others))
    position = position_between(*neighbours(renumbered))
    assert position is not None  # noqa: S101 - evenly spaced gaps are always wide enough
    return Placement(
        position, rebalanced={sid: pos for (sid, _), pos in zip(others, renumbered, strict=True)}
    )
