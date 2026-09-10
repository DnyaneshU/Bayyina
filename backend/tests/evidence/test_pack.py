"""The evidence pack: what it must contain, and what must not be able to enter it.

**G10 — it states, it never argues.** The pack lays out what the rules engine
computed. It composes nothing, weighs nothing and recommends nothing, and the
difference between "your rent sits 5.9% below the market average" and "you have
a strong case" is the difference between information and legal advice.

That is enforced by the input type, and the tests below try to get around it the
way a future change plausibly would: with a string, with a dict shaped like a
record, with a model that merely looks similar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bayyina.evidence.pack import (
    EvidenceError,
    EvidencePack,
    UnsupportedLanguageError,
    build_pack,
    money,
    supported_languages,
    written_date,
)
from bayyina.registry.evaluator import Evaluator, MarketEvidence
from bayyina.registry.loader import load_rules

RULES = Path(__file__).resolve().parents[2] / "rules"
RENT = "rent_increase.dubai.decree_43_2013"
NOTICE = "notice_validity.dubai.law_26_2007_a14"


@pytest.fixture(scope="module")
def evaluator() -> Evaluator:
    return Evaluator(load_rules(RULES))


@pytest.fixture(scope="module")
def rent_eval(evaluator):
    """A rent answer resting on a market figure we derived."""
    return evaluator.evaluate(
        RENT,
        {
            "current_annual_rent": "80000",
            "proposed_annual_rent": "96000",
            "market_average_rent": "85000",
        },
        {
            "current_annual_rent": "caller_stated",
            "proposed_annual_rent": "caller_stated",
            "market_average_rent": "dld_open_rent_contracts_derived",
        },
        market=MarketEvidence(contract_count=5019, snapshot_id="snap_20260226", age_days=30),
    )


@pytest.fixture(scope="module")
def notice_eval(evaluator):
    """A notice answer, which rests on no market data at all."""
    return evaluator.evaluate(
        NOTICE,
        {"contract_expiry": "2026-11-30", "notice_served": "2026-09-20"},
        {"contract_expiry": "caller_stated", "notice_served": "caller_stated"},
    )


@pytest.fixture(scope="module")
def review_eval(evaluator):
    """An answer the rule was never allowed to compute."""
    return evaluator.evaluate(
        RENT,
        {"current_annual_rent": "80000", "proposed_annual_rent": "96000"},
        {"current_annual_rent": "caller_stated", "proposed_annual_rent": "caller_stated"},
        market=MarketEvidence(contract_count=0, snapshot_id="snap_20260226"),
    )


# --- G10: nothing written may enter the document path -------------------------


def test_generator_rejects_anything_but_evaluation_records():
    """The plan's test, and the reason this module has a type at its door."""
    with pytest.raises(TypeError):
        build_pack(["some free text"], caller_ref="x", language="en")


@pytest.mark.parametrize(
    "smuggled",
    [
        "a sentence someone wrote",
        b"bytes",
        {"rule_id": RENT, "verdict": "permitted"},
        [{"rule_id": RENT, "verdict": "permitted"}],
        [None],
        42,
    ],
    ids=["string", "bytes", "dict", "list-of-dicts", "none", "int"],
)
def test_nothing_that_merely_looks_like_a_verdict_gets_in(smuggled):
    """Every shape a composed answer plausibly arrives in.

    The dict cases matter most: pydantic would happily coerce a mapping into an
    `EvaluationRecord`, so a verdict assembled by hand — or by a model — would
    arrive indistinguishable from one the engine computed.
    """
    with pytest.raises((TypeError, EvidenceError)):
        build_pack(smuggled, caller_ref="x", language="en")


def test_the_model_refuses_a_smuggled_record_too(rent_eval):
    """`build_pack` is not the only door. Constructing the model directly must
    be no easier, or the guard is a convention rather than a guarantee."""
    with pytest.raises((TypeError, ValueError)):
        EvidencePack(
            caller_ref="x",
            language="en",
            records=({"rule_id": RENT, "verdict": "permitted"},),  # type: ignore[arg-type]
        )


def test_a_pack_with_no_findings_is_not_a_document():
    with pytest.raises(EvidenceError, match="no findings"):
        build_pack([], caller_ref="x", language="en")


def test_the_evidence_package_imports_no_language_model():
    """**The DoD, as a test rather than a grep somebody remembers to run.**

    Checked across the whole package's source, including templates: an LLM
    reachable from the document path would make every disclosure in the pack a
    claim we cannot support.
    """
    import bayyina.evidence as package

    banned = ("openai", "anthropic", "elevenlabs", "cohere", "litellm", "transformers")
    offenders: list[str] = []

    root = Path(package.__file__).parent
    for source in sorted(root.rglob("*")):
        if source.is_dir() or source.suffix not in {".py", ".j2", ".txt", ".html"}:
            continue
        text = source.read_text(encoding="utf-8").lower()
        for name in banned:
            if name in text:
                offenders.append(f"{source.relative_to(root)} mentions {name!r}")

    assert not offenders, "an LLM is reachable from the document path: " + "; ".join(offenders)


