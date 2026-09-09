"""Timing every response, from the first deployment.

We publish a latency budget - under 150 ms p95 for our hop of a sub-1.5-second
first-audio budget - and a budget nobody measures is a wish. Every response
carries `x-response-ms`, including error responses, because a slow failure is
the one most worth seeing in the numbers.

This is deliberately tiny. Observability added later is observability shaped by
what already broke; added now, it is shaped by what we promised.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

RESPONSE_TIME_HEADER = "x-response-ms"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

logger = logging.getLogger("bayyina.access")

Handler = Callable[[Request], Awaitable[Response]]


def configure_logging(level: str) -> None:
    """Attach a handler to the `bayyina` logger tree.

    Without this the timing lines below go nowhere: a library logger with no
    handler inherits the root logger, which defaults to WARNING, so every
    `logger.info` is silently dropped. Under uvicorn that is easy to miss -
    uvicorn prints its own access lines, so the output looks healthy while our
    own measurements never appear.

    Scoped to the `bayyina` tree rather than calling `basicConfig`, so importing
    the package never reconfigures logging for an application that embeds it.

    A handler is attached **only when the tree would otherwise be silent** - no
    handler of our own and nothing on the root logger. That covers plain uvicorn,
    where our lines would vanish, without stealing the logs from a host
    application that has already configured its own. Propagation is left on for
    the same reason: an embedder's handlers, and pytest's `caplog`, must still
    see our records.
    """
    bayyina = logging.getLogger("bayyina")
    bayyina.setLevel(level.upper())

    if not bayyina.handlers and not logging.getLogger().handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        bayyina.addHandler(handler)


def add_response_timing(app: FastAPI) -> None:
    """Stamp every response with the time we spent on it."""

    @app.middleware("http")
    async def _timed(request: Request, call_next: Handler) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000

        response.headers[RESPONSE_TIME_HEADER] = f"{elapsed_ms:.1f}"
        logger.info(
            "%s %s %s %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
