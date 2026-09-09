"""Guardrail G9: evaluations are written once and the log can prove it.

The chain is what makes "auditable lineage" checkable rather than asserted. An
edited entry must be detectable, and the detection must name the entry.
"""

from decimal import Decimal

import pytest

from bayyina.audit import GENESIS, AuditChainError, AuditLog
from bayyina.registry.evaluator import Evaluator, MarketEvidence
from bayyina.settings import Settings

RENT = "rent_increase.dubai.decree_43_2013"
INPUTS = {
    "current_annual_rent": Decimal("80000"),
    "market_average_rent": Decimal("87000"),
    "proposed_annual_rent": Decimal("96000"),
}
SOURCES = {
    "current_annual_rent": "caller_stated",
    "market_average_rent": "dld_open_rent_contracts_derived",
    "proposed_annual_rent": "caller_stated",
}
MARKET = MarketEvidence(contract_count=5557, snapshot_id="2026-Q3")
THRESHOLDS = Settings(min_contracts_for_answer=10, min_contracts_for_full_confidence=30)


@pytest.fixture
def record(signed_rules):
    return Evaluator(signed_rules, settings=THRESHOLDS).evaluate(
        RENT, INPUTS, SOURCES, market=MARKET
    )


def test_an_empty_log_reads_as_empty(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    assert log.entries() == []
    assert log.verify_chain() == 0


def test_the_first_entry_chains_from_genesis(tmp_path, record):
    entry = AuditLog(tmp_path / "audit.jsonl").append(record)
    assert entry.seq == 1
    assert entry.prev == GENESIS


def test_entries_chain_to_the_one_before(tmp_path, record):
    log = AuditLog(tmp_path / "audit.jsonl")
    first = log.append(record)
    second = log.append(record)
    assert second.seq == 2
    assert second.prev == first.digest
    assert log.verify_chain() == 2


def test_the_record_is_preserved_verbatim(tmp_path, record):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.append(record)
    stored = log.entries()[0].record
    assert stored["eval_id"] == record.eval_id
    assert stored["citation"]["clause"] == "Article 1"
    assert stored["rule_signature"] == record.rule_signature


def test_a_reopened_log_continues_the_chain(tmp_path, record):
    """The tip is recovered from the file, not held only in memory."""
    path = tmp_path / "audit.jsonl"
    first = AuditLog(path).append(record)
    second = AuditLog(path).append(record)
    assert second.seq == 2
    assert second.prev == first.digest
    assert AuditLog(path).verify_chain() == 2


def test_an_edited_entry_is_detected(tmp_path, record):
    """Change one field of one line and the chain disagrees."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append(record)
    log.append(record)

    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"not_permitted"', '"permitted"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(AuditChainError, match="entry 1"):
        AuditLog(path).verify_chain()


def test_a_removed_entry_is_detected(tmp_path, record):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append(record)
    log.append(record)
    log.append(record)

    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")

    with pytest.raises(AuditChainError):
        AuditLog(path).verify_chain()


def test_the_log_has_no_way_to_change_an_entry(tmp_path):
    """Append-only is a property of the interface, not a promise in a comment."""
    log = AuditLog(tmp_path / "audit.jsonl")
    public = {name for name in dir(log) if not name.startswith("_")}
    assert public == {"append", "entries", "verify_chain", "path"}


def test_an_entry_cannot_be_edited_in_memory(tmp_path, record):
    from pydantic import ValidationError

    entry = AuditLog(tmp_path / "audit.jsonl").append(record)
    with pytest.raises(ValidationError):
        entry.seq = 99


# --- Concurrency -------------------------------------------------------------


def test_concurrent_appends_keep_the_chain_intact(tmp_path, record):
    """FastAPI runs handlers in a threadpool, so this is the real deployment shape.

    Reading the tip and writing the next entry must be atomic together. Without
    that, two threads chain from the same entry, both claim the same sequence
    number, and the log is broken from that point on.
    """
    import threading

    log = AuditLog(tmp_path / "audit.jsonl")
    errors: list[Exception] = []

    def writer() -> None:
        for _ in range(25):
            try:
                log.append(record)
            except Exception as exc:  # noqa: BLE001 - the test is what catches it
                errors.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert AuditLog(tmp_path / "audit.jsonl").verify_chain() == 100


def test_a_truncated_line_is_reported_as_a_chain_error(tmp_path, record):
    """A half-written line is a damaged log, not a schema problem."""
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append(record)
    path.write_text(path.read_text(encoding="utf-8")[:-40], encoding="utf-8")

    with pytest.raises(AuditChainError, match="line 1"):
        AuditLog(path).entries()