# --- What the pack must say ---------------------------------------------------


def test_pack_marks_caller_stated_facts_as_unverified(rent_eval):
    text = build_pack([rent_eval], "x", "en").render_text()
    assert "as stated by the caller" in text.lower()
    assert "not independently verified" in text.lower()


def test_pack_carries_rule_version_and_signature(rent_eval):
    pack = build_pack([rent_eval], "x", "en")
    assert pack.signatures[rent_eval.rule_id].startswith("sha256:")
    text = pack.render_text()
    assert rent_eval.rule_signature in text
    assert f"version {rent_eval.rule_version}" in text


def test_pack_states_it_is_not_official(rent_eval):
    assert (
        "not an official determination" in build_pack([rent_eval], "x", "en").render_text().lower()
    )


def test_pack_carries_every_standing_disclosure(rent_eval):
    """D1 to D7 from GLOSSARY section 3. These are not paraphrasable, and a pack
    missing one is a compliance problem rather than a formatting one."""
    # Whitespace-normalised. These are wrapped for print, so a line break can
    # fall inside "Dubai Land Department" — intact on the page, invisible to a
    # raw substring match.
    text = " ".join(build_pack([rent_eval], "x", "en").render_text().lower().split())
    for disclosure in (
        "generated by bayyina",  # D1, AI identity
        "not legal advice",  # D2
        "pending review by a qualified lawyer",  # D4, provisional
        "not an official determination",  # D5
        "as stated by the caller",  # D6
        "dubai land department",  # D7, data source
    ):
        assert disclosure in text, f"the pack does not carry {disclosure!r}"


def test_pack_quotes_the_clause_in_full(rent_eval):
    """A citation without the text is a reference someone has to go and find."""
    text = build_pack([rent_eval], "x", "en").render_text()
    assert rent_eval.citation.verbatim.strip().splitlines()[0].strip() in text
    assert rent_eval.citation.clause in text


def test_pack_leads_with_the_answer(rent_eval):
    """Answer first, reasoning second. Someone reading this in a queue gets the
    outcome before the workings."""
    lines = [
        line
        for line in build_pack([rent_eval], "x", "en").render_text().splitlines()
        if line.strip()
    ]
    verdict_at = next(i for i, line in enumerate(lines) if "PUBLISHED LIMIT" in line)
    workings_at = next(i for i, line in enumerate(lines) if "HOW WE GOT THERE" in line)
    assert verdict_at < workings_at


def test_a_review_pack_carries_no_figures_to_misread(review_eval):
    """G5 reaching the document. The rule was never run, so there is no verdict
    and no computed figure — and the pack must not invent a shape for one."""
    text = build_pack([review_eval], "x", "en").render_text()

    assert "NEEDS A PERSON" in text
    assert "HOW WE GOT THERE" not in text
    assert "not an official determination" in text.lower()
    assert "The rule applied".upper() in text, "the citation survives a non-answer"


def test_a_notice_pack_needs_no_market_data(notice_eval):
    """The notice rule rests only on the caller's dates, which is what makes it
    degrade gracefully when market data is thin."""
    text = build_pack([notice_eval], "x", "en").render_text()
    assert "THE MARKET FIGURE" not in text
    assert "Days short" in text


def test_a_pack_can_carry_more_than_one_finding(rent_eval, notice_eval):
    """A caller usually has both questions, and both belong on one document."""
    pack = build_pack([rent_eval, notice_eval], "x", "en")
    text = pack.render_text()

    assert len(pack.signatures) == 2
    assert rent_eval.citation.clause in text
    assert notice_eval.citation.clause in text


# --- Language -----------------------------------------------------------------


def test_supported_languages_are_derived_from_the_templates():
    """Derived, never listed — the same shape as the interface's switcher.
    A language becomes supported when a translated template appears."""
    assert "en" in supported_languages()


def test_a_language_we_cannot_render_is_refused_rather_than_faked(rent_eval):
    """**No English fallback.**

    The plan is explicit that an English PDF for a Malayalam caller is a failed
    delivery, and a silent fallback is exactly how that happens unnoticed: the
    call completes, the pack sends, and the person cannot read the document they
    were told to take to the Rental Dispute Centre.
    """
    for language in ("ar", "ml"):
        with pytest.raises(UnsupportedLanguageError, match=language):
            build_pack([rent_eval], "x", language)


