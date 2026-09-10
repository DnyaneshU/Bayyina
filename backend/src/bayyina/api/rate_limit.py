"""A per-client request limit on the public endpoints.

`/evaluate` is a public POST that runs a rule and appends to the audit log. Left
open it is both a cost and a way to fill the log with noise, and `.env.example`
has advertised `PUBLIC_RATE_LIMIT_PER_MINUTE` as an abuse guard since T1.1 with
nothing behind it. This is the thing behind it.

**`/healthz` is deliberately exempt.** Hosting platforms poll it every few
seconds; rate-limiting it would make the platform mark a healthy service dead.

Two honest limits, both consequences of keeping this in-process rather than
adding Redis for a service that fits in one container:

- **Per process.** Two workers means two counters and twice the effective limit.
- **Fixed window.** A burst straddling a window boundary can briefly exceed the
  limit. A sliding window costs more memory than the problem is worth here.

It is an abuse guard, not a quota system, and the docstring says so rather than
letting someone later assume it is exact.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from .errors import Failure, behaviour

WINDOW_SECONDS = 60

# Polled by the platform, so never limited. Anything added here must be cheap
# and safe to call as often as a load balancer likes.
EXEMPT_PATHS = frozenset({"/healthz"})

Handler = Callable[[Request], Awaitable[Response]]


class FixedWindowLimiter:
    """Counts requests per client in a fixed window."""

    def __init__(self, per_minute: int) -> None:
        self._per_minute = per_minute
        self._counts: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()

    def check(self, client: str, now: float | None = None) -> tuple[bool, int]:
        """Return whether the request is allowed, and seconds until the reset."""
        moment = time.monotonic() if now is None else now
        window = int(moment // WINDOW_SECONDS)
        resets_in = WINDOW_SECONDS - int(moment % WINDOW_SECONDS)

        with self._lock:
            recorded_window, count = self._counts.get(client, (window, 0))
            if recorded_window != window:
                recorded_window, count = window, 0

            if count >= self._per_minute:
                return False, resets_in

            self._counts[client] = (recorded_window, count + 1)

            # The map only grows while a window is open, and every entry in a
            # stale window is dead. Cleared opportunistically so a long-running
            # process does not accumulate one entry per address seen all day.
            if len(self._counts) > 10_000:
                self._counts = {
                    key: value for key, value in self._counts.items() if value[0] == window
                }

            return True, resets_in


def _client_of(request: Request) -> str:
    """Who to count against.

    Behind a proxy this is the proxy unless uvicorn runs with `--proxy-headers`,
    which is why T1.9 sets that flag. Without it every request appears to come
    from one address and the limit would apply to all callers collectively.
    """
    return request.client.host if request.client else "unknown"


def add_rate_limiting(app: FastAPI, per_minute: int) -> None:
    """Apply the limit to every public route except the health check."""
    limiter = FixedWindowLimiter(per_minute)
    app.state.rate_limiter = limiter

    @app.middleware("http")
    async def _limited(request: Request, call_next: Handler) -> Response:
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        allowed, resets_in = limiter.check(_client_of(request))
        if not allowed:
            return JSONResponse(
                status_code=behaviour(Failure.RATE_LIMITED).status,
                content={
                    "detail": (
                        f"Too many requests. The limit is {per_minute} per minute. "
                        f"Try again in {resets_in} seconds."
                    )
                },
                headers={"Retry-After": str(resets_in)},
            )

        return await call_next(request)
