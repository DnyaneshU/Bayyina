"""The market routes: looking a figure up, and answering from one.

The point of `/evaluate` accepting a dwelling is that **the caller stops having
to know the market average**. Until now the web checker asked a resident to type
a figure it then applied exactly, and disclosed that it had not checked it. Now
we derive it, and the answer stops being conditional.

What must not change is the refusal. Deriving a figure ourselves is not a licence
to derive a weak one, so every path that cannot produce a number it can stand
behind still declines — and declines with an outcome, not an error.
"""

from __future__ import annotations

import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from bayyina.api.app import create_app
from bayyina.market.aggregate import aggregate
from bayyina.market.ingest import ingest
from bayyina.settings import Settings

from ..market.conftest import START, build_release, row

RENT = "rent_increase.dubai.decree_43_2013"
NOTICE = "notice_validity.dubai.law_26_2007_a14"

#: The synthetic release's contracts all start here, so it is the window end.
FRESH = START + timedelta(days=30)


def contracts(
    count: int,
    *,
    prefix: str,
    rent: float,
    area: str,
    area_id: int,
    sub_type: str = "2 bed rooms+hall",
    property_type: str = "Flat",
) -> list[tuple]:
    return [
        row(
            f"CRT_{prefix}_{i}",
            rent=rent + i * 1_000,
            area=area,
            area_id=area_id,
            sub_type=sub_type,
            property_type=property_type,
        )
        for i in range(count)
    ]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """A service with real market data behind it.

    Al Barsha First is thick (200 contracts, median AED 159,500), Marsa Dubai is
    thin (4), and Hatta is known but has no flats.
    """
    workspace = tmp_path_factory.mktemp("market_api")
    release = build_release(
        workspace / "release.parquet",
        contracts(200, prefix="BARSHA", rent=60_000, area="Al Barsha First", area_id=368)
        + contracts(4, prefix="MARINA", rent=120_000, area="Marsa Dubai", area_id=999)
        + contracts(
            40,
            prefix="HATTA",
            rent=90_000,
            area="Hatta",
            area_id=555,
            property_type="Villa",
            sub_type="3 bed rooms+hall",
        ),
    )
    database = workspace / "market.duckdb"
    ingest(release, database, snapshot_id="snap_test")
    aggregate(database, "snap_test")

    settings = Settings(
        public_rate_limit_per_minute=10_000,
        # The synthetic release is dated in the past relative to whenever the
        # tests run, so on any machine it would read as both ageing and stale.
        # Both thresholds are lifted here so these tests assert what they are
        # about; recency has its own tests below and in tests/market/.
        market_snapshot_fresh_days=100_000,
        market_snapshot_max_age_days=100_000,
    )
    return TestClient(
        create_app(
            audit_path=workspace / "audit.jsonl",
            market_db=database,
            settings=settings,
        )
    )


# --- GET /comparables ---------------------------------------------------------


def test_a_thick_cell_returns_a_figure(client):
    body = client.get(
        "/comparables", params={"area": "Al Barsha First", "kind": "flat", "bedrooms": 2}
    ).json()

    assert body["status"] == "ok"
    assert body["contract_count"] == 200
    assert float(body["median_annual_rent"]) == 159_500
    assert body["full_confidence"] is True
    assert body["area_name"] == "Al Barsha First"


def test_a_refusal_is_an_answer_not_an_error(client):
    """**Always 200.**

    `insufficient_data`, `stale` and `unknown_area` are each a thing the agent
    has to say out loud. Returning them as 4xx would teach every client to treat
    our honesty as a fault and retry it.
    """
    for params, expected in [
        ({"area": "Marsa Dubai", "kind": "flat", "bedrooms": 2}, "insufficient_data"),
        ({"area": "Narnia", "kind": "flat", "bedrooms": 2}, "unknown_area"),
        ({"area": "Hatta", "kind": "flat", "bedrooms": 2}, "insufficient_data"),
    ]:
        response = client.get("/comparables", params=params)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == expected
        assert response.json()["median_annual_rent"] is None


def test_a_residents_spelling_reaches_dlds(client):
    body = client.get(
        "/comparables", params={"area": "al  barsha   first", "kind": "flat", "bedrooms": 2}
    ).json()
    assert body["status"] == "ok"


