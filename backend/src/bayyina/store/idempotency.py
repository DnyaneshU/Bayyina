"""Replay a result rather than repeat an action.

**A voice agent retries.** The network stalls, the tool call times out, the
platform sends it again — and the second attempt must not send a second text
message about someone's tenancy or arm the same deadline twice. The caller
experiences one action because there was one action, not because everything
happened to work.

The key is chosen by the caller and passed as `Idempotency-Key`. Two properties
make it safe:

**A repeated key returns the stored response.** Not a fresh one that happens to
look the same — the bytes the caller was given the first time, so a document
quoted in a hearing is the document we produced.

**A repeated key with a different request is refused, 409.** This is the half
that is easy to leave out and it is the one that matters. Without it, a client
that reuses a key by mistake — a constant, a poorly seeded generator, a copied
line of code — receives *someone else's document*. The stored fingerprint makes
that a loud error instead of a data leak.
"""

from __future__ import annotations

import hashlib

from .db import Store


class IdempotencyConflictError(RuntimeError):
    """The same key was used for a different request."""


def fingerprint(payload: bytes | str) -> str:
    """A stable digest of what was asked for.

    The request body, hashed. Comparing bodies directly would store a copy of
    everything anyone ever asked, including their rent and their address, in a
    table whose purpose is deduplication.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


class Idempotency:
    def __init__(self, store: Store) -> None:
        self._store = store

    def stored(self, key: str, *, operation: str, request: bytes | str) -> str | None:
        """The earlier response for this key, or None if it is new.

        Raises `IdempotencyConflictError` when the key was used for a different
        request, which is a client bug that must not be answered with somebody
        else's data.
        """
        row = self._store.execute(
            "select operation, request_fingerprint, response from idempotency where key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None

        if row["operation"] != operation:
            raise IdempotencyConflictError(
                f"idempotency key {key!r} was used for {row['operation']!r} and is "
                f"now being used for {operation!r}"
            )
        if row["request_fingerprint"] != fingerprint(request):
            raise IdempotencyConflictError(
                f"idempotency key {key!r} was used for a different request. "
                f"Returning the earlier response would hand this caller somebody "
                f"else's document."
            )
        return row["response"]

    def remember(
        self,
        key: str,
        *,
        call_id: str,
        operation: str,
        request: bytes | str,
        response: str,
    ) -> None:
        """Record what this key produced.

        `insert or ignore`: two concurrent first attempts with the same key both
        act, and the loser's write is discarded rather than overwriting the
        response the winner already returned. Preventing the double action in
        that window needs a lock, not a table, and the window is the length of
        one request.
        """
        with self._store.transaction() as db:
            db.execute(
                """
                insert or ignore into idempotency
                    (key, call_id, operation, request_fingerprint, response)
                values (?, ?, ?, ?, ?)
                """,
                (key, call_id, operation, fingerprint(request), response),
            )
