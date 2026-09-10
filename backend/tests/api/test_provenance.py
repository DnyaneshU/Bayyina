"""The provenance page is the answer to "why should I believe you?".

Its job is narrow and testable: show the source text, show our encoding of it,
show the signature over the bytes, and never quietly present any of the three as
something it is not.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bayyina.api.app import create_app
from bayyina.registry.explain import UnexplainableLogicError, explain, percent
from bayyina.registry.schema import RuleLogic
from bayyina.registry.signing import rule_digest
from bayyina.settings import Settings

RENT = "rent_increase.dubai.decree_43_2013"
NOTICE = "notice_validity.dubai.law_26_2007_a14"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    """The real corpus, as the deployed service loads it.

    A stub rule would let this file pass while the page a reviewer actually
    opens showed something else.
    """
    return create_app(
        audit_path=tmp_path_factory.mktemp("audit") / "audit.jsonl",
        market_db=tmp_path_factory.mktemp("market") / "absent.duckdb",
        settings=Settings(public_rate_limit_per_minute=10_000),
    )


@pytest.fixture(scope="module")
def client(app) -> TestClient:
    return TestClient(app)


# --- The listing --------------------------------------------------------------


def test_the_index_lists_every_rule_in_the_corpus(client: TestClient):
    response = client.get("/provenance")
    assert response.status_code == 200

    body = response.json()
    assert body["count"] == 2
    assert {rule["rule_id"] for rule in body["rules"]} == {RENT, NOTICE}


def test_the_index_discloses_that_nothing_is_certified_yet(client: TestClient):
    """`provisional` is the honest state and it must be visible without asking.

    A reader who sees a signature and an official-looking citation will assume a
    lawyer signed this off. Nobody has. The status says so on the first screen,
    not three clicks in.
    """
    body = client.get("/provenance").json()
    assert [rule["approval_status"] for rule in body["rules"]] == [
        "provisional",
        "provisional",
    ]


# --- One rule -----------------------------------------------------------------


def test_an_unknown_rule_is_404_and_says_what_does_exist(client: TestClient):
    """Not an empty page.

    A citation resolving to a blank document reads as "this rule exists and says
    nothing", which is the opposite of what an absent rule means.
    """
    response = client.get("/provenance/rent_increase.dubai.decree_99_2099")
    assert response.status_code == 404

    detail = response.json()["detail"]
    assert "no rule" in detail
    assert RENT in detail, "the 404 should name the rules that do exist"


def test_the_detail_carries_the_clause_verbatim(client: TestClient):
    """Never summarised.

    The comparison this page exists for is text against encoding, and a
    paraphrase makes that comparison worthless.
    """
    verbatim = client.get(f"/provenance/{RENT}").json()["verbatim"]

    assert "average rental value of similar units" in verbatim
    for quoted in ("10%", "11% to\n       20%", "20%", "30%", "40%"):
        assert quoted.split("\n")[0] in verbatim


def test_the_detail_shows_the_encoding_beside_the_source(client: TestClient):
    """Five bands in the decree, five steps in the encoding.

    This is the whole point of the page. A reviewer reads clause 2 - "5% where
    the rent is 11% to 20% less" - and finds a step beside it saying 5%.
    """
    encoded = client.get(f"/provenance/{RENT}").json()["encoded"]

    assert [step["step"] for step in encoded] == [1, 2, 3, 4, 5]
    assert "no increase is permitted" in encoded[0]["outcome"]
    assert "5%" in encoded[1]["outcome"]
    assert "10%" in encoded[2]["outcome"]
    assert "15%" in encoded[3]["outcome"]
    assert "20%" in encoded[4]["outcome"]


def test_the_detail_says_which_inputs_we_derive(client: TestClient):
    """`derived` is the first thing a reviewer asks about a figure.

    The market average is ours, computed from the open contracts dataset. It is
    not the RERA index, and the page must not let a reader assume it is.
    """
    inputs = client.get(f"/provenance/{RENT}").json()["inputs"]
    derived = {item["name"]: item["derived"] for item in inputs}

    assert derived["market_average_rent"] is True
    assert derived["current_annual_rent"] is False
    assert derived["proposed_annual_rent"] is False


def test_the_detail_publishes_the_review_notes(client: TestClient):
    """Where we interpreted an ambiguous text, in public.

    The decree states whole-percentage bands and leaves 10-11% undefined. We
    chose. Publishing that choice is the difference between provenance and
    marketing, and it is the most useful thing on the page for the reviewer this
    exists to serve.
    """
    notes = " ".join(client.get(f"/provenance/{RENT}").json()["review_notes"])

    assert "INTERPRETATION" in notes
    assert "TRANSLATION" in notes, "the unofficial translation must be disclosed"
    assert "RERA" in notes, "our figure must not be presented as the official index"


def test_the_detail_links_to_the_publisher(client: TestClient):
    citation = client.get(f"/provenance/{RENT}").json()["citation"]

    assert citation["clause"] == "Article 1"
    assert citation["url"].startswith("https://")
    assert "Decree No. (43) of 2013" in citation["title"]


# --- The signature ------------------------------------------------------------


def test_the_signature_is_recomputed_rather_than_echoed(client: TestClient, app):
    """Printing `approval.signature` from the file would attest to nothing.

    A tampered file carries a tampered signature block quite happily. The page
    reports the result of hashing the body *now*.
    """
    body = client.get(f"/provenance/{RENT}").json()

    assert body["signature_matches"] is True
    assert body["signature"] == rule_digest(app.state.rules[RENT])
    assert body["computed_signature"] is None, (
        "a matching signature should not also report a computed one"
    )


def test_a_tampered_body_is_reported_as_a_mismatch(client: TestClient, app):
    """The corpus is verified at boot and in CI, so this should be unreachable.

    It is tested anyway, because the one thing this page must never do is
    present a forgery as provenance. The loaded object is tampered with rather
    than the file: the loader refuses a bad file outright, which is a different
    guardrail with its own test.
    """
    rule = app.state.rules[RENT]
    original = rule.bands[0].max_increase
    try:
        rule.bands[0].max_increase = 0.99
        body = client.get(f"/provenance/{RENT}").json()

        assert body["signature_matches"] is False
        assert body["computed_signature"] is not None
        assert body["computed_signature"] != body["signature"], (
            "a mismatch must name what we actually computed"
        )
    finally:
        rule.bands[0].max_increase = original

    assert client.get(f"/provenance/{RENT}").json()["signature_matches"] is True


# --- The explainer ------------------------------------------------------------


def test_every_band_produces_a_step(signed_rules):
    """Generated from the table, not written beside it.

    A hand-written summary is a second copy of the law that drifts the first
    time someone edits one and not the other - silently, because nothing
    executes prose.
    """
    rule = signed_rules[RENT]
    assert len(explain(rule)) == len(rule.bands)


def test_each_step_states_its_own_bands_numbers(signed_rules):
    """The percentage in the sentence is the percentage in the table."""
    rule = signed_rules[RENT]

    for band, step in zip(rule.bands, explain(rule), strict=True):
        if band.max_increase == 0:
            assert "no increase" in step.outcome
        else:
            assert percent(band.max_increase) in step.outcome
        if band.gap_to is not None:
            assert percent(band.gap_to) in step.condition


def test_the_lower_bound_comes_from_the_previous_upper_bound(signed_rules):
    """The evaluator reads `gap_to` and never `gap_from`.

    The schema refuses a file where the two disagree, so they cannot drift - but
    the sentences are built from the bound that is actually enforced, so a page
    can never describe a boundary nothing applies.
    """
    steps = explain(signed_rules[RENT])

    # Band 1 ends at 0.10, so step 2 must open at "more than 10%".
    assert "more than 10%" in steps[1].condition
    # The unbounded final band opens at the previous band's upper bound.
    assert "more than 40%" in steps[-1].condition
    assert "up to" not in steps[-1].condition


def test_the_first_band_is_closed_at_the_bottom(signed_rules):
    """A rent at or above market has a gap of zero and matches step 1.

    Written as "up to 10%" rather than "more than 0% and up to 10%", because the
    latter reads as excluding exactly the case it includes.
    """
    first = explain(signed_rules[RENT])[0]
    assert "up to 10%" in first.condition
    assert "more than" not in first.condition


def test_the_inclusive_upper_bound_is_stated(signed_rules):
    """A gap of exactly 10% permits no increase, and that is not obvious.

    It is the single boundary a reviewer is most likely to read the other way,
    so the sentence says it rather than leaving it to be inferred.
    """
    assert "including exactly 10%" in explain(signed_rules[RENT])[0].condition


def test_the_notice_rule_states_its_required_days(signed_rules):
    steps = explain(signed_rules[NOTICE])

    assert len(steps) == 2
    assert "90 days" in steps[0].condition
    assert "fewer than 90 days" in steps[1].condition


def test_a_logic_with_no_description_refuses_rather_than_improvising(signed_rules):
    """A rule that cannot be stated in words cannot be reviewed.

    Falling back to a generic sentence would give a page that looks complete and
    says nothing about what actually runs.
    """
    rule = signed_rules[RENT].model_copy()
    object.__setattr__(rule, "logic", "an_unregistered_logic")

    with pytest.raises(UnexplainableLogicError, match="no description"):
        explain(rule)


def test_every_logic_the_registry_supports_has_a_writer():
    """The guard on the guard.

    The test above proves an *unknown* logic raises. This one proves no *known*
    logic is missing a writer, which is how the gap would actually appear:
    someone adds a logic kind, ships it, and the provenance page for every rule
    using it explodes in front of the reviewer it was built for.
    """
    from bayyina.registry.explain import _WRITERS

    missing = [logic.value for logic in RuleLogic if logic not in _WRITERS]
    assert not missing, f"these logic kinds have no provenance description: {missing}"


def test_the_page_is_reachable_without_market_data(client: TestClient):
    """Provenance does not depend on the comparables database.

    The market data is optional at boot (D-074) and absent in this fixture. A
    reviewer checking an encoding against a decree must not be blocked by a
    dataset that has nothing to do with the question.
    """
    assert client.get("/provenance").status_code == 200
    assert client.get(f"/provenance/{NOTICE}").status_code == 200


def test_the_static_root_does_not_swallow_the_api(tmp_path_factory):
    """A built frontend mounts at "/" and catches everything after it.

    The mount is added last for exactly this reason, and this is the test that
    says so: with static files present, /provenance must still be the API.
    """
    static = tmp_path_factory.mktemp("static")
    (static / "index.html").write_text("<html>Bayyina</html>", encoding="utf-8")

    served = TestClient(
        create_app(
            audit_path=tmp_path_factory.mktemp("audit2") / "audit.jsonl",
            market_db=tmp_path_factory.mktemp("market2") / "absent.duckdb",
            static_dir=static,
            settings=Settings(public_rate_limit_per_minute=10_000),
        )
    )

    assert served.get("/provenance").json()["count"] == 2
    assert Path(static / "index.html").exists()