def test_an_unknown_kind_is_refused_at_the_boundary(client):
    """`kind` is a closed set. A typo must not silently become "no data here"."""
    response = client.get(
        "/comparables", params={"area": "Al Barsha First", "kind": "castle", "bedrooms": 2}
    )
    assert response.status_code == 422


# --- POST /evaluate with a dwelling -------------------------------------------


def test_the_caller_no_longer_has_to_know_the_market_average(client):
    """The whole point of T2.3.

    With a figure of our own the answer stops being conditional: the outcome is
    CLEAR rather than CLEAR_WITH_CONDITIONS, and `market_average_not_derived`
    disappears because it is no longer true.
    """
    response = client.post(
        "/evaluate",
        json={
            "rule_id": RENT,
            "inputs": {"current_annual_rent": "150000", "proposed_annual_rent": "155000"},
            "input_sources": {
                "current_annual_rent": "caller_stated",
                "proposed_annual_rent": "caller_stated",
            },
            "dwelling": {"area": "Al Barsha First", "kind": "flat", "bedrooms": 2},
        },
    )
    assert response.status_code == 200, response.text
    record = response.json()

    assert record["state"] == "CLEAR"
    assert record["conditions"] == []
    assert record["confidence"] == 1.0
    assert record["inputs"]["market_average_rent"] == "159500.00"


def test_a_figure_of_ours_is_recorded_as_ours(client):
    """G9 is per-field, and this is the field where it matters most.

    `caller_stated` and `dld_open_rent_contracts_derived` carry completely
    different weight on an evidence pack, and the difference has to survive to
    the audit log.
    """
    record = client.post(
        "/evaluate",
        json={
            "rule_id": RENT,
            "inputs": {"current_annual_rent": "150000", "proposed_annual_rent": "155000"},
            "input_sources": {
                "current_annual_rent": "caller_stated",
                "proposed_annual_rent": "caller_stated",
            },
            "dwelling": {"area": "Al Barsha First", "kind": "flat", "bedrooms": 2},
        },
    ).json()

    assert record["input_sources"]["market_average_rent"] == "dld_open_rent_contracts_derived"
    assert record["input_sources"]["current_annual_rent"] == "caller_stated"
    assert record["input_sources"]["market_snapshot"] == "snap_test"
    assert record["evidence"]["contract_count"] == 200


def test_a_thin_area_declines_rather_than_derives_a_weak_figure(client):
    """Deriving our own figure is not a licence to derive a bad one.

    Four contracts is below the floor, so the rule is never run: the record
    carries no verdict, no computed figures and no confidence, and there is
    therefore no number anywhere for a later step to decide to speak.
    """
    record = client.post(
        "/evaluate",
        json={
            "rule_id": RENT,
            "inputs": {"current_annual_rent": "120000", "proposed_annual_rent": "150000"},
            "input_sources": {
                "current_annual_rent": "caller_stated",
                "proposed_annual_rent": "caller_stated",
            },
            "dwelling": {"area": "Marsa Dubai", "kind": "flat", "bedrooms": 2},
        },
    ).json()

    assert record["state"] == "HUMAN_REVIEW_REQUIRED"
    assert record["verdict"] is None
    assert record["computed"] == {}
    assert record["confidence"] is None
    assert "market_average_rent" not in record["inputs"]


def test_an_unknown_area_declines_too(client):
    record = client.post(
        "/evaluate",
        json={
            "rule_id": RENT,
            "inputs": {"current_annual_rent": "120000", "proposed_annual_rent": "150000"},
            "input_sources": {
                "current_annual_rent": "caller_stated",
                "proposed_annual_rent": "caller_stated",
            },
            "dwelling": {"area": "Narnia", "kind": "flat", "bedrooms": 2},
        },
    ).json()
    assert record["state"] == "HUMAN_REVIEW_REQUIRED"
    assert record["verdict"] is None


def test_supplying_both_a_figure_and_a_dwelling_is_refused(client):
    """With both, nobody could tell which number the answer used - including us,
    reading the audit log a month later."""
    response = client.post(
        "/evaluate",
        json={
            "rule_id": RENT,
            "inputs": {
                "current_annual_rent": "150000",
                "proposed_annual_rent": "155000",
                "market_average_rent": "87000",
            },
            "input_sources": {
                "current_annual_rent": "caller_stated",
                "proposed_annual_rent": "caller_stated",
                "market_average_rent": "user_supplied",
            },
            "dwelling": {"area": "Al Barsha First", "kind": "flat", "bedrooms": 2},
        },
    )
    assert response.status_code == 422
    assert "not both" in response.json()["detail"]


