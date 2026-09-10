"""Fixtures for the case store."""

import pytest

from bayyina.registry.evaluator import Evaluator, MarketEvidence
from bayyina.store.db import Store, run_migrations

RENT = "rent_increase.dubai.decree_43_2013"


@pytest.fixture
def store(tmp_path):
    """A migrated store, one per test.

    A file rather than `:memory:`. WAL is the thing under test in one of these
    and an in-memory database silently declines to use it, so the fixture would
    quietly make that assertion meaningless.
    """
    store = Store(tmp_path / "cases.db")
    run_migrations(store.connection)
    yield store
    store.close()


@pytest.fixture
def record(signed_rules):
    """A real evaluation, not a stand-in.

    `Cases.create` takes a record for the same reason `build_pack` does — what
    opens a case is something we computed. A stub would let these tests pass
    against a shape the evaluator does not actually produce.
    """
    return Evaluator(signed_rules).evaluate(
        RENT,
        {
            "current_annual_rent": "80000",
            "proposed_annual_rent": "96000",
            "market_average_rent": "87000",
        },
        {
            "current_annual_rent": "caller_stated",
            "proposed_annual_rent": "caller_stated",
            "market_average_rent": "dld_open_rent_contracts_derived",
        },
        market=MarketEvidence(contract_count=5019, snapshot_id="2026-Q3", age_days=30),
    )
