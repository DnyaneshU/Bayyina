# Bayyina Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A multilingual voice agent and public web checker that answer Dubai
rent-increase, notice-validity and end-of-service questions from a signed,
versioned rules registry, with the governing clause cited aloud.

**Architecture:** Determinism at the core, language only at the edge. A Python
rules registry computes every verdict as a pure function and returns a structured
result with a citation; the ElevenLabs agent triages, slot-fills and speaks, but
never computes. Market comparables come from 4.2M registered Ejari contracts in
DuckDB. Guardrails are schema contracts and load-time checks, never prompt text.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB, pytest, Jinja2,
ElevenLabs Agents (Workflows, Scribe v2, Eleven v3), Twilio.

**Spec:** [docs/DESIGN.md](docs/DESIGN.md) (what and why) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (how). Executors read both.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **The LLM never computes a verdict.** Any task that puts arithmetic or rule
  interpretation into a prompt is wrong by construction.
- **The agent acts but never decides.** It assembles, lodges, tracks and follows
  up. No code path may set a case to `approved`, `rejected` or `amended` — those
  belong to a human officer. A task that adds one is wrong by construction.
- **No verdict without a citation.** Every evaluator return carries a non-null
  `citation`, or it is not a verdict.
- **No outbound call without recorded consent**, and an opt-out is irreversible.
- **Rule signature statuses:** `unsigned` → the loader raises and the service does
  not boot. `provisional` → loads, and every response carries
  `review_status: "provisional"` which the agent must disclose aloud.
  `certified` → requires a qualified reviewer. **We are `provisional` until a
  reviewer is appointed, and we say so.**
- **Money is `Decimal`, never `float`.** Rates and gaps may be float.
- **Dates are `datetime.date`, never strings, past the API boundary.**
- **Every evaluation writes an immutable record.** Records are append-only.
- **Languages v1:** English, Arabic (Gulf), Malayalam, Hindi, Urdu.
- **Commit after every task.** Small, frequent, message prefixed `feat:`/`test:`/`docs:`.
- **Python 3.11+**, `pytest` for all tests, `ruff` for lint.

---

## Phase Map

| Phase | Window | Outcome |
|---|---|---|
| **0** | Now → 10 Sep | Unblock: template, word limits, organiser questions, reviewer hunt |
| **1** | Now → 23 Sep | Registry + comparables + web checker **deployed**, canvas submitted |
| **2** | 23 → 30 Sep | Agent skeleton and test suites written *before* the sprint starts |
| **3** | 30 Sep → 14 Oct | Build sprint: full agent, all guardrails, demo recording |
| **4** | 14 → 26 Oct | Harden, rehearse, pursue pilot conversation |

**Phase 1 is the one that must not slip.** Box N scores zero without a live link.

---

# PHASE 0 · Unblock

### Task 0: Resolve external unknowns

No code. These gate later decisions and every one is a same-day action.

- [ ] **Step 1: Download the official Idea Canvas template**

From the challenge page ("Download the Template Idea Canvas Submission Document").
Record the **exact word limit for each of the 14 boxes** into the status-tracker
table in `docs/CANVAS.md`, replacing every *from template* placeholder.

- [ ] **Step 2: Post the Demo Day question on the challenge Discussion tab**

Ask: *"Is remote participation available for finalists at Demo Day on 26–27
October?"* The team cannot travel. The answer shapes Phase 4. Asking early also
puts the team name in front of the organisers.

- [ ] **Step 3: Search the Ignyte mentor directory for a legal or regtech advisor**

550+ mentors are available on the platform today. A one-off advisory review is
enough to move rule status from `provisional` to `certified` and to name a
reviewer in box K. Budget one hour.

- [ ] **Step 4: Register for Dubai Pulse and request the rent contracts dataset**

`dld_rent_contracts-open`. API key and secret arrive in two separate emails.
**Do this first — access is not instant, and Task 11 blocks on it.** Download the
bulk CSV in parallel as a fallback so Task 11 is never blocked on OAuth onboarding.

- [ ] **Step 5: Verify the box D baseline figures**

Every ⚠ row in `docs/CANVAS.md` box D. Where a figure cannot be sourced, rewrite
it as an explicit hypothesis to be measured. **Do not invent numbers** — boxes D
and J are cross-checked.

- [ ] **Step 6: Commit**

```bash
git add docs/CANVAS.md
git commit -m "docs: record canvas word limits and sourced baselines"
```

---

# PHASE 1 · Registry, Data, Web Checker

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `src/bayyina/__init__.py`, `tests/__init__.py`, `.gitignore`
- Test: `tests/test_scaffold.py`

**Interfaces:**
- Produces: the `bayyina` package importable from `src/`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scaffold.py
def test_package_imports():
    import bayyina
    assert bayyina.__version__
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `pytest tests/test_scaffold.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bayyina'`

- [ ] **Step 3: Create the package**

```toml
# pyproject.toml
[project]
name = "bayyina"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7",
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "pyyaml>=6.0",
  "duckdb>=1.0",
  "jinja2>=3.1",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```python