def test_the_caller_supplied_path_still_works_unchanged(client):
    """T1.8's behaviour is not regressed by T2.3 existing.

    Someone who already knows their area's average, or whose area we have no
    data for, must still be able to get an answer they can act on.
    """
    record = client.post(
        "/evaluate",
        json={
            "rule_id": RENT,
            "inputs": {
                "current_annual_rent": "80000",
                "proposed_annual_rent": "96000",
                "market_average_rent": "87000",
            },
            "input_sources": {
                "current_annual_rent": "caller_stated",
                "proposed_annual_rent": "caller_stated",
                "market_average_rent": "user_supplied",
            },
            "market": {"snapshot_id": "user_supplied"},
        },
    ).json()

    assert record["state"] == "CLEAR_WITH_CONDITIONS"
    assert record["conditions"] == ["market_average_not_derived"]


def test_a_rule_needing_no_market_data_is_untouched(client):
    """The notice rule rests only on the caller's own dates, so no amount of
    thin market data can weaken it. This is what makes the thin-data path
    degrade gracefully rather than fail."""
    record = client.post(
        "/evaluate",
        json={
            "rule_id": NOTICE,
            "inputs": {"contract_expiry": "2026-11-30", "notice_served": "2026-09-20"},
            "input_sources": {
                "contract_expiry": "caller_stated",
                "notice_served": "caller_stated",
            },
        },
    ).json()
    assert record["state"] == "CLEAR"
    assert record["verdict"] is not None


# --- Health and degradation ---------------------------------------------------


def test_healthz_reports_loaded_market_data(client):
    body = client.get("/healthz").json()
    assert body["checks"]["market_data_loaded"] is True
    assert body["checks"]["market_data_usable"] is True
    assert body["status"] == "ok"
    assert body["market_data_age_days"] is not None


def test_ageing_data_is_not_reported_as_a_fault(tmp_path_factory):
    """Ageing is a working state, not degradation.

    Making freshness pass/fail would report `degraded` for eight months of every
    publication cycle, and a service that is always degraded is one nobody looks
    at the health of. The age is reported as a fact; the answers disclose it.
    """
    client = _ageing_client(tmp_path_factory, fresh_days=1, max_age_days=100_000)
    body = client.get("/healthz").json()

    assert body["status"] == "ok"
    assert body["checks"]["market_data_usable"] is True
    assert body["market_data_age_days"] > 1, "the age is still reported"


def test_data_past_the_limit_is_reported_as_a_fault(tmp_path_factory):
    """Past `max_age` nothing can be answered from it, and that is degradation."""
    client = _ageing_client(tmp_path_factory, fresh_days=1, max_age_days=2)
    body = client.get("/healthz").json()

    assert body["status"] == "degraded"
    assert body["checks"]["market_data_usable"] is False


def test_without_market_data_the_derived_path_says_so_and_the_rest_works(tmp_path):
    """Optional at boot, and honest about it.

    A missing dataset must not take down the notice rule or the caller-supplied
    path, and asking for a derived figure must not produce a 500 that reads like
    a crash.
    """
    bare = TestClient(
        create_app(
            audit_path=tmp_path / "audit.jsonl",
            market_db=tmp_path / "absent.duckdb",
            settings=Settings(public_rate_limit_per_minute=10_000),
        )
    )

    response = bare.get(
        "/comparables", params={"area": "Al Barsha First", "kind": "flat", "bedrooms": 2}
    )
    assert response.status_code == 503
    assert "ingest_market" in response.json()["detail"]

    still_works = bare.post(
        "/evaluate",
        json={
            "rule_id": NOTICE,
            "inputs": {"contract_expiry": "2026-11-30", "notice_served": "2026-09-20"},
            "input_sources": {
                "contract_expiry": "caller_stated",
                "notice_served": "caller_stated",
            },
        },
    )
    assert still_works.status_code == 200


# --- Latency ------------------------------------------------------------------


