from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_health_probe
from app.api.schemas.health import HealthChecks, HealthResponse
from app.application.ports.health import HealthProbe

router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "",
    summary="Service health",
    description="Reports reachability of the database and Redis. Returns 503 if any check fails.",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health(
    response: Response, probe: Annotated[HealthProbe, Depends(get_health_probe)]
) -> HealthResponse:
    report = await probe.check()
    if not report.healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if report.healthy else "degraded",
        checks=HealthChecks(
            database="ok" if report.database else "error",
            redis="ok" if report.redis else "error",
        ),
    )
