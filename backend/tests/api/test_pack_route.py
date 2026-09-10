"""`/evidence-pack`: the document, over HTTP.

The security property under test is narrow and total: **there is no request
shape that lets a caller choose what the document says.** Everything else here
is about not handing someone a document they cannot read.
"""

import pytest
from fastapi.testclient import TestClient

from bayyina.api.app import create_app
from bayyina.settings import Settings

RENT = "rent_increase.dubai.decree_43_2013"
NOTICE = "notice_validity.dubai.law_26_2007_a14"

BODY = {
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
    "caller_ref": "BYN-4821",
    "language": "en",
}


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    return TestClient(
        create_app(
            audit_path=tmp_path_factory.mktemp("audit") / "audit.jsonl",
            market_db=tmp_path_factory.mktemp("market") / "absent.duckdb",
            settings=Settings(public_rate_limit_per_minute=10_000),
        )
    )


# --- The document -------------------------------------------------------------


def test_it_returns_a_readable_document(client: TestClient):
    response = client.post("/evidence-pack", json=BODY)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "THAT INCREASE IS ABOVE THE PUBLISHED LIMIT." in response.text


def test_the_document_carries_the_required_disclosures(client: TestClient):
    """Not one of these is optional, and none is paraphrasable."""
    text = client.post("/evidence-pack", json=BODY).text.lower()

    assert "not legal advice" in text
    assert "not an official determination" in text
    assert "as stated by the caller" in text
    assert "pending review by a qualified lawyer" in text


def test_the_document_quotes_the_clause_and_names_the_signature(client: TestClient):
    text = client.post("/evidence-pack", json=BODY).text

    assert "Article 1" in text
    assert "sha256:" in text
    assert "average rental value of similar units" in text


def test_it_downloads_rather_than_rendering_in_the_tab(client: TestClient):
    response = client.post("/evidence-pack", json=BODY)

    assert (
        'attachment; filename="bayyina-BYN-4821.txt"' in (response.headers["content-disposition"])
    )


def test_a_pack_is_never_cached(client: TestClient):
    """A stale copy served after a rule is re-signed would cite a version we no
    longer run."""
    assert client.post("/evidence-pack", json=BODY).headers["cache-control"] == "no-store"


# --- G10 at the network edge --------------------------------------------------


def test_a_caller_cannot_post_a_verdict(client: TestClient):
    """The point of the endpoint taking inputs rather than a record.

    A record posted over HTTP would arrive already looking like one - a verdict
    nobody computed, carrying our citation, our signature and our name. The
    request model forbids the extra field outright.
    """
    forged = {
        **BODY,
        "state": "CLEAR",
        "verdict": "permitted",
        "computed": {"max_lawful_rent": "999999"},
    }
    response = client.post("/evidence-pack", json=forged)
    assert response.status_code == 422


def test_the_verdict_comes_from_the_evaluator_not_the_request(client: TestClient):
    """The same inputs always produce the same document.

    96,000 against a market average of 87,000 is above the limit, and no field a
    caller can set changes that sentence.
    """
    text = client.post("/evidence-pack", json=BODY).text
    assert "ABOVE THE PUBLISHED LIMIT" in text

    permitted = {
        **BODY,
        "inputs": {**BODY["inputs"], "proposed_annual_rent": "80000"},
    }
    assert "WITHIN THE PUBLISHED LIMIT" in client.post("/evidence-pack", json=permitted).text


def test_the_filename_cannot_carry_a_path(client: TestClient):
    """`caller_ref` reaches us from a voice agent and lands in a header."""
    response = client.post("/evidence-pack", json={**BODY, "caller_ref": '../../etc/passwd"; x'})

    disposition = response.headers["content-disposition"]
    assert ".." not in disposition
    assert "/" not in disposition.split("filename=")[1]
    assert '"; x' not in disposition.replace('filename="', "")


def test_every_pack_is_written_to_the_audit_log(client: TestClient, tmp_path):
    """G9. A document a person acted on that the log never saw is the gap the
    log exists to close."""
    before = client.app.state.audit.path.read_text(encoding="utf-8").count("\n")
    client.post("/evidence-pack", json=BODY)
    after = client.app.state.audit.path.read_text(encoding="utf-8").count("\n")

    assert after == before + 1


# --- Language -----------------------------------------------------------------


def test_it_lists_only_languages_it_can_actually_render(client: TestClient):
    body = client.get("/evidence-pack/languages").json()
    assert body["languages"] == ["en"]


def test_an_untranslated_language_is_refused_not_silently_englished(client: TestClient):
    """An English pack for a Malayalam caller is a failed delivery.

    A silent fallback is how that happens without anyone noticing: the call
    completes, the pack sends, and the person cannot read the thing they were
    told to take to the Rental Dispute Centre.
    """
    response = client.post("/evidence-pack", json={**BODY, "language": "ml"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "ml" in detail
    assert "en" in detail, "the refusal must say what we do have"


def test_the_refusal_names_no_language_we_cannot_render(client: TestClient):
    """The guard on the guard.

    If `supported_languages()` ever returned a language with no template, this
    endpoint would advertise it and then fail on use. The listing and the
    refusal read the same source, and this asserts they agree.
    """
    advertised = client.get("/evidence-pack/languages").json()["languages"]
    for language in advertised:
        assert client.post("/evidence-pack", json={**BODY, "language": language}).status_code == 200


# --- The honest outcome -------------------------------------------------------


def test_human_review_still_produces_a_document(client: TestClient):
    """Not a consolation prize.

    It is the document naming which facts were missing and which rule would have
    applied - the one a person takes to the Rental Dispute Centre when we could
    not answer. Refusing to produce it would leave them with nothing exactly
    when they need something.
    """
    thin = {
        **BODY,
        "input_sources": {
            **BODY["input_sources"],
            "market_average_rent": "dld_open_rent_contracts_derived",
        },
        "market": {"contract_count": 0, "snapshot_id": "2026-Q3"},
    }
    response = client.post("/evidence-pack", json=thin)

    assert response.status_code == 200, "an honest outcome is not an error"
    assert "THIS NEEDS A PERSON TO LOOK AT IT." in response.text
    assert "not an error" in response.text


def test_the_notice_rule_produces_a_pack_too(client: TestClient):
    response = client.post(
        "/evidence-pack",
        json={
            "rule_id": NOTICE,
            "inputs": {"contract_expiry": "2026-12-31", "notice_served": "2026-11-01"},
            "input_sources": {
                "contract_expiry": "caller_stated",
                "notice_served": "caller_stated",
            },
            "caller_ref": "BYN-9001",
            "language": "en",
        },
    )

    assert response.status_code == 200
    assert "NOT VALID" in response.text
    assert "Article 14" in response.text


def test_a_pack_without_market_data_still_works(client: TestClient):
    """The comparables database is absent in this fixture, as it is in CI.

    A caller-supplied figure needs no market data, and the pack must not be
    blocked by a dataset the request never touches (D-074).
    """
    assert client.post("/evidence-pack", json=BODY).status_code == 200