def test_deriving_a_figure_stays_inside_the_webhook_budget(client):
    """**< 150 ms p95**, and the derived path must not have spent it.

    Voice latency is 20% of the Stage 2 score and this webhook is one of five
    things between a caller finishing a sentence and hearing a reply. The
    comparables table is read at boot, so a lookup should cost microseconds — if
    this ever approaches the budget, something has put I/O back on the path.
    """
    body = {
        "rule_id": RENT,
        "inputs": {"current_annual_rent": "150000", "proposed_annual_rent": "155000"},
        "input_sources": {
            "current_annual_rent": "caller_stated",
            "proposed_annual_rent": "caller_stated",
        },
        "dwelling": {"area": "Al Barsha First", "kind": "flat", "bedrooms": 2},
    }
    for _ in range(5):
        client.post("/evaluate", json=body)

    timings = []
    for _ in range(50):
        started = time.perf_counter()
        response = client.post("/evaluate", json=body)
        timings.append((time.perf_counter() - started) * 1000)
        assert response.status_code == 200

    timings.sort()
    p95 = timings[47]
    assert p95 < 150.0, f"p95 is {p95:.1f} ms, over the 150 ms webhook budget"


def test_the_lookup_route_reports_its_own_timing(client):
    """Every route carries `x-response-ms`, so the budget is measurable in
    production rather than only in a test."""
    response = client.get(
        "/comparables", params={"area": "Al Barsha First", "kind": "flat", "bedrooms": 2}
    )
    assert float(response.headers["x-response-ms"]) < 150.0


# --- Recency, disclosed rather than refused -----------------------------------


def _ageing_client(tmp_path_factory, fresh_days: int, max_age_days: int) -> TestClient:
    """A service whose freshness thresholds make the fixture data ageing."""
    workspace = tmp_path_factory.mktemp("ageing")
    release = build_release(
        workspace / "release.parquet",
        contracts(200, prefix="BARSHA", rent=60_000, area="Al Barsha First", area_id=368),
    )
    database = workspace / "market.duckdb"
    ingest(release, database, snapshot_id="snap_test")
    aggregate(database, "snap_test")
    return TestClient(
        create_app(
            audit_path=workspace / "audit.jsonl",
            market_db=database,
            settings=Settings(
                public_rate_limit_per_minute=10_000,
                market_snapshot_fresh_days=fresh_days,
                market_snapshot_max_age_days=max_age_days,
            ),
        )
    )


DERIVED = {
    "rule_id": RENT,
    "inputs": {"current_annual_rent": "150000", "proposed_annual_rent": "155000"},
    "input_sources": {
        "current_annual_rent": "caller_stated",
        "proposed_annual_rent": "caller_stated",
    },
    "dwelling": {"area": "Al Barsha First", "kind": "flat", "bedrooms": 2},
}


def test_ageing_data_still_answers_but_says_how_old_it_is(tmp_path_factory):
    """**The middle band, and the reason the product works at all right now.**

    Our release is 193 days old. Under a single threshold that is either a
    refusal — every rent question returns HUMAN_REVIEW_REQUIRED — or a silent
    lie. Neither is acceptable, so the answer is given *and* the age is named.

    Measured: a cell drifts 4.3% at six months against rule bands five
    percentage points wide. Worth quoting, not worth quoting silently.
    """
    client = _ageing_client(tmp_path_factory, fresh_days=1, max_age_days=100_000)
    record = client.post("/evaluate", json=DERIVED).json()

    assert record["state"] == "CLEAR_WITH_CONDITIONS"
    assert "market_data_ageing" in record["conditions"]
    assert record["verdict"] is not None, "an ageing figure still produces an answer"
    assert record["evidence"]["age_days"] > 0


def test_data_past_the_limit_produces_no_answer_at_all(tmp_path_factory):
    """Past a year the median cell has moved more than a whole band, so the
    figure no longer describes the market and there is nothing to disclose."""
    client = _ageing_client(tmp_path_factory, fresh_days=1, max_age_days=2)
    record = client.post("/evaluate", json=DERIVED).json()

    assert record["state"] == "HUMAN_REVIEW_REQUIRED"
    assert record["verdict"] is None
    assert record["conditions"] == []


def test_fresh_data_carries_no_apology(tmp_path_factory):
    """A condition on every answer is a condition nobody reads."""
    client = _ageing_client(tmp_path_factory, fresh_days=100_000, max_age_days=100_000)
    record = client.post("/evaluate", json=DERIVED).json()

    assert record["state"] == "CLEAR"
    assert record["conditions"] == []


