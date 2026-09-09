"""Response headers that constrain what a browser will do with our pages.

The checker shows someone a figure they may act on and, later, a link to their
own evidence pack. The headers here exist so that a page which looks like ours
cannot be framed inside someone else's, and so that a browser that once reached
us over HTTPS refuses to try HTTP again.

**The Content-Security-Policy is strict because the build allows it.** The Vite
build emits external scripts and an external stylesheet with no inline `<script>`
and no inline `style`, which was verified before this policy was written rather
than assumed. If a future build inlines anything, the page breaks loudly in
development rather than silently weakening the policy - which is the right way
round.

TLS itself is terminated at the platform edge (D-045). This module only tells the
browser what to do about it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        # The interface talks to this origin only. There is no third-party
        # analytics, and a policy that permits one invites adding one.
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
    ]
)

# One year. No `preload`: submitting to the preload list is effectively
# irreversible, and this host is a demo deployment that may move.
STRICT_TRANSPORT_SECURITY = "max-age=31536000; includeSubDomains"

BASE_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # We ask for none of these. Saying so stops an embedded frame asking either.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
}

Handler = Callable[[Request], Awaitable[Response]]


def _is_https(request: Request) -> bool:
    """Whether the browser reached us over TLS.

    Behind a proxy the connection to this process is plain HTTP, so the original
    scheme arrives in `X-Forwarded-Proto`. Uvicorn populates `request.url.scheme`
    from it **only when started with `--proxy-headers`**, which is why the
    container command sets that flag.
    """
    forwarded = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded.split(",")[0].strip() == "https"


def add_security_headers(app: FastAPI) -> None:
    """Attach the standard security headers to every response."""

    @app.middleware("http")
    async def _secured(request: Request, call_next: Handler) -> Response:
        response = await call_next(request)

        for header, value in BASE_HEADERS.items():
            response.headers.setdefault(header, value)

        # Only over TLS. Sent on a plain-HTTP local dev server it would pin
        # localhost to HTTPS in the developer's browser and break the dev server
        # in a way that is genuinely painful to undo.
        if _is_https(request):
            response.headers.setdefault("Strict-Transport-Security", STRICT_TRANSPORT_SECURITY)

        return response