def test_the_refusal_says_what_is_available(rent_eval):
    with pytest.raises(UnsupportedLanguageError, match="en"):
        build_pack([rent_eval], "x", "ml")


# --- How things are written ---------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("80000"), "AED 80,000"),
        (80000, "AED 80,000"),
        ("88000.00", "AED 88,000"),
        (Decimal("88000.50"), "AED 88,000.50"),
        (None, "—"),
    ],
)
def test_money_follows_the_glossary(amount, expected):
    """GLOSSARY section 4: written **AED 80,000**. Never "80K", never "Dhs"."""
    assert money(amount) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2026, 11, 30), "30 November 2026"),
        ("2026-11-30", "30 November 2026"),
        (None, "—"),
    ],
)
def test_dates_are_never_numeric(value, expected):
    """GLOSSARY section 4. The ambiguity between conventions produces wrong
    verdicts, so 30/11 never appears."""
    assert written_date(value) == expected


def test_the_pack_writes_money_the_way_the_glossary_requires(rent_eval):
    text = build_pack([rent_eval], "x", "en").render_text()
    assert "AED 80,000" in text
    assert "80000" not in text.replace(rent_eval.rule_signature, ""), (
        "a raw amount reached the document"
    )


def test_the_pack_uses_no_internal_field_names(rent_eval, notice_eval):
    """`gap_pct` and `max_lawful_rent` are our names for things.

    GLOSSARY section 1 gives each a different user-facing word on purpose — "the
    most they can charge" rather than "legal rent", because the latter sounds
    like a fixed official figure and is not.
    """
    text = build_pack([rent_eval, notice_eval], "x", "en").render_text()
    for internal in (
        "gap_pct",
        "max_lawful_rent",
        "max_increase_pct",
        "proposed_increase_pct",
        "band_matched",
        "shortfall_days",
        "days_notice",
        "current_annual_rent",
        "market_average_rent",
    ):
        assert internal not in text, f"the internal name {internal!r} reached the document"


def test_a_percentage_is_written_as_one(rent_eval):
    """`0.058824` is not something a person can act on."""
    text = build_pack([rent_eval], "x", "en").render_text()
    assert "5.9%" in text
    assert "0.058824" not in text


def test_no_banned_word_reaches_the_document(rent_eval, notice_eval, review_eval):
    """GLOSSARY section 1: each of these either claims legal authority, predicts
    an outcome, or turns information into advice."""
    text = build_pack([rent_eval, notice_eval, review_eval], "x", "en").render_text().lower()
    for banned in (
        "you should",
        "we recommend",
        "your rights",
        "we determine",
        "guarantee",
        "case is strong",
    ):
        assert banned not in text, f"the pack says {banned!r}"

    # "advice" appears only inside the D2 disclosure, which is the one place it
    # is required. Anywhere else it would be the thing D2 denies.
    assert text.count("advice") == text.count("not legal advice")


def test_the_document_fits_on_a_printed_page(rent_eval, notice_eval):
    """This gets printed and carried into a hearing. A line that runs off the
    page is a line nobody reads."""
    text = build_pack([rent_eval, notice_eval], "x", "en").render_text()
    overlong = [
        line
        for line in text.splitlines()
        # A sha256 signature cannot be wrapped and must stay copy-pasteable.
        if len(line) > 78 and "sha256:" not in line
    ]
    assert not overlong, "lines past 78 columns:\n  " + "\n  ".join(overlong)


def test_every_unsupported_language_leaves_instructions():
    """A gap nobody can find is a gap nobody closes.

    Each language the product promises but cannot yet render carries a marker
    saying what is needed and why it is blocked — the same shape as the locale
    files' `_TRANSLATION_STATUS` (D-022). A directory with no template and no
    note reads as an oversight rather than a decision.
    """
    from bayyina.evidence.pack import PACK_TEMPLATE, TEMPLATE_ROOT

    promised = {"en", "ar", "ml"}
    supported = set(supported_languages())

    for language in sorted(promised - supported):
        directory = TEMPLATE_ROOT / language
        assert directory.is_dir(), f"{language} is promised but has no template directory"
        assert not (directory / PACK_TEMPLATE).exists()

        notes = list(directory.glob("_TRANSLATION_NEEDED*"))
        assert notes, f"{language} has no template and no note saying what is needed"

        text = notes[0].read_text(encoding="utf-8")
        assert "GLOSSARY" in text, f"{language}'s note does not point at the source of truth"
        assert "D1" in text, f"{language}'s note does not mention the disclosures"


def test_a_marker_file_does_not_make_a_language_supported():
    """Support is the template, not the intention to write one."""
    assert set(supported_languages()) == {"en"}