def test_thin_and_ageing_data_owes_the_listener_both_facts(tmp_path_factory):
    """Depth and recency are independent, and either can weaken an answer.

    Ranking them — reporting only the worse one — would let a caller act on a
    figure believing they had heard everything wrong with it.
    """
    workspace = tmp_path_factory.mktemp("thin_ageing")
    release = build_release(
        workspace / "release.parquet",
        contracts(15, prefix="THIN", rent=60_000, area="Al Barsha First", area_id=368),
    )
    database = workspace / "market.duckdb"
    ingest(release, database, snapshot_id="snap_test")
    aggregate(database, "snap_test")
    client = TestClient(
        create_app(
            audit_path=workspace / "audit.jsonl",
            market_db=database,
            settings=Settings(
                public_rate_limit_per_minute=10_000,
                market_snapshot_fresh_days=1,
                market_snapshot_max_age_days=100_000,
            ),
        )
    )

    record = client.post("/evaluate", json=DERIVED).json()
    assert set(record["conditions"]) == {"thin_comparable_data", "market_data_ageing"}
    assert record["confidence"] == 0.5, "15 of 30 comparables"


# --- GET /areas ---------------------------------------------------------------


def test_the_areas_we_know_can_be_listed(client):
    """`unknown_area` without this is a dead end.

    The agent has just told someone we do not know where they live, and has
    nothing to offer next. 184 names is small enough to return whole and small
    enough for an agent to match a spoken place against.
    """
    body = client.get("/areas").json()

    assert body["count"] == len(body["areas"]) == 3
    assert body["areas"] == ["Al Barsha First", "Hatta", "Marsa Dubai"]
    assert body["snapshot_id"] == "snap_test"


def test_areas_are_listed_by_the_name_a_person_would_say(client):
    """Display names, not keys. Nobody says 'al barshaa south third' out loud."""
    assert all(name[0].isupper() for name in client.get("/areas").json()["areas"])


def test_every_listed_area_can_actually_be_looked_up(client):
    """A list that includes a name `/comparables` then cannot resolve would be
    worse than no list — it would send the agent round a loop."""
    for name in client.get("/areas").json()["areas"]:
        found = client.get(
            "/comparables", params={"area": name, "kind": "flat", "bedrooms": 2}
        ).json()
        assert found["status"] != "unknown_area", f"we list {name} but cannot resolve it"


def test_listing_areas_without_market_data_says_how_to_build_it(tmp_path):
    bare = TestClient(
        create_app(
            audit_path=tmp_path / "audit.jsonl",
            market_db=tmp_path / "absent.duckdb",
            settings=Settings(public_rate_limit_per_minute=10_000),
        )
    )
    response = bare.get("/areas")
    assert response.status_code == 503
    assert "ingest_market" in response.json()["detail"]


# --- The boundary -------------------------------------------------------------


@pytest.mark.parametrize("area", ["   ", "!!!", "-", "  ,  "])
def test_something_that_is_not_a_place_name_is_a_bad_request(client, area):
    """`'   '` and `'!!!'` both pass `min_length=1` and normalise to the empty
    key, which came back as `unknown_area` — technically true and useless.

    "We don't know that area" implies we looked. A caller who sent punctuation
    made a mistake we can name, and the message points at `/areas`.
    """
    response = client.get("/comparables", params={"area": area, "kind": "flat", "bedrooms": 2})
    assert response.status_code == 422
    assert "/areas" in response.json()["detail"]


def test_a_real_place_we_do_not_know_is_still_an_answer(client):
    """The distinction being drawn: 'Narnia' is a place name we cannot resolve,
    which is an outcome. Punctuation is a malformed request."""
    response = client.get("/comparables", params={"area": "Narnia", "kind": "flat", "bedrooms": 2})
    assert response.status_code == 200
    assert response.json()["status"] == "unknown_area"


def test_evaluate_refuses_an_unresolvable_dwelling_too(client):
    """The same boundary on both routes, or the agent learns one of them lies."""
    response = client.post(
        "/evaluate",
        json={**DERIVED, "dwelling": {"area": "!!!", "kind": "flat", "bedrooms": 2}},
    )
    assert response.status_code == 422
