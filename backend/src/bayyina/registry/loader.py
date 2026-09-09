"""Loading the corpus — guardrail G7.

The service must not start on an unsigned or tampered corpus. This is a
load-time failure rather than a policy document, and it is the mechanism behind
the tamper demo: change one digit in a signed rule and the process refuses to
boot.

Failures name the file and the rule, because an operator has to be able to fix
this from the error message alone.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from bayyina.registry.schema import ApprovalStatus, Rule
from bayyina.registry.signing import verify_signature


class CorpusError(RuntimeError):
    """Base for every reason a corpus cannot be trusted."""


class MalformedRuleError(CorpusError):
    """A file in the corpus is not a rule.

    Broken YAML, or YAML that does not match the schema. Raised as a CorpusError
    rather than allowed to surface as a parser traceback, because G7 promises an
    operator can fix a rejected corpus from the message alone - and a stack trace
    from inside pydantic is not that message.
    """


class UnsignedRuleError(CorpusError):
    """A rule carries no approval. Nobody has attested to this encoding."""


class TamperedRuleError(CorpusError):
    """A rule body no longer matches the signature recorded against it."""


class MissingCorpusError(CorpusError):
    """The corpus directory does not exist.

    Distinct from an empty one, because the fixes are different: a missing
    directory is almost always a working directory or a container COPY that is
    wrong, and an empty one is a deleted file. Reporting both as "no rules found"
    makes an operator guess which.
    """


class EmptyCorpusError(CorpusError):
    """No rules were found where rules were expected.

    An empty corpus is the ultimate unverified corpus. A service holding no
    rules can answer nothing, so booting is strictly worse than failing: it
    reports healthy while being useless. In practice this means a deleted file,
    a bad checkout, or a container build that did not copy `rules/`.
    """


def _parse(path: Path) -> Rule:
    """Read one rule file, naming precisely what is wrong with it.

    Both failure modes here are things a person can fix in the file they just
    edited, so the message says which file, which field, and what was expected.
    """
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise MalformedRuleError(f"{path.name}: is not valid YAML. {exc}") from exc

    if not isinstance(document, dict):
        found = "nothing" if document is None else type(document).__name__
        raise MalformedRuleError(
            f"{path.name}: contains no rule - the file parsed as {found}. "
            f"A rule file must be a YAML mapping starting with 'id:'."
        )

    try:
        return Rule.model_validate(document)
    except ValidationError as exc:
        problems = "\n".join(
            f"    {'.'.join(str(part) for part in error['loc']) or '(root)'}: {error['msg']}"
            for error in exc.errors()
        )
        raise MalformedRuleError(
            f"{path.name}: does not match the rule schema:\n{problems}"
        ) from exc


def load_rules(directory: Path | str, *, allow_empty: bool = False) -> dict[str, Rule]:
    """Load and verify every rule in a directory.

    Returns rules keyed by id. Raises on the first rule that cannot be trusted —
    **the whole corpus fails**, because partially loading it would mean the
    service runs on logic nobody has reviewed.

    `allow_empty` exists only for the window before the first rule is signed.
    It must be an explicit choice, never a default, so that a corpus which
    silently disappears is caught rather than tolerated.
    """
    root = Path(directory)
    if not root.is_dir():
        raise MissingCorpusError(
            f"the corpus directory '{directory}' does not exist "
            f"(resolved to '{root.resolve()}'). The service is almost certainly "
            f"running from the wrong working directory, or the container image "
            f"did not copy rules/."
        )

    rules: dict[str, Rule] = {}

    for path in sorted(root.glob("*.yaml")):
        rule = _parse(path)

        if rule.approval.status is ApprovalStatus.UNSIGNED:
            raise UnsignedRuleError(
                f"{path.name}: rule '{rule.id}' v{rule.version} is unsigned. "
                f"An approver must sign it before the service can start. "
                f"Run: python scripts/sign_rule.py {path}"
            )

        if not verify_signature(rule):
            raise TamperedRuleError(
                f"{path.name}: the body of rule '{rule.id}' v{rule.version} does not "
                f"match its recorded signature. The rule was edited after signing. "
                f"Review the change, then re-sign: python scripts/sign_rule.py {path}"
            )

        rules[rule.id] = rule

    if not rules and not allow_empty:
        raise EmptyCorpusError(
            f"'{root.resolve()}' exists but contains no *.yaml rules. A service "
            "with no rules can answer nothing, so it must not start. This usually "
            "means a deleted file or a bad checkout. Pass allow_empty=True only "
            "before the first rule has been signed."
        )

    return rules
