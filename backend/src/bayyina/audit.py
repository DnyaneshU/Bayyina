"""The evaluation audit log - guardrail G9.

Every evaluation is written once, as one JSON line, and never revisited. The
class exposes no method that updates or deletes an entry, because the guarantee
is meant to be a property of the code rather than a promise in a document.

Each entry carries the digest of the entry before it. That makes an edit or an
insertion detectable: re-running the chain from the beginning will disagree at
the first altered entry and name it. **A plain chain cannot detect truncation of
the tail** - removing the last entries leaves a shorter but internally consistent
log - so `verify_chain` is a check on integrity, not on completeness. Detecting
truncation needs an external witness, which is a pilot concern and not something
we claim today.

The canonical serialisation is the one the rule signer uses, so the two hashes in
this system are produced by the same rule about what the bytes are.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from bayyina.registry.evaluator import EvaluationRecord
from bayyina.registry.signing import DIGEST_PREFIX, canonical_bytes

# The digest a first entry chains from. A fixed, recognisable value, so that a
# log beginning anywhere else is obviously not the beginning of a log.
GENESIS = f"{DIGEST_PREFIX}{'0' * 64}"


class AuditChainError(RuntimeError):
    """The log does not hash to what it claims. An entry was edited or inserted."""


class AuditEntry(BaseModel):
    """One line of the log."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    seq: int
    prev: str
    digest: str
    record: dict[str, Any]


def _digest(seq: int, prev: str, record: dict[str, Any]) -> str:
    body = {"seq": seq, "prev": prev, "record": record}
    return f"{DIGEST_PREFIX}{hashlib.sha256(canonical_bytes(body)).hexdigest()}"


class AuditLog:
    """An append-only, hash-chained log of evaluation records.

    JSON Lines rather than one JSON document: a line is written whole or not at
    all, so a process killed mid-write cannot corrupt the entries already there.

    **One writer per file.** Reading the tip and appending the next entry must be
    atomic together, or two writers both chain from the same entry and the log
    breaks. A lock makes that safe across threads, which is what FastAPI's
    threadpool needs. It does **not** make it safe across processes: running
    several workers against one log file needs file locking or a single writer,
    and we deploy one container for exactly this kind of reason.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._tip: tuple[int, str] | None = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: EvaluationRecord) -> AuditEntry:
        """Write one record. The only way anything enters the log."""
        # mode="json" so that Decimal amounts and datetimes serialise to stable
        # text rather than to a repr that could differ between runs. Done outside
        # the lock: it depends on nothing shared.
        body = record.model_dump(mode="json")

        with self._lock:
            seq, prev = self._current_tip()
            seq += 1
            entry = AuditEntry(seq=seq, prev=prev, digest=_digest(seq, prev, body), record=body)

            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry.model_dump(), ensure_ascii=False) + "\n")

            self._tip = (entry.seq, entry.digest)

        return entry

    def entries(self) -> list[AuditEntry]:
        """Read the log back. Used by the officer dashboard and by tests."""
        if not self._path.exists():
            return []

        entries: list[AuditEntry] = []
        for number, line in enumerate(self._path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                entries.append(AuditEntry.model_validate_json(line))
            except ValidationError as exc:
                # A line that will not parse is a damaged log, which is the same
                # class of problem as a line that will not verify - so it is
                # reported the same way rather than as a schema error.
                raise AuditChainError(
                    f"line {number} of {self._path.name} is not a readable audit entry; "
                    f"the log was truncated mid-write or edited by hand. {exc.error_count()} "
                    f"problem(s)"
                ) from exc
        return entries

    def verify_chain(self) -> int:
        """Recompute the chain from the beginning. Returns the number of entries.

        Raises `AuditChainError` naming the first entry that disagrees, so that
        an operator can see exactly where the log stopped being trustworthy.
        """
        prev = GENESIS
        entries = self.entries()

        for index, entry in enumerate(entries, start=1):
            if entry.seq != index:
                raise AuditChainError(
                    f"entry {index} is numbered {entry.seq}; the log has a gap or a "
                    "duplicate, so an entry was removed or inserted"
                )
            if entry.prev != prev:
                raise AuditChainError(
                    f"entry {entry.seq} chains from {entry.prev} but the previous entry "
                    f"hashes to {prev}; an entry was inserted or reordered"
                )
            expected = _digest(entry.seq, entry.prev, entry.record)
            if entry.digest != expected:
                raise AuditChainError(
                    f"entry {entry.seq} hashes to {expected} but records {entry.digest}; "
                    "its contents were edited after it was written"
                )
            prev = entry.digest

        return len(entries)

    def _current_tip(self) -> tuple[int, str]:
        if self._tip is None:
            entries = self.entries()
            self._tip = (entries[-1].seq, entries[-1].digest) if entries else (0, GENESIS)
        return self._tip
