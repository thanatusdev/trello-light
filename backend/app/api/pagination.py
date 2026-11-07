from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

MAX_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int
    size: int


def page_params(default_size: int = 20) -> Callable[..., PageParams]:
    """Dependency reading ``?page=&size=``, with ``size`` defaulting to ``default_size``."""

    def dependency(
        page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
        size: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description="Items per page")
        ] = default_size,
    ) -> PageParams:
        return PageParams(page=page, size=size)

    return dependency


get_page_params = page_params()


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
