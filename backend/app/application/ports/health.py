from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HealthReport:
    database: bool
    redis: bool

    @property
    def healthy(self) -> bool:
        return self.database and self.redis


class HealthProbe(Protocol):
    async def check(self) -> HealthReport:
        """Probe every backing service. Never raises: a failure is reported as ``False``."""
        ...