# src/bayyina/__init__.py
__version__ = "0.1.0"
```

```gitignore
__pycache__/
*.pyc
.venv/
data/*.duckdb
data/raw/
.env
```

- [ ] **Step 4: Install and confirm the test passes**

Run: `pip install -e ".[dev]" && pytest tests/test_scaffold.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src tests .gitignore
git commit -m "feat: project scaffold"
```

---

## Task 2: Rule schema

**Files:**
- Create: `src/bayyina/registry/__init__.py`, `src/bayyina/registry/schema.py`
- Test: `tests/registry/test_schema.py`

**Interfaces:**
- Produces: `Rule`, `RuleSource`, `RuleApproval`, `Band`, `ApprovalStatus`.
  `Rule.body_for_signing() -> dict` returns the rule minus its approval block —
  this is what Task 3 hashes.

- [ ] **Step 1: Write the failing test**

```python
# tests/registry/test_schema.py
import pytest
from bayyina.registry.schema import Rule, ApprovalStatus

MINIMAL = {
    "id": "rent_increase.dubai.decree_43_2013",
    "version": 1,
    "jurisdiction": "AE-DU",
    "effective_from": "2013-12-09",
    "effective_to": None,
    "source": {
        "document_id": "dubai_decree_43_2013",
        "title": "Decree No. (43) of 2013",
        "clause": "Article 1",
        "url": "https://dubailand.gov.ae/",
        "verbatim": "Sets maximum permitted percentage increase in property rent.",
    },
    "logic": "banded_percentage",
    "inputs": {},
    "bands": [
        {"gap_from": 0.0, "gap_to": 0.10, "max_increase": 0.0},
        {"gap_from": 0.10, "gap_to": None, "max_increase": 0.20},
    ],
    "review_notes": [],
    "approval": {"status": "unsigned", "approved_by": None,
                 "approved_at": None, "signature": None},
}

def test_parses_minimal_rule():
    rule = Rule.model_validate(MINIMAL)
    assert rule.id == "rent_increase.dubai.decree_43_2013"
    assert rule.approval.status is ApprovalStatus.UNSIGNED

def test_body_for_signing_excludes_approval():
    body = Rule.model_validate(MINIMAL).body_for_signing()
    assert "approval" not in body
    assert body["id"] == "rent_increase.dubai.decree_43_2013"

def test_citation_fields_are_mandatory():
    broken = {**MINIMAL, "source": {**MINIMAL["source"], "clause": None}}
    with pytest.raises(Exception):
        Rule.model_validate(broken)
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/registry/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: bayyina.registry.schema`

- [ ] **Step 3: Implement the schema**

```python
# src/bayyina/registry/schema.py
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, Enum):
    UNSIGNED = "unsigned"        # loader refuses — service will not boot
    PROVISIONAL = "provisional"  # loads; agent must disclose aloud
    CERTIFIED = "certified"      # reviewed by a qualified person


class RuleSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str
    title: str
    clause: str            # mandatory: no verdict without a citation
    url: str
    verbatim: str


class RuleApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ApprovalStatus = ApprovalStatus.UNSIGNED
    approved_by: str | None = None
    approved_at: datetime | None = None
    signature: str | None = None


class Band(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gap_from: float
    gap_to: float | None      # None == unbounded upper band
    max_increase: float


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    version: int
    jurisdiction: str
    effective_from: date
    effective_to: date | None = None
    source: RuleSource
    logic: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    bands: list[Band] | None = None
    review_notes: list[str] = Field(default_factory=list)
    approval: RuleApproval = Field(default_factory=RuleApproval)

    def body_for_signing(self) -> dict[str, Any]:
        """The rule minus its approval block. This is what gets hashed."""
        return self.model_dump(mode="json", exclude={"approval"})
```

- [ ] **Step 4: Run and confirm all three tests pass**

Run: `pytest tests/registry/test_schema.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/registry tests/registry
git commit -m "feat: rule schema with mandatory citation fields"
```

---

## Task 3: Signing and verification

**Files:**
- Create: `src/bayyina/registry/signing.py`
- Test: `tests/registry/test_signing.py`

**Interfaces:**
- Consumes: `Rule` from Task 2.
- Produces: `rule_digest(rule: Rule) -> str` returning `"sha256:<hex>"`;
  `verify_signature(rule: Rule) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/registry/test_signing.py
from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest, verify_signature
from tests.registry.test_schema import MINIMAL


def _rule(**overrides):
    data = {**MINIMAL, **overrides}
    return Rule.model_validate(data)


def test_digest_is_stable():
    assert rule_digest(_rule()) == rule_digest(_rule())


def test_digest_changes_when_body_changes():
    tampered = _rule(bands=[{"gap_from": 0.0, "gap_to": 0.10,
                             "max_increase": 0.99}])
    assert rule_digest(_rule()) != rule_digest(tampered)


def test_digest_ignores_approval_block():
    signed = _rule(approval={"status": "provisional", "approved_by": "team",
                             "approved_at": "2026-09-07T00:00:00Z",
                             "signature": "sha256:whatever"})
    assert rule_digest(_rule()) == rule_digest(signed)


def test_verify_accepts_matching_signature():
    base = _rule()
    good = _rule(approval={"status": "provisional", "approved_by": "team",
                           "approved_at": "2026-09-07T00:00:00Z",
                           "signature": rule_digest(base)})
    assert verify_signature(good) is True


def test_verify_rejects_tampered_body():
    base = _rule()
    tampered = _rule(
        bands=[{"gap_from": 0.0, "gap_to": 0.10, "max_increase": 0.99}],
        approval={"status": "provisional", "approved_by": "team",
                  "approved_at": "2026-09-07T00:00:00Z",
                  "signature": rule_digest(base)},
    )
    assert verify_signature(tampered) is False
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/registry/test_signing.py -v`
Expected: FAIL — `ModuleNotFoundError: bayyina.registry.signing`

- [ ] **Step 3: Implement**

```python
# src/bayyina/registry/signing.py
from __future__ import annotations

import hashlib
import json

from bayyina.registry.schema import Rule


def _canonical_bytes(body: dict) -> bytes:
    """Deterministic serialisation: sorted keys, no incidental whitespace."""
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def rule_digest(rule: Rule) -> str:
    """Hash of the rule body, excluding the approval block."""
    digest = hashlib.sha256(_canonical_bytes(rule.body_for_signing())).hexdigest()
    return f"sha256:{digest}"


def verify_signature(rule: Rule) -> bool:
    """True when the recorded signature matches the current rule body."""
    if not rule.approval.signature:
        return False
    return rule.approval.signature == rule_digest(rule)
```

- [ ] **Step 4: Run and confirm all five tests pass**

Run: `pytest tests/registry/test_signing.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/registry/signing.py tests/registry/test_signing.py
git commit -m "feat: canonical rule digest and signature verification"
```

---

## Task 4: Loader — guardrail G7

**Files:**
- Create: `src/bayyina/registry/loader.py`
- Test: `tests/registry/test_loader.py`

**Interfaces:**
- Consumes: `Rule`, `verify_signature`.
- Produces: `load_rules(directory: Path) -> dict[str, Rule]`;
  exceptions `UnsignedRuleError`, `TamperedRuleError`.

**This is guardrail G7.** The service must not boot with an unsigned corpus.

- [ ] **Step 1: Write the failing test**

```python
# tests/registry/test_loader.py
import yaml
import pytest

from bayyina.registry.loader import (
    load_rules, UnsignedRuleError, TamperedRuleError,
)
from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest
from tests.registry.test_schema import MINIMAL


def _write(tmp_path, data, name="r.v1.yaml"):
    (tmp_path / name).write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


def _signed(data):
    signed = {**data, "approval": {"status": "provisional",
                                   "approved_by": "team",
                                   "approved_at": "2026-09-07T00:00:00Z",
                                   "signature": None}}
    signed["approval"]["signature"] = rule_digest(Rule.model_validate(signed))
    return signed


def test_refuses_unsigned_rule(tmp_path):
    _write(tmp_path, MINIMAL)
    with pytest.raises(UnsignedRuleError):
        load_rules(tmp_path)


def test_refuses_tampered_rule(tmp_path):
    data = _signed(MINIMAL)
    data["bands"][0]["max_increase"] = 0.99   # tamper after signing
    _write(tmp_path, data)
    with pytest.raises(TamperedRuleError):
        load_rules(tmp_path)


def test_loads_signed_rule(tmp_path):
    _write(tmp_path, _signed(MINIMAL))
    rules = load_rules(tmp_path)
    assert "rent_increase.dubai.decree_43_2013" in rules
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/registry/test_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: bayyina.registry.loader`

- [ ] **Step 3: Implement**

```python
# src/bayyina/registry/loader.py
from __future__ import annotations

from pathlib import Path

import yaml

from bayyina.registry.schema import ApprovalStatus, Rule
from bayyina.registry.signing import verify_signature


class UnsignedRuleError(RuntimeError):
    """A rule in the corpus carries no approval. The service must not boot."""


class TamperedRuleError(RuntimeError):
    """A rule body no longer matches its recorded signature."""


def load_rules(directory: Path) -> dict[str, Rule]:
    rules: dict[str, Rule] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        rule = Rule.model_validate(yaml.safe_load(path.read_text("utf-8")))

        if rule.approval.status is ApprovalStatus.UNSIGNED:
            raise UnsignedRuleError(
                f"{path.name}: rule {rule.id} v{rule.version} is unsigned. "
                "An approver must sign it before the service can start."
            )
        if not verify_signature(rule):
            raise TamperedRuleError(
                f"{path.name}: body of {rule.id} v{rule.version} does not "
                "match its signature."
            )
        rules[rule.id] = rule
    return rules
```

- [ ] **Step 4: Run and confirm all three tests pass**

Run: `pytest tests/registry/test_loader.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/registry/loader.py tests/registry/test_loader.py
git commit -m "feat: G7 loader refuses unsigned and tampered rules"
```

---

## Task 5: Rent increase logic

**Files:**
- Create: `src/bayyina/rules_logic/__init__.py`, `src/bayyina/rules_logic/banded_percentage.py`
- Test: `tests/rules_logic/test_banded_percentage.py`

**Interfaces:**
- Produces: `evaluate(current_annual_rent: Decimal, market_average_rent: Decimal,
  proposed_annual_rent: Decimal, bands: list[Band]) -> BandedResult` where
  `BandedResult` has `verdict: str`, `gap_pct: float`, `band_matched: int`,
  `max_increase_pct: float`, `max_lawful_rent: Decimal`,
  `proposed_increase_pct: float`.

Band semantics: bands are ascending; the first band whose `gap_to` is `None` or
`>= gap` matches. So gap 0.10 → band 0 (0%), gap 0.1001 → band 1 (5%).

- [ ] **Step 1: Write the failing test**

```python
# tests/rules_logic/test_banded_percentage.py
from decimal import Decimal

import pytest

from bayyina.registry.schema import Band
from bayyina.rules_logic.banded_percentage import evaluate

BANDS = [
    Band(gap_from=0.00, gap_to=0.10, max_increase=0.00),
    Band(gap_from=0.10, gap_to=0.20, max_increase=0.05),
    Band(gap_from=0.20, gap_to=0.30, max_increase=0.10),
    Band(gap_from=0.30, gap_to=0.40, max_increase=0.15),
    Band(gap_from=0.40, gap_to=None, max_increase=0.20),
]


@pytest.mark.parametrize(
    "current,market,expected_band,expected_max",
    [
        (Decimal("100000"), Decimal("100000"), 0, 0.00),  # at market
        (Decimal("90000"),  Decimal("100000"), 0, 0.00),  # exactly 10% below
        (Decimal("89000"),  Decimal("100000"), 1, 0.05),  # just over 10%
        (Decimal("80000"),  Decimal("100000"), 1, 0.05),  # exactly 20%
        (Decimal("70000"),  Decimal("100000"), 2, 0.10),  # exactly 30%
        (Decimal("60000"),  Decimal("100000"), 3, 0.15),  # exactly 40%
        (Decimal("50000"),  Decimal("100000"), 4, 0.20),  # 50% below
    ],
)
def test_band_boundaries(current, market, expected_band, expected_max):
    r = evaluate(current, market, current, BANDS)
    assert r.band_matched == expected_band
    assert r.max_increase_pct == pytest.approx(expected_max)


def test_rent_above_market_permits_no_increase():
    r = evaluate(Decimal("120000"), Decimal("100000"), Decimal("125000"), BANDS)
    assert r.band_matched == 0
    assert r.verdict == "not_permitted"


def test_permitted_when_proposal_within_cap():
    r = evaluate(Decimal("50000"), Decimal("100000"), Decimal("60000"), BANDS)
    assert r.max_lawful_rent == Decimal("60000.00")
    assert r.verdict == "permitted"


def test_not_permitted_when_proposal_exceeds_cap():
    r = evaluate(Decimal("50000"), Decimal("100000"), Decimal("61000"), BANDS)
    assert r.verdict == "not_permitted"


def test_zero_market_average_is_rejected():
    with pytest.raises(ValueError):
        evaluate(Decimal("50000"), Decimal("0"), Decimal("60000"), BANDS)
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/rules_logic/test_banded_percentage.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/bayyina/rules_logic/banded_percentage.py
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from bayyina.registry.schema import Band

_CENTS = Decimal("0.01")


@dataclass(frozen=True)
class BandedResult:
    verdict: str
    gap_pct: float
    band_matched: int
    max_increase_pct: float
    max_lawful_rent: Decimal
    proposed_increase_pct: float


def evaluate(
    current_annual_rent: Decimal,
    market_average_rent: Decimal,
    proposed_annual_rent: Decimal,
    bands: list[Band],
) -> BandedResult:
    if market_average_rent <= 0:
        raise ValueError("market_average_rent must be positive")
    if current_annual_rent <= 0:
        raise ValueError("current_annual_rent must be positive")

    # How far the current rent sits BELOW the market average.
    # At or above market, the gap is zero and the lowest band applies.
    raw_gap = (market_average_rent - current_annual_rent) / market_average_rent
    gap = max(0.0, float(raw_gap))

    for index, band in enumerate(bands):
        if band.gap_to is None or gap <= band.gap_to:
            max_increase = band.max_increase
            matched = index
            break
    else:  # pragma: no cover - bands always end with an unbounded band
        raise ValueError("no band matched; corpus is malformed")

    max_lawful = (
        current_annual_rent * (Decimal("1") + Decimal(str(max_increase)))
    ).quantize(_CENTS, rounding=ROUND_HALF_UP)

    proposed_increase = float(
        (proposed_annual_rent - current_annual_rent) / current_annual_rent
    )

    return BandedResult(
        verdict="permitted" if proposed_annual_rent <= max_lawful else "not_permitted",
        gap_pct=gap,
        band_matched=matched,
        max_increase_pct=max_increase,
        max_lawful_rent=max_lawful,
        proposed_increase_pct=proposed_increase,
    )
```

- [ ] **Step 4: Run and confirm all tests pass**

Run: `pytest tests/rules_logic/test_banded_percentage.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/rules_logic tests/rules_logic
git commit -m "feat: Decree 43/2013 banded percentage evaluation"
```

---

## Task 6: Notice validity logic

**Files:**
- Create: `src/bayyina/rules_logic/notice_period.py`
- Test: `tests/rules_logic/test_notice_period.py`

**Interfaces:**
- Produces: `evaluate(contract_expiry: date, notice_served: date,
  required_days: int) -> NoticeResult` with `verdict`, `days_notice`,
  `required_days`, `shortfall_days`.

- [ ] **Step 1: Write the failing test**

```python
# tests/rules_logic/test_notice_period.py
from datetime import date

import pytest

from bayyina.rules_logic.notice_period import evaluate


@pytest.mark.parametrize(
    "served,expected_verdict,expected_days",
    [
        (date(2026, 1, 1),  "valid",   90),   # exactly 90 days
        (date(2025, 12, 1), "valid",  121),   # comfortably early
        (date(2026, 1, 2),  "invalid", 89),   # one day short
        (date(2026, 3, 1),  "invalid",  31),  # far too late
    ],
)
def test_ninety_day_boundary(served, expected_verdict, expected_days):
    r = evaluate(date(2026, 4, 1), served, 90)
    assert r.days_notice == expected_days
    assert r.verdict == expected_verdict


def test_shortfall_is_reported():
    r = evaluate(date(2026, 4, 1), date(2026, 1, 2), 90)
    assert r.shortfall_days == 1


def test_valid_notice_has_zero_shortfall():
    assert evaluate(date(2026, 4, 1), date(2026, 1, 1), 90).shortfall_days == 0


def test_notice_after_expiry_is_invalid():
    r = evaluate(date(2026, 4, 1), date(2026, 5, 1), 90)
    assert r.verdict == "invalid"
    assert r.days_notice < 0
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/rules_logic/test_notice_period.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/bayyina/rules_logic/notice_period.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class NoticeResult:
    verdict: str
    days_notice: int
    required_days: int
    shortfall_days: int


def evaluate(
    contract_expiry: date, notice_served: date, required_days: int
) -> NoticeResult:
    days_notice = (contract_expiry - notice_served).days
    shortfall = max(0, required_days - days_notice)
    return NoticeResult(
        verdict="valid" if days_notice >= required_days else "invalid",
        days_notice=days_notice,
        required_days=required_days,
        shortfall_days=shortfall,
    )
```

- [ ] **Step 4: Run and confirm all tests pass**

Run: `pytest tests/rules_logic/test_notice_period.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/rules_logic/notice_period.py tests/rules_logic/test_notice_period.py
git commit -m "feat: Law 26/2007 Art.14 notice period evaluation"
```

---

## Task 7: Gratuity logic

**Files:**
- Create: `src/bayyina/rules_logic/gratuity.py`
- Test: `tests/rules_logic/test_gratuity.py`

**Interfaces:**
- Produces: `evaluate(basic_monthly_salary: Decimal, start: date, end: date,
  unpaid_leave_days: int = 0) -> GratuityResult` with `verdict`,
  `service_years`, `entitled_days`, `daily_wage`, `gratuity_amount`,
  `cap_applied: bool`.

Article 51: under one year → no entitlement; one to five years → 21 days' basic
wage per year; beyond five years → 21 days for each of the first five plus 30 days
for each subsequent year; total capped at two years' wage. **Basic salary only.**

v1 daily-wage convention: `basic_monthly ÷ 30`. The alternative
(`basic × 12 ÷ 365`) is recorded in the rule's `review_notes` — the provenance
mechanism surfacing a genuine ambiguity rather than burying it.

- [ ] **Step 1: Write the failing test**

```python
# tests/rules_logic/test_gratuity.py
from datetime import date
from decimal import Decimal

import pytest

from bayyina.rules_logic.gratuity import evaluate

SALARY = Decimal("9000")     # daily wage = 300


def test_under_one_year_has_no_entitlement():
    r = evaluate(SALARY, date(2025, 1, 1), date(2025, 9, 1))
    assert r.verdict == "no_entitlement"
    assert r.gratuity_amount == Decimal("0.00")


def test_exactly_one_year_gives_twenty_one_days():
    r = evaluate(SALARY, date(2025, 1, 1), date(2026, 1, 1))
    assert r.entitled_days == pytest.approx(21.0, abs=0.2)
    assert r.gratuity_amount == pytest.approx(Decimal("6300"), abs=Decimal("60"))


def test_three_years_scales_linearly():
    r = evaluate(SALARY, date(2023, 1, 1), date(2026, 1, 1))
    assert r.entitled_days == pytest.approx(63.0, abs=0.5)


def test_beyond_five_years_uses_thirty_day_rate():
    # 7 years -> 21*5 + 30*2 = 165 days
    r = evaluate(SALARY, date(2019, 1, 1), date(2026, 1, 1))
    assert r.entitled_days == pytest.approx(165.0, abs=1.0)


def test_two_year_wage_cap_is_applied():
    # 40 years of service would far exceed the cap of 24 months' salary
    r = evaluate(SALARY, date(1986, 1, 1), date(2026, 1, 1))
    assert r.cap_applied is True
    assert r.gratuity_amount == Decimal("216000.00")   # 9000 * 24


def test_unpaid_leave_reduces_service():
    with_leave = evaluate(SALARY, date(2023, 1, 1), date(2026, 1, 1), 200)
    without = evaluate(SALARY, date(2023, 1, 1), date(2026, 1, 1), 0)
    assert with_leave.service_years < without.service_years


def test_end_before_start_is_rejected():
    with pytest.raises(ValueError):
        evaluate(SALARY, date(2026, 1, 1), date(2025, 1, 1))
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/rules_logic/test_gratuity.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# src/bayyina/rules_logic/gratuity.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")
_DAYS_PER_YEAR = 365.0
_FIRST_TIER_YEARS = 5.0
_FIRST_TIER_DAYS = 21.0
_SECOND_TIER_DAYS = 30.0
_CAP_MONTHS = 24


@dataclass(frozen=True)
class GratuityResult:
    verdict: str
    service_years: float
    entitled_days: float
    daily_wage: Decimal
    gratuity_amount: Decimal
    cap_applied: bool


def evaluate(
    basic_monthly_salary: Decimal,
    start: date,
    end: date,
    unpaid_leave_days: int = 0,
) -> GratuityResult:
    if end < start:
        raise ValueError("end date precedes start date")
    if basic_monthly_salary <= 0:
        raise ValueError("basic_monthly_salary must be positive")

    service_days = (end - start).days - unpaid_leave_days
    service_years = max(0.0, service_days / _DAYS_PER_YEAR)
    daily_wage = (basic_monthly_salary / Decimal("30")).quantize(
        _CENTS, rounding=ROUND_HALF_UP
    )

    if service_years < 1.0:
        return GratuityResult(
            verdict="no_entitlement",
            service_years=service_years,
            entitled_days=0.0,
            daily_wage=daily_wage,
            gratuity_amount=Decimal("0.00"),
            cap_applied=False,
        )

    if service_years <= _FIRST_TIER_YEARS:
        entitled_days = _FIRST_TIER_DAYS * service_years
    else:
        entitled_days = _FIRST_TIER_DAYS * _FIRST_TIER_YEARS + _SECOND_TIER_DAYS * (
            service_years - _FIRST_TIER_YEARS
        )

    raw = daily_wage * Decimal(str(entitled_days))
    cap = basic_monthly_salary * _CAP_MONTHS
    cap_applied = raw > cap
    amount = (cap if cap_applied else raw).quantize(_CENTS, rounding=ROUND_HALF_UP)

    return GratuityResult(
        verdict="entitled",
        service_years=service_years,
        entitled_days=entitled_days,
        daily_wage=daily_wage,
        gratuity_amount=amount,
        cap_applied=cap_applied,
    )
```

- [ ] **Step 4: Run and confirm all tests pass**

Run: `pytest tests/rules_logic/test_gratuity.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/rules_logic/gratuity.py tests/rules_logic/test_gratuity.py
git commit -m "feat: Art.51 end-of-service gratuity evaluation"
```

---

## Task 8: Evaluator and evaluation record

**Files:**
- Create: `src/bayyina/registry/evaluator.py`, `src/bayyina/evaluation_log.py`
- Test: `tests/registry/test_evaluator.py`, `tests/test_evaluation_log.py`

**Interfaces:**
- Consumes: `load_rules`, the three `rules_logic` modules.
- Produces: `Evaluator(rules: dict[str, Rule])` with
  `evaluate(rule_id: str, inputs: dict, input_sources: dict) -> EvaluationRecord`.
  `EvaluationRecord` is a Pydantic model matching
  [ARCHITECTURE.md](docs/ARCHITECTURE.md) §5.3, always carrying a non-null
  `citation` and a `review_status` copied from the rule's approval status.
- Produces: `EvaluationLog.append(record) -> None`, `EvaluationLog.get(eval_id)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/registry/test_evaluator.py
from decimal import Decimal

import pytest

from bayyina.registry.evaluator import Evaluator, UnknownRuleError


def test_verdict_always_carries_a_citation(signed_rules):
    rec = Evaluator(signed_rules).evaluate(
        "rent_increase.dubai.decree_43_2013",
        {"current_annual_rent": Decimal("85000"),
         "market_average_rent": Decimal("91000"),
         "proposed_annual_rent": Decimal("102000")},
        {"market_average_rent": "dld_open_rent_contracts_derived"},
    )
    assert rec.citation.clause == "Article 1"
    assert rec.verdict == "not_permitted"


def test_review_status_is_carried_from_the_rule(signed_rules):
    rec = Evaluator(signed_rules).evaluate(
        "rent_increase.dubai.decree_43_2013",
        {"current_annual_rent": Decimal("85000"),
         "market_average_rent": Decimal("91000"),
         "proposed_annual_rent": Decimal("102000")},
        {"market_average_rent": "dld_open_rent_contracts_derived"},
    )
    assert rec.review_status == "provisional"


def test_unknown_rule_raises(signed_rules):
    with pytest.raises(UnknownRuleError):
        Evaluator(signed_rules).evaluate("nope", {}, {})
```

Add a `signed_rules` fixture in `tests/conftest.py` that signs and loads the three
real YAML files from `rules/` (written in Task 10) — so this test exercises the
production corpus, not a stub.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/registry/test_evaluator.py -v`
Expected: FAIL — `ModuleNotFoundError: bayyina.registry.evaluator`

- [ ] **Step 3: Implement the evaluator, dispatching on `rule.logic`**

Dispatch table `{"banded_percentage": ..., "notice_period": ..., "gratuity": ...}`.
Build an `EvaluationRecord` with `eval_id` (uuid4, `ev_` prefix), `rule_id`,
`rule_version`, `rule_signature`, `inputs`, `input_sources`, `verdict`,
`computed`, `citation` (from `rule.source`), `confidence`, `review_status`
(from `rule.approval.status`), `created_at` (UTC now).

- [ ] **Step 4: Run and confirm the tests pass**

Run: `pytest tests/registry -v`

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/registry/evaluator.py src/bayyina/evaluation_log.py tests
git commit -m "feat: evaluator dispatch and immutable evaluation records"
```

---

## Task 9: Write and sign the three rule files

**Files:**
- Create: `rules/rent_increase.dubai.decree_43_2013.v1.yaml`,
  `rules/notice_validity.dubai.law_26_2007_a14.v1.yaml`,
  `rules/gratuity.uae.decree_33_2021_a51.v1.yaml`
- Create: `scripts/sign_rule.py`
- Test: `tests/test_corpus.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_corpus.py
from pathlib import Path

from bayyina.registry.loader import load_rules

RULES_DIR = Path(__file__).resolve().parents[1] / "rules"


def test_production_corpus_loads():
    rules = load_rules(RULES_DIR)
    assert set(rules) == {
        "rent_increase.dubai.decree_43_2013",
        "notice_validity.dubai.law_26_2007_a14",
        "gratuity.uae.decree_33_2021_a51",
    }


def test_every_rule_has_a_verbatim_source_clause():
    for rule in load_rules(RULES_DIR).values():
        assert rule.source.clause
        assert rule.source.verbatim.strip()
        assert rule.source.url.startswith("https://")
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/test_corpus.py -v`
Expected: FAIL — the `rules/` directory is empty

- [ ] **Step 3: Write the three YAML files**

Use the full worked example in [ARCHITECTURE.md](docs/ARCHITECTURE.md) §5.1 for
the rent rule. Set `approval.status: provisional` and `approved_by` to the team
name for all three — **we are provisional until a reviewer is appointed, and the
agent discloses this aloud.** Record the gratuity daily-wage ambiguity in
`review_notes`.

- [ ] **Step 4: Write the signing script and sign all three**

```python
# scripts/sign_rule.py
"""Sign a rule file in place. Usage: python scripts/sign_rule.py rules/<file>.yaml"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text("utf-8"))
data["approval"]["approved_at"] = datetime.now(timezone.utc).isoformat()
data["approval"]["signature"] = None
data["approval"]["signature"] = rule_digest(Rule.model_validate(data))
path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), "utf-8")
print(f"signed {data['id']} v{data['version']} -> {data['approval']['signature']}")
```

Run it for each of the three files.

- [ ] **Step 5: Run the corpus tests and confirm they pass**

Run: `pytest tests/test_corpus.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add rules scripts tests/test_corpus.py
git commit -m "feat: sign the three v1 rules as provisional"
```

---

## Task 10: Market comparables from Dubai Pulse

**Files:**
- Create: `src/bayyina/market/__init__.py`, `src/bayyina/market/ingest.py`,
  `src/bayyina/market/comparables.py`
- Test: `tests/market/test_comparables.py`

**Interfaces:**
- Produces: `ingest_csv(csv_path: Path, db_path: Path) -> int` returning row count.
- Produces: `Comparables(db_path).median_rent(area: str, property_type: str,
  bedrooms: int, window_days: int = 365) -> ComparableResult` with
  `median_annual_rent: Decimal | None`, `contract_count: int`,
  `confidence: float`, `status: str`, `snapshot_id: str`.

**Guardrail G5 lives here.** Fewer than 30 contracts → reduced confidence; fewer
than 10 → `status = "insufficient_data"` and `median_annual_rent = None`, and the
agent must ask for the Ejari number rather than answer.

- [ ] **Step 1: Write the failing test**

```python
# tests/market/test_comparables.py
from decimal import Decimal

from bayyina.market.comparables import Comparables


def test_returns_median_for_a_well_populated_comparable(seeded_db):
    r = Comparables(seeded_db).median_rent("Al Barsha", "Flat", 2)
    assert r.status == "ok"
    assert r.median_annual_rent == Decimal("85000")
    assert r.contract_count >= 30


def test_insufficient_data_returns_no_number(seeded_db):
    r = Comparables(seeded_db).median_rent("Nowhere", "Villa", 9)
    assert r.status == "insufficient_data"
    assert r.median_annual_rent is None


def test_thin_comparable_reduces_confidence(seeded_db):
    thin = Comparables(seeded_db).median_rent("Thin Area", "Flat", 1)
    thick = Comparables(seeded_db).median_rent("Al Barsha", "Flat", 2)
    assert thin.confidence < thick.confidence
    assert thin.status == "ok"


def test_snapshot_id_is_recorded(seeded_db):
    assert Comparables(seeded_db).median_rent("Al Barsha", "Flat", 2).snapshot_id
```

Add a `seeded_db` fixture in `tests/market/conftest.py` creating a temporary
DuckDB with 40 Al Barsha 2-bed contracts around AED 85,000, 12 "Thin Area" 1-bed
contracts, and nothing for "Nowhere".

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/market/test_comparables.py -v`

- [ ] **Step 3: Implement ingest and comparables**

`ingest.py` reads the Dubai Pulse CSV into DuckDB with
`CREATE TABLE rent_contracts AS SELECT * FROM read_csv_auto(...)`, normalising
area, property type, bedrooms, annual rent and contract start date. Record a
`snapshots` row with `snapshot_id`, `computed_at`, `source`, `row_count`.

- [ ] **Step 4: Run and confirm the tests pass**

Run: `pytest tests/market -v`

- [ ] **Step 5: Run the real ingest and record the row count**

Run: `python -m bayyina.market.ingest data/raw/dld_rent_contracts.csv data/rent_contracts.duckdb`
Record the actual row count in `docs/CANVAS.md` box D — **this is a sourced
baseline figure.**

- [ ] **Step 6: Commit**

```bash
git add src/bayyina/market tests/market
git commit -m "feat: Dubai Pulse ingest and comparable medians with G5 thresholds"
```

---

## Task 11: API — evaluate, comparables, health

**Files:**
- Create: `src/bayyina/api/__init__.py`, `src/bayyina/api/app.py`,
  `src/bayyina/api/routes_evaluate.py`, `src/bayyina/guardrails/tokens.py`
- Test: `tests/api/test_evaluate.py`

**Interfaces:**
- Consumes: `Evaluator`, `Comparables`, `load_rules`.
- Produces: FastAPI app. `POST /evaluate`, `GET /comparables`, `GET /rules`,
  `GET /healthz`.
- Produces: `issue_token(payload: dict) -> str`, `verify_token(token, payload) -> bool`.

**Guardrails G3 and G7 are tested here.**

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_evaluate.py
from fastapi.testclient import TestClient

from bayyina.api.app import create_app

client = TestClient(create_app())


def _payload(**over):
    return {"rule_id": "rent_increase.dubai.decree_43_2013",
            "inputs": {"current_annual_rent": "85000",
                       "market_average_rent": "91000",
                       "proposed_annual_rent": "102000"},
            "confirmation_token": None, **over}


def test_evaluate_rejects_missing_confirmation_token():
    assert client.post("/evaluate", json=_payload()).status_code == 422


def test_evaluate_returns_verdict_with_citation():
    token = client.post("/agent/confirm",
                        json={"slots": _payload()["inputs"]}).json()["token"]
    body = client.post("/evaluate", json=_payload(confirmation_token=token)).json()
    assert body["verdict"] == "not_permitted"
    assert body["citation"]["clause"] == "Article 1"
    assert body["review_status"] == "provisional"


def test_healthz_reports_corpus_signature_state():
    body = client.get("/healthz").json()
    assert body["corpus_signed"] is True
    assert body["rule_count"] == 3
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/api/test_evaluate.py -v`

- [ ] **Step 3: Implement**

`create_app()` calls `load_rules(RULES_DIR)` at startup — **an unsigned corpus
raises `UnsignedRuleError` and the app does not start (G7)**. `/evaluate` requires
a non-null `confirmation_token` validated against the submitted slots (G3).

- [ ] **Step 4: Run and confirm the tests pass**

Run: `pytest tests/api -v`

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/api src/bayyina/guardrails tests/api
git commit -m "feat: evaluate API with G3 token gate and G7 boot check"
```

---

## Task 12: Provenance pages

**Files:**
- Create: `src/bayyina/api/routes_provenance.py`, `web/templates/provenance.html`
- Test: `tests/api/test_provenance.py`

Renders encoded logic beside the verbatim source clause, with the official link
and the signature. **This is how verifiability replaces authority** — see
[DESIGN.md](docs/DESIGN.md) §9.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_provenance.py
from fastapi.testclient import TestClient
from bayyina.api.app import create_app

client = TestClient(create_app())


def test_provenance_page_shows_clause_and_signature():
    html = client.get("/provenance/rent_increase.dubai.decree_43_2013").text
    assert "Article 1" in html
    assert "sha256:" in html
    assert "provisional" in html.lower()


def test_unknown_rule_returns_404():
    assert client.get("/provenance/nope").status_code == 404
```

- [ ] **Step 2: Run and confirm failure**
- [ ] **Step 3: Implement the route and Jinja template**
- [ ] **Step 4: Run and confirm the tests pass**
- [ ] **Step 5: Commit**

```bash
git commit -am "feat: public rule provenance pages"
```

---

## Task 12A: Evidence pack assembly

**Files:**
- Create: `src/bayyina/actions/__init__.py`, `src/bayyina/actions/evidence_pack.py`
- Test: `tests/actions/test_evidence_pack.py`

**Interfaces:**
- Consumes: `EvaluationRecord` from Task 8.
- Produces: `build_pack(records: list[EvaluationRecord], caller_ref: str) -> EvidencePack`
  with `pack_id`, `caller_ref`, `grounds: list[str]`, `evaluations`, `rule_versions`,
  `signatures`, `market_snapshot`, `generated_at`, `render_text() -> str`.

**This is action-layer step 2** — the agent stops answering and starts producing.

- [ ] **Step 1: Write the failing test**

```python
# tests/actions/test_evidence_pack.py
import pytest

from bayyina.actions.evidence_pack import build_pack


def test_pack_carries_every_rule_version_and_signature(rent_eval, notice_eval):
    pack = build_pack([rent_eval, notice_eval], caller_ref="ejari:12345")
    assert set(pack.rule_versions) == {
        "rent_increase.dubai.decree_43_2013",
        "notice_validity.dubai.law_26_2007_a14",
    }
    assert all(s.startswith("sha256:") for s in pack.signatures.values())


def test_pack_lists_each_independent_ground(rent_eval, notice_eval):
    pack = build_pack([rent_eval, notice_eval], caller_ref="ejari:12345")
    assert len(pack.grounds) == 2


def test_pack_refuses_to_build_with_no_adverse_finding(permitted_eval):
    with pytest.raises(ValueError):
        build_pack([permitted_eval], caller_ref="ejari:12345")


def test_rendered_pack_cites_every_clause(rent_eval, notice_eval):
    text = build_pack([rent_eval, notice_eval], "ejari:12345").render_text()
    assert "Article 1" in text
    assert "Article 14" in text
```

Add fixtures in `tests/actions/conftest.py` producing a `not_permitted` rent
evaluation, an `invalid` notice evaluation, and a `permitted` rent evaluation.

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/actions/test_evidence_pack.py -v`
Expected: FAIL — `ModuleNotFoundError: bayyina.actions.evidence_pack`

- [ ] **Step 3: Implement**

`build_pack` raises `ValueError` when no evaluation carries an adverse verdict —
**we never assemble a case that the rules do not support.** `render_text()`
produces the plain-text filing body, quoting each clause and its rule signature.

- [ ] **Step 4: Run and confirm the tests pass**

Run: `pytest tests/actions -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/actions tests/actions
git commit -m "feat: evidence pack assembly from evaluation records"
```

---

## Task 12B: Lodge to the officer review queue — guardrail G4

**Files:**
- Create: `src/bayyina/actions/review_queue.py`, `src/bayyina/api/routes_filing.py`
- Test: `tests/actions/test_review_queue.py`, `tests/api/test_filing.py`

**Interfaces:**
- Consumes: `EvidencePack`, `verify_token` from Task 11.
- Produces: `lodge(pack: EvidencePack, confirmation_token: str) -> QueuedCase`
  with `case_id`, `status="awaiting_officer_review"`, `lodged_at`, `pack_id`.
- Raises `MissingConfirmationError` when the token is absent or does not match.

**This is the human-in-the-loop enforcement.** There must be no code path that
files directly, and the test suite proves it.

- [ ] **Step 1: Write the failing test**

```python
# tests/actions/test_review_queue.py
import pytest

from bayyina.actions.review_queue import (
    lodge, MissingConfirmationError, QUEUE_TERMINAL_STATUSES,
)


def test_lodging_without_a_token_is_refused(sample_pack):
    with pytest.raises(MissingConfirmationError):
        lodge(sample_pack, confirmation_token=None)


def test_lodging_with_a_mismatched_token_is_refused(sample_pack):
    with pytest.raises(MissingConfirmationError):
        lodge(sample_pack, confirmation_token="not-the-right-token")


def test_lodged_case_awaits_an_officer(sample_pack, valid_token):
    case = lodge(sample_pack, valid_token)
    assert case.status == "awaiting_officer_review"


def test_no_status_reachable_by_the_agent_is_terminal(sample_pack, valid_token):
    """The agent can never move a case to a decided state."""
    case = lodge(sample_pack, valid_token)
    assert case.status not in QUEUE_TERMINAL_STATUSES
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/actions/test_review_queue.py -v`

- [ ] **Step 3: Implement**

`QUEUE_TERMINAL_STATUSES = frozenset({"approved", "rejected", "amended"})` — these
are set only by an officer through the review interface. `lodge()` has no
parameter that can produce them.

- [ ] **Step 4: Run and confirm the tests pass**

Run: `pytest tests/actions/test_review_queue.py tests/api/test_filing.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/actions/review_queue.py src/bayyina/api/routes_filing.py tests
git commit -m "feat: G4 two-key lodging into the officer review queue"
```

---

## Task 12C: Deadlines and consent — guardrail G8

**Files:**
- Create: `src/bayyina/actions/deadlines.py`, `src/bayyina/guardrails/consent.py`
- Test: `tests/actions/test_deadlines.py`, `tests/guardrails/test_consent.py`

**Interfaces:**
- Produces: `record_consent(call_id, granted: bool) -> ConsentRecord`;
  `opt_out(call_id) -> None`; `has_consent(call_id) -> bool`.
- Produces: `register_deadline(case_id, due: date, rule_id) -> Deadline`;
  `schedule_callback(case_id, call_id, days_before: int) -> Callback`, which
  raises `NoConsentError` when consent is absent or withdrawn.

**This is what makes Bayyina a coordination product rather than a lookup.** A
resident who learns on day 88 that they had 90 days has learned nothing useful.

- [ ] **Step 1: Write the failing test**

```python
# tests/actions/test_deadlines.py
from datetime import date

import pytest

from bayyina.actions.deadlines import schedule_callback, register_deadline
from bayyina.guardrails.consent import record_consent, opt_out, NoConsentError


def test_callback_requires_consent():
    register_deadline("case-1", date(2026, 4, 1), "notice_validity.dubai.law_26_2007_a14")
    with pytest.raises(NoConsentError):
        schedule_callback("case-1", call_id="call-1", days_before=7)


def test_callback_scheduled_when_consent_recorded():
    record_consent("call-2", granted=True)
    register_deadline("case-2", date(2026, 4, 1), "notice_validity.dubai.law_26_2007_a14")
    cb = schedule_callback("case-2", call_id="call-2", days_before=7)
    assert cb.scheduled_for == date(2026, 3, 25)


def test_opt_out_blocks_all_future_callbacks():
    record_consent("call-3", granted=True)
    opt_out("call-3")
    register_deadline("case-3", date(2026, 4, 1), "notice_validity.dubai.law_26_2007_a14")
    with pytest.raises(NoConsentError):
        schedule_callback("case-3", call_id="call-3", days_before=7)


def test_opt_out_is_recorded_in_the_audit_trail(audit_log):
    record_consent("call-4", granted=True)
    opt_out("call-4")
    assert any(e["event"] == "opt_out" for e in audit_log.entries("call-4"))
```

- [ ] **Step 2: Run and confirm failure**

Run: `pytest tests/actions/test_deadlines.py tests/guardrails/test_consent.py -v`

- [ ] **Step 3: Implement.** `opt_out` writes a suppression record that
      `has_consent` always honours — withdrawal is irreversible within a call.

- [ ] **Step 4: Run and confirm the tests pass**

- [ ] **Step 5: Commit**

```bash
git add src/bayyina/actions/deadlines.py src/bayyina/guardrails/consent.py tests
git commit -m "feat: G8 deadline tracking with consent-gated callbacks"
```

---

## Task 13: Public web checker

**Files:**
- Create: `web/index.html`, `web/checker.js`, `web/style.css`
- Modify: `src/bayyina/api/app.py` — mount static files

Two forms — rent increase and gratuity — calling `/comparables` and `/evaluate`.
Every result displays the verdict, the computed values, the cited clause with a
link to `/provenance/{rule_id}`, the market-average source, and the
`review_status: provisional` notice.

- [ ] **Step 1: Build the two forms and wire them to the API**
- [ ] **Step 2: Verify manually against three known cases** — a permitted
      increase, a refused increase, and an `insufficient_data` comparable
- [ ] **Step 3: Commit**

---

## Task 14: Deploy — this is Box N

**Files:**
- Create: `Dockerfile`, `.dockerignore`

- [ ] **Step 1: Write the Dockerfile** — Python 3.11 slim, install the package,
      copy `rules/`, `web/` and the built `data/rent_contracts.duckdb`, run uvicorn
- [ ] **Step 2: Deploy to a public host** (Railway, Render or Fly.io free tier)
- [ ] **Step 3: Verify `/healthz` reports `corpus_signed: true` in production**
- [ ] **Step 4: Record the live URL in `docs/CANVAS.md` box N**
- [ ] **Step 5: Commit**

```bash
git commit -am "feat: containerised deployment; box N link live"
```

---

## Task 15: Complete and submit the canvas

- [ ] **Step 1: Fill boxes A and M** with team details
- [ ] **Step 2: Fill box N** with the live URL and repository link
- [ ] **Step 3: Re-check the D↔J cross-reference** — every KPI in J measured
      against a figure that appears in D. Fix any drift
- [ ] **Step 4: Trim every box to its recorded word limit.** Text beyond the
      limit is not assessed — trim deliberately rather than letting it be cut
- [ ] **Step 5: Transcribe into the official template and submit before 23 September**
- [ ] **Step 6: Commit the final text**

```bash
git commit -am "docs: canvas submitted"
```

---

# PHASE 2 · 23–30 September · Build while waiting

Shortlist is announced 30 September. Do not idle for a week.

- [ ] **Task 16:** Build the agent skeleton on the ElevenLabs free tier — greet,
      disclose, triage, one slot-fill flow, English and Arabic. Proves the webhook
      tool contract works end to end before the sprint clock starts.
- [ ] **Task 17:** Implement `guardrails/triage.py` — the answerable-vs-interpretive
      classifier (G2) and distress detection (G6), with a labelled test set of at
      least 60 utterances per language covering both classes.
- [ ] **Task 18:** Write the Agent Testing suites **before** having the platform to
      run them on: primary flow, advice-seeking caller, contradictory numbers,
      mid-call language switch, distressed caller, and the filing-tool refusal
      test.
- [ ] **Task 19:** Storyboard the demo recording. It is built to pitch standard
      from the start — **if the team cannot travel, this recording is the pitch.**
- [ ] **Task 20:** Begin institutional outreach for a named pilot contact.

---

# PHASE 3 · 30 September – 14 October · Build sprint

Expanded into full TDD tasks on 30 September, once platform access lands. Planning
these in false detail now would be fiction — the exact shape depends on the
Workflows builder we have not yet used.

**Deliverables, fixed now:**

- [ ] Full six-node workflow with all seven guardrails enforced and demonstrable
- [ ] Malayalam, Hindi and Urdu added to English and Arabic
- [ ] Twilio telephony with a test number
- [ ] UAE Pass consent handshake, stubbed against the real design
- [ ] Agent Testing suites executed, multi-run pass rates recorded
- [ ] Post-call webhooks writing transcript + evaluation record to the audit store
- [ ] Demo recording: primary flow **through the full action layer** (check →
      assemble → lodge → track → consented callback), plus **three** failure
      paths: interpretive escalation, filing-tool refusal without a token, and
      **the live tamper demo** — change one digit in the rent band table, restart,
      and the service refuses to boot with `TamperedRuleError`
      ([DESIGN.md](docs/DESIGN.md) §5.5)
- [ ] One-page architecture diagram exported from ARCHITECTURE.md §2
- [ ] `README.md` condensed from ARCHITECTURE.md
- [ ] Submit by 14 October

---

# PHASE 4 · 14–26 October

- [ ] Harden against the failure modes the test suites surface
- [ ] Convert the pilot conversation into a named contact for the Stage 2
      "path to a named institutional pilot" criterion
- [ ] Rehearse the pitch; confirm the remote-participation answer from Task 0
- [ ] Appoint a reviewer if the mentor search succeeded, and move rule status from
      `provisional` to `certified`

---

## Self-Review Notes

Checked against DESIGN.md and ARCHITECTURE.md on 2026-09-07, after the action-layer
revision.

**Guardrail coverage — all nine have an implementing task:**

| Guardrail | Task |
|---|---|
| G1 citation-or-silence | Task 8 (citation mandatory in the record) |
| G2 interpretive tripwire | Task 17 |
| G3 confidence floor | Task 11 |
| G4 two-key filing | **Task 12B** — moved into Phase 1 |
| G5 stale / thin data | Task 10 |
| G6 distress detection | Task 17 |
| G7 unsigned-rule refusal | Task 4 |
| G8 consent and opt-out | **Task 12C** |
| G9 auditable lineage | Task 8 + Task 12C |

**Action-layer coverage** ([DESIGN.md](docs/DESIGN.md) §5.3): check → Task 8;
assemble → Task 12A; lodge → Task 12B; track and follow up → Task 12C. **All four
now sit in Phase 1**, because criterion 2 of the Track 2 filter makes them the
spine rather than a tail step. An earlier draft deferred filing to Phase 3; that
was the weakness the qualification filter caught.

**Resolved:** the `ApprovalStatus` mismatch flagged in the previous review.
ARCHITECTURE.md §5.2 now documents the three-state model
(`unsigned`/`provisional`/`certified`) that the plan implements.

**Type consistency:** `EvaluationRecord` (Task 8) is consumed by `build_pack`
(12A); `EvidencePack` by `lodge` (12B); `case_id` by `register_deadline` (12C).
`verify_token` is defined in Task 11 and reused in 12B. No orphan references.
