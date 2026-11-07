import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageRequest:
    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(frozen=True, slots=True)
class PageResult[T]:
    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return math.ceil(self.total / self.size)
