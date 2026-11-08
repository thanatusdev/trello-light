"""Rate limiting with slowapi.

Each app gets its own slowapi ``Limiter`` (on ``app.state.limiter``) built from its
settings, so limits, storage and the on/off switch are not import-time globals.

- Every API route has the default limit, counted per route and per caller: the user id
  when the request carries a valid access token, otherwise the client IP.
- Login and register instead have stricter limits counted per client IP.
- The client IP is ``request.client.host``. The app itself never reads ``X-Forwarded-For``;
  behind a proxy, uvicorn's ``--proxy-headers --forwarded-allow-ips=<proxy ip>`` replaces
  the socket peer with the forwarded address. In compose the API is only reachable on the
  internal network and nginx overwrites ``X-Forwarded-For`` with ``$remote_addr``, so the
  image and compose trust ``*``. Do not publish the API port to untrusted networks.
- Storage errors are logged and the request is allowed (fail open).

Limits are enforced by FastAPI dependencies rather than ``SlowAPIMiddleware`` or
``@limiter.limit``: the decorator binds to one module-level limiter, and the middleware
cannot find endpoints in FastAPI >= 0.162 (included routers are no longer flattened into
``app.routes``), so it silently lets every request through.
"""

import logging
import math
import time
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from limits import RateLimitItem, parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.dependencies import get_clock, get_token_service
from app.api.schemas.errors import ErrorResponse
from app.application.ports.token_service import TokenType
from app.domain.errors import InvalidToken
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)

RATE_LIMITED_DETAIL = "Rate limit exceeded, try again later"


def rate_limited_response(description: str) -> dict[int | str, dict[str, Any]]:
    """OpenAPI entry for the 429 a rate-limited route can return."""
    return {
        429: {
            "model": ErrorResponse,
            "description": description,
            "headers": {
                "Retry-After": {
                    "description": "Seconds to wait before retrying",
                    "schema": {"type": "integer"},
                }
            },
        }
    }


# Documented once on the router that applies ``default_rate_limit``.
RATE_LIMITED_RESPONSES = rate_limited_response("Too many requests; see the `Retry-After` header")


class RateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(RATE_LIMITED_DETAIL)
        self.retry_after = retry_after


def client_ip(request: Request) -> str:
    return f"ip:{get_remote_address(request)}"


def user_or_ip(request: Request) -> str:
    """The authenticated user's id, or the client IP if there is no valid access token."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        tokens = get_token_service(request.app.state.settings, get_clock())
        try:
            return f"user:{tokens.decode(token, TokenType.ACCESS)}"
        except InvalidToken:
            pass
    return client_ip(request)


def _retry_after(limiter: Limiter, item: RateLimitItem, *identifiers: str) -> int:
    reset_at, _ = limiter.limiter.get_window_stats(item, *identifiers)
    return max(1, math.ceil(reset_at - time.time()))


def _check(request: Request, limit: str, key: str) -> None:
    limiter: Limiter = request.app.state.limiter
    if not limiter.enabled:
        return
    item = parse(limit)
    identifiers = (request.scope["route"].path, key)
    try:
        if limiter.limiter.hit(item, *identifiers):
            return
        retry_after = _retry_after(limiter, item, *identifiers)
    except Exception:
        logger.exception("Rate limit storage failed; allowing the request")
        return
    raise RateLimited(retry_after)


def default_rate_limit(request: Request) -> None:
    """Router dependency: the default limit, per route and per user (or IP)."""
    if request.scope["endpoint"] in request.app.state.rate_limit_exempt:
        return
    _check(request, request.app.state.settings.rate_limit_default, user_or_ip(request))


def ip_rate_limit(limit: Callable[[Settings], str]) -> Callable[[Request], None]:
    """Route dependency: at most ``limit(settings)`` requests per client IP to this route.
    Such routes must also be exempt from the default limit."""

    def dependency(request: Request) -> None:
        _check(request, limit(request.app.state.settings), client_ip(request))

    return dependency


async def rate_limited_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RateLimited):  # pragma: no cover - only registered for RateLimited
        raise exc
    return JSONResponse(
        {"detail": RATE_LIMITED_DETAIL},
        status_code=429,
        headers={"Retry-After": str(exc.retry_after)},
    )


def install_rate_limiting(
    app: FastAPI, settings: Settings, *, exempt: list[Callable[..., object]]
) -> None:
    """``exempt`` endpoints skip the default limit (health checks, and routes that use
    ``ip_rate_limit`` instead). Add ``default_rate_limit`` to the API router."""
    app.state.limiter = Limiter(
        key_func=user_or_ip,
        storage_uri=settings.rate_limit_storage,
        enabled=settings.rate_limit_enabled,
    )
    app.state.rate_limit_exempt = frozenset(exempt)
    app.add_exception_handler(RateLimited, rate_limited_handler)
