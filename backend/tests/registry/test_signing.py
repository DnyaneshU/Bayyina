"""The signature covers the rule body and nothing else.

This is guardrail G7. If these tests are wrong, the tamper demo does not work and
the compliance claim is hollow.
"""

from pathlib import Path

from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest, verify_signature
from tests.registry.test_schema import MINIMAL

APPROVAL = {
    "status": "provisional",
    "approved_by": "Bayyina team",
    "approved_at": "2026-09-09T00:00:00Z",
}
# A structurally valid table with one value changed. Tampering that *also*
# breaks the table's shape would be caught by schema validation instead, which
# is not what these tests are about.
TAMPERED_BANDS = [
    {"gap_from": 0.0, "gap_to": 0.10, "max_increase": 0.99},
    {"gap_from": 0.10, "gap_to": None, "max_increase": 0.20},
]


def _rule(**overrides) -> Rule:
    return Rule.model_validate({**MINIMAL, **overrides})


def test_digest_is_stable():
    assert rule_digest(_rule()) == rule_digest(_rule())


def test_digest_is_prefixed_and_hex():
    digest = rule_digest(_rule())
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


def test_digest_changes_when_a_band_changes():
    """One digit in the band table must change the signature. This is the demo."""
    assert rule_digest(_rule()) != rule_digest(_rule(bands=TAMPERED_BANDS))


def test_digest_ignores_the_approval_block():
    """Signing must not change what is signed, or no signature could ever verify."""
    signed = _rule(approval={**APPROVAL, "signature": "sha256:anything"})
    assert rule_digest(_rule()) == rule_digest(signed)


def test_verify_accepts_a_matching_signature():
    good = _rule(approval={**APPROVAL, "signature": rule_digest(_rule())})
    assert verify_signature(good) is True


def test_verify_rejects_a_tampered_body():
    bad = _rule(
        bands=TAMPERED_BANDS,
        approval={**APPROVAL, "signature": rule_digest(_rule())},
    )
    assert verify_signature(bad) is False


def test_verify_rejects_a_missing_signature():
    assert verify_signature(_rule()) is False


def test_the_digest_does_not_depend_on_line_endings():
    """The project is developed on Windows and deployed to Linux.

    If a CRLF-to-LF conversion changed a rule's digest, every signature would
    break the moment the corpus was checked out on a Linux runner or copied into
    a container — a total deployment failure, from a file nobody edited.

    It holds because PyYAML normalises line breaks when parsing, per the YAML
    spec. That is a property we now rely on, so it is asserted rather than
    assumed.
    """
    import yaml

    from bayyina.registry.schema import Rule

    path = Path(__file__).resolve().parents[2] / "rules"
    for rule_file in sorted(path.glob("*.yaml")):
        raw = rule_file.read_bytes()
        lf = Rule.model_validate(yaml.safe_load(raw.replace(b"\r\n", b"\n").decode("utf-8")))
        crlf = Rule.model_validate(
            yaml.safe_load(raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n").decode("utf-8"))
        )

        assert rule_digest(lf) == rule_digest(crlf), f"{rule_file.name} digest moved"
        assert verify_signature(lf) and verify_signature(crlf)
