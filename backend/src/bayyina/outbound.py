"""The only way to call anything outside this process.

**A webhook that hangs during a live call produces dead air.** httpx's default
timeout is five seconds; `TOOL_TIMEOUT_SECONDS` is three, because three seconds
of silence on a phone call is already long and five is a caller who has hung up.
The default is not a policy, it is the absence of one.

There are no outbound calls yet — SMS dispatch and the agent webhooks arrive in
Phase 3. This exists now for two reasons. The setting was declared and applied to
nothing, which is an advertised budget that is not enforced anywhere. And a
timeout added after the first outbound call is written is a timeout added after
the first outbound call has shipped without one.

A test asserts nothing else in the package constructs an httpx client, so the
next outbound call cannot quietly skip this.
"""

from __future__ import annotations

import httpx

from .settings import Settings, get_settings


def timeout(settings: Settings | None = None) -> httpx.Timeout:
    """The budget, as httpx expects it.

    The same value on every phase. A generous read with a tight connect would
    let a black-holed host consume the whole budget before a byte moved, and the
    caller hears the difference between the phases not at all — they hear
    silence either way.
    """
    settings = settings or get_settings()
    seconds = float(settings.tool_timeout_seconds)
    return httpx.Timeout(seconds, connect=seconds, read=seconds, write=seconds)


def client(settings: Settings | None = None, **kwargs) -> httpx.Client:
    """An HTTP client that cannot hang past the budget.

    `timeout` is set here and callers may not override it: a per-call override
    is how one endpoint ends up with a thirty-second budget nobody remembers
    agreeing to.
    """
    kwargs.pop("timeout", None)
    return httpx.Client(timeout=timeout(settings), **kwargs)


def async_client(settings: Settings | None = None, **kwargs) -> httpx.AsyncClient:
    """The async form, same budget."""
    kwargs.pop("timeout", None)
    return httpx.AsyncClient(timeout=timeout(settings), **kwargs)
