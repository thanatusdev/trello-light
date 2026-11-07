from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def __call__(self) -> datetime: ...
