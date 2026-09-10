# Bayyina Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working product that a Dubai resident can call today — which
checks a rent increase against published rules, explains the answer in their
language, and puts an evidence pack in their hand before the call ends.

**Architecture:** Determinism at the core, language only at the edge. A signed
rules registry computes every verdict; the ElevenLabs agent diagnoses, speaks and
never computes. All market data is open. **No government permission is required
for any part of the product to work.**

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, DuckDB, SQLite, Jinja2,
WeasyPrint, pytest, ElevenLabs Agents, Twilio.

**Spec:** [docs/DESIGN.md](docs/DESIGN.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
· [docs/CANVAS.md](docs/CANVAS.md). Executors read DESIGN and ARCHITECTURE before
starting.

**The one sentence this plan serves:**

> Bayyina converts published tenancy rules into a safe, conversational workflow
> that determines what can be determined, produces the evidence a person needs to
> act, and stops whenever the facts require human judgement.

---

## Global Constraints

Every task's requirements implicitly include this section. A task that violates
one of these is wrong even if its tests pass.

### Correctness

- **The LLM never computes a verdict.** Arithmetic or rule interpretation in a
  prompt is wrong by construction.
- **No verdict without a citation.** Every evaluator return carries a non-null
  `citation`, or it is not a verdict.
- **The agent never submits to an authority.** Mode C has no concrete
  implementation. No agent-reachable case status may be terminal.
- **The evidence generator has no LLM in its call path.** It accepts structured
  evaluation records and renders templates. Nothing else.
- **Money is `Decimal`.** Rates and gaps may be `float`. Dates are `datetime.date`
  past the API boundary.
- **Rule statuses:** `unsigned` → service refuses to boot. `provisional` → loads,
  and the agent discloses it aloud. `certified` → requires a qualified reviewer.
  **We are `provisional` and we say so.**

### Non-functional — these are budgets, not aspirations

| Budget | Target | Why |
|---|---|---|
| **Our webhook latency** | **< 150 ms p95** | Voice quality and latency is 20% of Stage 2. Total first-audio target is < 1.5 s; STT, LLM and TTS consume the rest. **This forbids runtime aggregation over the contract dataset** |
| Rule evaluation | < 5 ms | Pure functions, corpus in memory at boot |
| Comparable lookup | < 20 ms | Pre-aggregated table, indexed. Never a `GROUP BY` over 9.8M rows at call time |
| Evidence pack render | < 2 s | Runs after the verdict is spoken, so it is off the critical path |
| Cost per completed call | < $0.50 all-in | Measured in T4.6, not assumed |
| Hosting | < $20 / month | Single container |

### Customer experience — non-negotiable

- **Answer first, reasoning second.** "The increase is not permitted" precedes
  "because your rent sits 5.9% below market."
- **Four conversational turns maximum** to collect seven slots. Every extra turn
  is an abandonment opportunity.
- **One batched readback**, not seven confirmations.
- **The pack is in the call's language.** An English PDF for a Malayalam caller is
  a failed delivery.
- **Friction proportional to risk.** No verification step exists unless it
  prevents a real harm.
- **Abandonment is tracked from the first deployed call**, not added later.

### Process

- **Every task ends with a Definition of Done that is checkable by someone else.**
- Tests before implementation. `ruff` clean. Small commits.
- **Do not commit unless explicitly asked.** Leave the tree dirty for review.

---

## Engineering Standards

Cross-cutting requirements. They are not tasks; they are conditions every task
must satisfy, and a reviewer may reject work that ignores them.

### Backend

| Standard | Requirement | Why it matters here |
|---|---|---|
| **Failure is a first-class path** | Every agent-facing tool defines its timeout, its retry policy, and **what the agent says when it fails**. No tool may fail silently | A webhook that hangs during a live call produces dead air. The caller hangs up and never returns |
| **Idempotency** | `/evidence-pack`, `/dispatch` and `/deadline` accept an `Idempotency-Key` and return the prior result on replay | Voice platforms retry on network blips. A retry must not send two SMS or bill twice |
| **Timeouts everywhere** | Every outbound call (Twilio, DB) has an explicit timeout. No unbounded waits | One slow dependency must not consume the 150 ms budget |
| **SQLite in WAL mode** | `PRAGMA journal_mode=WAL`, busy timeout set | Default SQLite locks under concurrent writes. Concurrent calls are the normal case |
| **Secrets never in git** | All credentials via environment; `settings.py` reads them; `.env.example` documents them with dummy values | Twilio and ElevenLabs keys leaking is an incident, not a bug |
| **Structured logging with a correlation id** | One `call_id` threads greeting → evaluations → pack → dispatch → reminder. JSON lines | Post-call analysis is a Stage 2 deliverable. It is impossible to reconstruct without this |
| **Public endpoints are rate-limited** | The web checker is unauthenticated and hits the database | An open endpoint over public data is an abuse vector |
| **Health checks are deep** | `/healthz` verifies corpus signature, DuckDB readable, aggregate table present, snapshot age within bounds | A green health check that lies is worse than none |
| **Schema migrations exist from day one** | Even for SQLite. Numbered, forward-only | "We will add migrations later" means data loss later |

### Frontend

| Standard | Requirement |
|---|---|
| **Mobile-first at 360 px** | Designed at 360 px, then widened. **Not** desktop-tolerated-on-mobile — the audience is phone-first |
| **RTL is layout, not fonts** | Arabic sets `dir="rtl"` and mirrors the whole layout. Test it; do not assume a font swap suffices |
| **Every async action has three states** | Idle, loading, error. A silent failure on a rights check is a broken promise |
| **Validate before the round trip** | Never make the user wait for a 422 they could have been told about instantly |
| **`HUMAN_REVIEW_REQUIRED` is a designed state** | It is a legitimate outcome with its own layout and next steps — never an error page or an empty result |
| **Contrast and tap targets** | WCAG AA contrast; 44 px minimum targets. This audience includes older and low-literacy users |
| **No build step** | Static HTML/CSS/JS served by the same container. Toolchain complexity buys nothing at this scale |

### Content and documentation

| Standard | Requirement |
|---|---|
| **One glossary, three languages** | Every rule term, state name and UI label is defined once and reused across voice scripts, PDF templates, web copy and docs |
| **Translation is reviewed by a speaker** | Machine-translated legal-adjacent copy is a liability. Arabic and Malayalam get human review |
| **The provenance page is a documented product feature** | It is written, not merely rendered |
| **Decisions are recorded** | `docs/DECISIONS.md` — one line per material choice, with the date and the reason |

---

## The Customer Journey

This precedes the task list deliberately. Everything below is built to serve it,
and any task that degrades it is wrong.

| Stage | What the resident experiences | What must be true | Failure mode we design against |
|---|---|---|---|
| **Discovery** | Finds the web checker or the number | The web checker works standalone and answers the same question | An unusable product behind a phone number nobody has |
| **First 15 seconds** | Greeting, AI disclosure, recording notice | Disclosure is **≤ 8 seconds spoken**, complete, and in their language | Thirty seconds of legalese loses the caller before the value lands |
| **Language** | Speaks; is answered in kind | Auto-detect on the first utterance, plus an explicit recovery line offering the three languages | Wrong-language detection strands the caller silently |
| **Diagnosis** | Is asked ~4 questions, conversationally | Slots grouped naturally: *"What are you paying now, and what are they asking for?"* | Seven sequential questions reads as a form and loses people |
| **Confirmation** | Hears everything read back once | One batched readback, then confirm | Seven confirmations doubles call length |
| **The answer** | Hears the verdict, then why | **Answer first.** Clause cited after | Burying the answer under reasoning |
| **Thin data** | Told plainly that the comparison is unreliable | Names the limit, offers the Ejari path, **still delivers the notice check** | A dead end that leaves the caller with nothing |
| **The artifact** | Receives an SMS with the pack, on the call | Pack in their language. Delivery to the calling number needs no OTP — **being on the call proves control of it** | Verification friction that costs more than it protects |
| **After** | Reminder before the statutory deadline | Explicit opt-in, easy opt-out | Contact they did not ask for |
| **Escalation** | Told clearly a human is needed and why | Never a silent dead end | "I can't help with that." Full stop. |

### The two moments that decide whether this product is used

1. **Seconds 0–15.** Compliance disclosure and customer retention pull in opposite
   directions here. Resolve it by compressing the spoken disclosure to its legally
   necessary core and putting the full text in the pack — *not* by shortening what
   we disclose.
2. **The SMS arriving while still on the call.** This is the moment the product
   stops being a conversation and becomes a thing they own. If the pack arrives
   after the call, the moment is lost.

---

## Delivery Strategy — walking skeleton first

**We do not build the registry, then the data, then the API, then the frontend.**
That sequence discovers integration problems last, when they are most expensive.

Instead: **Phase 1 ships a thin end-to-end slice to a public URL within days** —
one signed rule, a manually supplied comparable, a plain web form, a real verdict.
It is deployed and reachable. That single decision:

- satisfies **Box N** (a working link, which scores zero without one) early
- proves deploy, config and boot-time guardrails before they can block anything
- gives every later phase somewhere to land instead of a big-bang integration

Then each layer thickens against a running system.

```
Phase 1  ▓░░░░░  thin slice, deployed          → Box N safe
Phase 2  ▓▓▓░░░  real data, real artifact      → the product exists
Phase 3  ▓▓▓▓▓░  voice                          → the competition build
Phase 4  ▓▓▓▓▓▓  evidence, demo, hardening      → Stage 2 submission
```

## Workstreams

Four tracks run in parallel. **Only Track A is the critical path** — the others
are sized to finish before they are needed, and none of them can block a deploy.

| Track | Owns | Depends on | Idle risk |
|---|---|---|---|
| **A · Core** | Registry, rule logic, evaluator, API, deploy | Nothing | **This is the critical path.** Protect it |
| **B · Data** | Dubai Pulse ingest, validation, aggregation, comparables | T0.3 credentials only | Blocked until credentials land — start the bulk CSV immediately |
| **C · Surface** | Design system, web checker, provenance pages, evidence templates, PDF | A's `/evaluate` contract (fixed at T1.7) | Can begin on the contract before the implementation exists |
| **D · Submission** | Canvas, baselines, organiser questions, glossary, README | Nothing | **Fully independent. Start it on day one and never let it become a week-three panic** |

**Interface freeze:** the `/evaluate` request and response shapes are fixed at
T1.7 and must not change afterwards without telling Track C. That single agreement
is what lets frontend and backend proceed without waiting on each other.

### Sequencing rules

1. **Track A never waits.** If B, C or D block, A continues.
2. **Ship Phase 1 before starting Phase 2.** A deployed thin slice beats an
   undeployed thick one.
3. **Track D has its own deadline chain** ending 21 September, two days before the
   canvas closes. The canvas is not a side-effect of engineering; it is the
   Stage 1 deliverable.
4. **A blocked customer gate stops the phase.** T2.8 failing is not a
   nice-to-have — it is a stop.

### Calendar

Today is **9 September 2026**. Stage 1 closes **23 September** — 14 days.

| Phase | Window | Gate to pass |
|---|---|---|
| **0** | 9–11 Sep | Unblocked; scripts and glossary written |
| **1** | 11–15 Sep | **Public URL live.** Box N satisfied |
| **2** | 15–21 Sep | Real comparables, evidence pack, provenance, comprehension passed |
| **Canvas** | 21–23 Sep | **Submit** |
| **3a** | 23–30 Sep | Voice skeleton on the free tier while awaiting the shortlist |
| **3b** | 30 Sep–10 Oct | Full agent, three languages, all guardrails |
| **4** | 10–14 Oct | Test evidence, demo recording, README. **Submit** |
| **Harden** | 14–26 Oct | Latency, pilot outreach, rehearsal |

### Stage gates — pass or do not proceed

| Gate | Date | Criterion | If it fails |
|---|---|---|---|
| **G-A · Deployed** | 15 Sep | Public URL returns a correct verdict; `/healthz` green | Stop all Phase 2 work. Nothing matters more than this |
| **G-B · Canvas** | 21 Sep | All 14 boxes within word limits; D↔J consistent; N has a link | Submit what exists. A submitted imperfect canvas beats a perfect unsubmitted one |
| **G-C · Comprehension** | 20 Sep | Two non-English readers state verdict and next step unaided | **Blocking.** Fix templates before any voice work |
| **G-D · Latency** | 8 Oct | p95 first audio < 1.5 s | Cut scope, not the budget. Latency is 20% of Stage 2 |
| **G-E · Demo** | 13 Oct | Recording runs end to end plus three failure paths, unedited | Re-record. This is the pitch if we cannot travel |

### If we are not shortlisted on 30 September

**The product still ships.** Mode A depends on nothing the competition provides.
Phase 3 continues on the free tier at reduced scope, and Track D pivots from canvas
to launch. This is stated so the decision is already made rather than debated on
the day.

---

## File Structure

```
IgNyte/
├── plan.md · README.md
├── docs/            DESIGN · ARCHITECTURE · GLOSSARY · DECISIONS · CANVAS
├── agent/           scripts/{en,ar,ml}/ · workflows/ · tests/
│
├── backend/         PYTHON — the rules engine and API
│   ├── pyproject.toml · .env.example
│   ├── rules/       THE CORPUS — signed, versioned YAML
│   ├── scripts/     sign_rule · verify_corpus · explore
│   ├── src/bayyina/
│   │   ├── registry/    schema · signing · loader · evaluator
│   │   ├── rules_logic/ banded_percentage · notice_period
│   │   ├── market/      ingest · aggregate · comparables
│   │   ├── evidence/    pack · render · templates/{en,ar,ml}/
│   │   ├── guardrails/  triage · tokens · consent
│   │   ├── store/       db · migrations · cases · consent · deadlines
│   │   ├── audit.py · settings.py · observability.py
│   │   └── api/         app · routes_{evaluate,agent,evidence,provenance}
│   ├── tests/       mirrors src/
│   └── data/        parquet + duckdb (gitignored)
│
└── frontend/        VITE + REACT + TYPESCRIPT
    ├── package.json · vite.config.ts · tsconfig*.json
    └── src/
        ├── api/     typed client
        ├── i18n/    locales/{en,ar,ml}.json
        ├── test/    setup
        └── components/
```

**Two toolchains, one deployment.** `frontend/` builds to static assets that
`backend/` serves in production, so the split costs nothing at deploy time. In
development the Vite dev server proxies `/api` to the backend, so **there is no
CORS configuration to maintain in either environment**.

**Principle:** files that change together live together. `registry/` changes when
the rule model changes; `rules_logic/` when a rule type is added; `evidence/` when
the document changes. Independent, therefore separate.

---

# PHASE 0 · Foundations

No code. Every item unblocks something later, and T0.6 gates all voice work.

## T0.1 — Canvas template and word limits

- [x] Download the official ElevenLabs Idea Canvas template
- [x] Record the **exact word limit for each of the 14 boxes** into the status
      tracker in `docs/CANVAS.md`, replacing every *from template* placeholder
- [x] Count the current draft of each box and record it beside the limit

**DoD:** No `*from template*` string remains in `docs/CANVAS.md`, and every box
shows `current / limit`.

## T0.2 — Organiser questions

- [ ] **STILL OPEN** — post on the Discussion tab: *"Is remote participation available
      for finalists at Demo Day on 26–27 October?"*
- [x] ~~Ask whether boxes accept tables~~ — **answered by the template itself**: D, F, I, J, K, M, N and P are printed as tables. (was: boxes D, I and J are
      currently drafted as tables)

**DoD:** Both posted. The second matters — if tables are disallowed, boxes D, I
and J need reformatting, and finding that out on 22 September is a crisis.

## T0.3 — Dubai Pulse access

- [x] Register at `dubaipulse.gov.ae`; request `dld_rent_contracts-open`
- [x] **In parallel, download the bulk CSV** — never block T2.1 on OAuth onboarding
- [x] Record dataset row count, column names and date range in `docs/CANVAS.md` box D

**DoD:** A local CSV exists and its schema is documented. Do this on day one;
credential turnaround is not instant.

## T0.4 — Baseline verification

- [x] Verify the RDC filing fee against the DLD published schedule
- [x] Verify DLD service standards for time-to-answer
- [x] Attempt RDC annual case volume and bounce rate from DLD annual reports
- [x] Move anything found into box D **Verified**; leave the rest as declared
      hypotheses with a measurement route

**DoD:** At least **two** additional rows move from hypothesis to verified.
Sourcing these is worth more than any feature.

## T0.5 — Legal reviewer outreach

- [ ] Search the Ignyte mentor directory (550+ mentors) for legal or regtech advisors
- [ ] Request a one-off advisory review of two rule encodings
- [ ] If accepted, plan for `certified`; if not, `provisional` stands and is disclosed

**DoD:** At least three approaches made and logged.

## T0.6 — Customer journey and conversation scripts ⚠ GATES ALL VOICE WORK

The scripts are a **deliverable**, not improvisation at build time.

- [x] Write `agent/scripts/en/` covering: greeting and disclosure (**≤ 8 seconds
      spoken — read it aloud with a timer**), language recovery, the four
      diagnosis turns, the batched readback, answer-first verdict delivery for
      each of the three states, the G5 thin-data script
      ([ARCHITECTURE.md](docs/ARCHITECTURE.md) §6.1), the G2 interpretive
      escalation, the G6 distress handoff, pack dispatch, and deadline opt-in
- [x] Map the seven rent slots into **four** conversational turns
- [x] Read every script aloud and time it. Anything over budget gets cut

**DoD:** A reviewer who has never seen the project can read the script set and
run the whole call by hand. Every turn has a purpose and a time cost.

## T0.7 — Budgets, written down

- [x] Record the latency budget table in `README.md` as a stated commitment
- [x] Instrument targets: which spans get timed, which percentile is reported

**DoD:** The budgets exist as a document a reviewer can hold us to.

## T0.8 — Glossary and content style guide ⚠ GATES ALL COPY · Track D

Three languages, legal-adjacent copy, four surfaces (voice, PDF, web, docs).
**Without one source of truth for terminology, they will drift** — and drift in a
compliance product reads as carelessness.

- [x] Create `docs/GLOSSARY.md` defining, in English, Arabic and Malayalam:
      every rule term (permitted increase, market average, notice period,
      shortfall), the three states (CLEAR / CLEAR WITH CONDITIONS / HUMAN REVIEW
      REQUIRED), and the standing disclosures (AI identity, recording, not legal
      advice, provisional review status)
- [x] Fix the register: plain language, short sentences, **no legal jargon we do
      not define on the spot**
- [x] Rule: **the same concept uses the same word everywhere.** Not "verdict" in
      the API, "result" in the PDF and "answer" on the web

**DoD:** Every user-visible string in the project can be traced to a glossary
entry. A translator can work from this file alone.

## T0.9 — Secrets, environments and the decision log · Track A

- [x] `.env.example` documenting every variable with dummy values — Twilio SID and
      token, ElevenLabs key, base URL, environment name
- [x] Confirm `.gitignore` covers `.env`, `data/raw/`, `*.duckdb`
- [x] Define two environments: `local` and `production`. No staging — it would add
      ceremony without adding safety at this size
- [x] Create `docs/DECISIONS.md` and seed it with the decisions already made:
      Mode C unimplemented; gratuity deferred; OTP only for a different number;
      pre-aggregated comparables for latency; `provisional` rule status

**DoD:** A new engineer can run the project from `.env.example` alone, and can
read why the five load-bearing decisions were made without asking.

## T0.10 — Primary research for Boxes F and G 🔴 **STAGE 1 CRITICAL PATH**

**Added 2026-09-09** after the real canvas template arrived. The brief described
14 boxes; the template has 17, and **Box F requires named, verifiable
conversations with people inside the institution type.** It was not in this plan
because we did not know it existed.

> *"We may contact them. Desk research alone scores in the bottom band."*
> *"If nothing changed, you have not spoken to enough people."*

Boxes F and G sit inside the **25% problem-fit** criterion. They cannot be
fabricated and they cannot be built by an engineer. **This is now the single
highest-value task in the project**, above all code.

- [ ] Search the Ignyte mentor directory in this order: **PropTech founders**
      (they have hit the DLD data wall and can speak to both the problem and the
      data), property and facilities management (**they issue the notices**),
      anyone with DLD/RERA/government background, then legal and compliance
- [ ] **Message six to eight people.** Cold response rates are low; three
      conversations are needed
- [ ] Run each as **20 minutes of listening, not pitching.** Five questions:
      where does it go wrong first · how much of what reaches you could have been
      settled by checking the index · when a case arrives incomplete what is
      missing · what do you wish tenants knew · what would stop you using this
- [ ] **Ask permission to name them** — Ignyte may contact them
- [ ] Record name, role, organisation type, date, and **the one thing they said
      that changed the idea** directly into `docs/CANVAS.md` box F
- [ ] Write box G **only after**: the assumption that turned out false, and what
      changed. **Do not fabricate this box** — it exists to catch teams who
      skipped the research

**DoD:** Three named conversations in box F with dates, and a box G that names a
real assumption we abandoned. **Target 18 September**, five days before close.

**Note:** T0.5 (legal reviewer) uses the same directory and the same outreach.
One effort serves both.

---

# PHASE 1 · Walking Skeleton → deployed

**Goal: a public URL that computes a real verdict from a signed rule.** Ship it
before adding depth.

## T1.1 — Scaffold, settings, CI

**Files:** `pyproject.toml`, `src/bayyina/__init__.py`, `src/bayyina/settings.py`,
`.github/workflows/ci.yml`, `.gitignore`
**Test:** `tests/test_scaffold.py`

- [x] **Write the failing test**

```python
# tests/test_scaffold.py
def test_package_imports():
    import bayyina

    assert bayyina.__version__


def test_settings_have_required_paths(tmp_path):
    from bayyina.settings import Settings

    s = Settings(rules_dir=tmp_path, data_dir=tmp_path)
    assert s.rules_dir == tmp_path
```

- [x] **Run it, confirm failure:** `pytest tests/test_scaffold.py -v` →
      `ModuleNotFoundError: No module named 'bayyina'`

- [x] **Create the package**

```toml
# pyproject.toml
[project]
name = "bayyina"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7", "pydantic-settings>=2.3", "fastapi>=0.111",
  "uvicorn[standard]>=0.30", "pyyaml>=6.0", "duckdb>=1.0",
  "jinja2>=3.1", "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.5"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

```python
# src/bayyina/settings.py
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    rules_dir: Path = Path("rules")
    data_dir: Path = Path("data")
    market_snapshot_max_age_days: int = 120
    min_contracts_for_answer: int = 10
    min_contracts_for_full_confidence: int = 30
```

> **Note added at T1.4.** An early draft of this block carried
> `notice_required_days: int = 90`. It was removed: the 90 days are a property of
> Law 26/2007 Article 14, not an operational choice, and holding a rule parameter
> in configuration would let an operator change the law by editing an environment
> variable while the rule signature still verified (D-027). Rule parameters live
> in the signed rule file. G5 thresholds stay here, because they are our choices
> about when we decline to answer.

- [x] **Run, confirm pass:** `pytest -v` → 2 passed
- [x] **Add CI** running `ruff check .` and `pytest` on every push

**DoD:** CI green on a clean checkout. `pip install -e ".[dev]"` works from zero.

---

## T1.2 — Rule schema, signing, loader (G7)

**Files:** `src/bayyina/registry/{schema,signing,loader}.py`, `scripts/sign_rule.py`,
`scripts/verify_corpus.py`
**Test:** `tests/registry/test_{schema,signing,loader}.py`

**Interfaces produced:**
- `Rule`, `RuleSource`, `RuleApproval`, `Band`, `ApprovalStatus`
- `Rule.body_for_signing() -> dict` — the rule minus its approval block
- `rule_digest(rule) -> str` returning `"sha256:<hex>"`; `verify_signature(rule) -> bool`
- `load_rules(directory) -> dict[str, Rule]`; `UnsignedRuleError`, `TamperedRuleError`

**This is the moat and the wow moment. Build it first and build it properly.**

- [x] **Write the failing tests**

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
        "verbatim": "Sets maximum…",
    },
    "logic": "banded_percentage",
    "inputs": {},
    "bands": [
        {"gap_from": 0.0, "gap_to": 0.10, "max_increase": 0.0},
        {"gap_from": 0.10, "gap_to": None, "max_increase": 0.20},
    ],
    "review_notes": [],
    "approval": {"status": "unsigned", "approved_by": None, "approved_at": None, "signature": None},
}


def test_parses_minimal_rule():
    assert Rule.model_validate(MINIMAL).approval.status is ApprovalStatus.UNSIGNED


def test_body_for_signing_excludes_approval():
    body = Rule.model_validate(MINIMAL).body_for_signing()
    assert "approval" not in body and body["version"] == 1


def test_citation_clause_is_mandatory():
    with pytest.raises(Exception):
        Rule.model_validate({**MINIMAL, "source": {**MINIMAL["source"], "clause": None}})


def test_unknown_field_is_rejected():
    """A typo in a rule file must fail loudly, not be silently ignored."""
    with pytest.raises(Exception):
        Rule.model_validate({**MINIMAL, "band": []})
```

```python
# tests/registry/test_signing.py
from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest, verify_signature
from tests.registry.test_schema import MINIMAL


def _rule(**over):
    return Rule.model_validate({**MINIMAL, **over})


def test_digest_is_stable():
    assert rule_digest(_rule()) == rule_digest(_rule())


def test_digest_changes_when_a_band_changes():
    tampered = _rule(bands=[{"gap_from": 0.0, "gap_to": 0.10, "max_increase": 0.99}])
    assert rule_digest(_rule()) != rule_digest(tampered)


def test_digest_ignores_the_approval_block():
    signed = _rule(
        approval={
            "status": "provisional",
            "approved_by": "team",
            "approved_at": "2026-09-09T00:00:00Z",
            "signature": "sha256:anything",
        }
    )
    assert rule_digest(_rule()) == rule_digest(signed)


def test_verify_accepts_a_matching_signature():
    good = _rule(
        approval={
            "status": "provisional",
            "approved_by": "team",
            "approved_at": "2026-09-09T00:00:00Z",
            "signature": rule_digest(_rule()),
        }
    )
    assert verify_signature(good) is True


def test_verify_rejects_a_tampered_body():
    bad = _rule(
        bands=[{"gap_from": 0.0, "gap_to": 0.10, "max_increase": 0.99}],
        approval={
            "status": "provisional",
            "approved_by": "team",
            "approved_at": "2026-09-09T00:00:00Z",
            "signature": rule_digest(_rule()),
        },
    )
    assert verify_signature(bad) is False
```

```python
# tests/registry/test_loader.py
import pytest, yaml
from bayyina.registry.loader import load_rules, UnsignedRuleError, TamperedRuleError
from bayyina.registry.schema import Rule
from bayyina.registry.signing import rule_digest
from tests.registry.test_schema import MINIMAL


def _signed(data):
    out = {
        **data,
        "approval": {
            "status": "provisional",
            "approved_by": "team",
            "approved_at": "2026-09-09T00:00:00Z",
            "signature": None,
        },
    }
    out["approval"]["signature"] = rule_digest(Rule.model_validate(out))
    return out


def _write(tmp_path, data, name="r.v1.yaml"):
    (tmp_path / name).write_text(yaml.safe_dump(data), encoding="utf-8")
    return tmp_path


def test_refuses_an_unsigned_rule(tmp_path):
    with pytest.raises(UnsignedRuleError):
        load_rules(_write(tmp_path, MINIMAL))


def test_refuses_a_tampered_rule(tmp_path):
    data = _signed(MINIMAL)
    data["bands"][0]["max_increase"] = 0.99  # tampered after signing
    with pytest.raises(TamperedRuleError):
        load_rules(_write(tmp_path, data))


def test_loads_a_signed_rule(tmp_path):
    rules = load_rules(_write(tmp_path, _signed(MINIMAL)))
    assert "rent_increase.dubai.decree_43_2013" in rules


def test_error_names_the_offending_file(tmp_path):
    """An operator must be able to fix this from the message alone."""
    with pytest.raises(UnsignedRuleError, match="r.v1.yaml"):
        load_rules(_write(tmp_path, MINIMAL))
```

- [x] **Run, confirm all fail** with `ModuleNotFoundError`

- [x] **Implement `schema.py`** — Pydantic models with `extra="forbid"` on every
      model so a typo in a rule file fails loudly. `clause`, `verbatim` and `url`
      are required on `RuleSource`.

- [x] **Implement `signing.py`**

```python
# src/bayyina/registry/signing.py
import hashlib, json
from bayyina.registry.schema import Rule


def _canonical_bytes(body: dict) -> bytes:
    """Deterministic serialisation: sorted keys, no incidental whitespace."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def rule_digest(rule: Rule) -> str:
    body = _canonical_bytes(rule.body_for_signing())
    return f"sha256:{hashlib.sha256(body).hexdigest()}"


def verify_signature(rule: Rule) -> bool:
    if not rule.approval.signature:
        return False
    return rule.approval.signature == rule_digest(rule)
```

- [x] **Implement `loader.py`** — raise `UnsignedRuleError` on
      `ApprovalStatus.UNSIGNED`, `TamperedRuleError` on digest mismatch. **Both
      messages name the file and the rule id**, because an operator fixes this
      from the message alone.

- [x] **Write `scripts/sign_rule.py` and `scripts/verify_corpus.py`** per
      [ARCHITECTURE.md](docs/ARCHITECTURE.md) §5.2.1. `verify_corpus.py` exits
      non-zero on any mismatch.

- [x] **Add `python scripts/verify_corpus.py rules/` to CI** — a rule edited
      without re-signing now fails the build

- [x] **Run:** `pytest tests/registry -v` → all pass

**DoD:** Editing one digit in a signed rule file makes CI fail *and* makes the
loader raise. Demonstrate both by hand — **this is the wow moment and it must work
on the first try on stage.**

---

## T1.3 — Rent increase logic

**Files:** `src/bayyina/rules_logic/banded_percentage.py`
**Test:** `tests/rules_logic/test_banded_percentage.py`

**Interface produced:** `evaluate(current_annual_rent, market_average_rent,
proposed_annual_rent, bands) -> BandedResult(verdict, gap_pct, band_matched,
max_increase_pct, max_lawful_rent, proposed_increase_pct)`

Band semantics: ascending; the first band whose `gap_to` is `None` or `>= gap`
matches. Gap 0.10 → band 0 (0%); gap 0.1001 → band 1 (5%).

- [x] **Write the failing test**

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
    "current,market,band,cap",
    [
        (Decimal("100000"), Decimal("100000"), 0, 0.00),  # at market
        (Decimal("90000"), Decimal("100000"), 0, 0.00),  # exactly 10% below
        (Decimal("89000"), Decimal("100000"), 1, 0.05),  # just past 10%
        (Decimal("80000"), Decimal("100000"), 1, 0.05),  # exactly 20%
        (Decimal("70000"), Decimal("100000"), 2, 0.10),  # exactly 30%
        (Decimal("60000"), Decimal("100000"), 3, 0.15),  # exactly 40%
        (Decimal("50000"), Decimal("100000"), 4, 0.20),  # 50% below
    ],
)
def test_every_band_boundary(current, market, band, cap):
    r = evaluate(current, market, current, BANDS)
    assert r.band_matched == band
    assert r.max_increase_pct == pytest.approx(cap)


def test_rent_above_market_permits_no_increase():
    r = evaluate(Decimal("120000"), Decimal("100000"), Decimal("125000"), BANDS)
    assert r.band_matched == 0 and r.verdict == "not_permitted"


def test_the_canonical_demo_case():
    """80k current, 85k market, 96k proposed -> 5.9% gap, 0% permitted."""
    r = evaluate(Decimal("80000"), Decimal("85000"), Decimal("96000"), BANDS)
    assert r.verdict == "not_permitted"
    assert r.gap_pct == pytest.approx(0.0588, abs=0.001)
    assert r.max_lawful_rent == Decimal("80000.00")


def test_permitted_when_within_cap():
    r = evaluate(Decimal("50000"), Decimal("100000"), Decimal("60000"), BANDS)
    assert r.verdict == "permitted" and r.max_lawful_rent == Decimal("60000.00")


def test_one_dirham_over_the_cap_is_not_permitted():
    r = evaluate(Decimal("50000"), Decimal("100000"), Decimal("60000.01"), BANDS)
    assert r.verdict == "not_permitted"


@pytest.mark.parametrize(
    "market,current",
    [
        (Decimal("0"), Decimal("50000")),
        (Decimal("100000"), Decimal("0")),
    ],
)
def test_non_positive_inputs_are_rejected(market, current):
    with pytest.raises(ValueError):
        evaluate(current, market, Decimal("60000"), BANDS)
```

- [x] **Run, confirm failure**
- [x] **Implement** — `gap = max(0.0, (market - current) / market)`; first matching
      band wins; `max_lawful_rent` quantised to cents with `ROUND_HALF_UP`
- [x] **Run, confirm pass** — 13 passed

**DoD:** Every band boundary tested on both sides. The demo case is a named test,
so a regression that breaks the stage demo fails CI.

---

## T1.4 — Notice validity logic

**Files:** `src/bayyina/rules_logic/notice_period.py`
**Test:** `tests/rules_logic/test_notice_period.py`

**Interface produced:** `evaluate(contract_expiry, notice_served, required_days)
-> NoticeResult(verdict, days_notice, required_days, shortfall_days)`

- [x] **Write the failing test**

```python
# tests/rules_logic/test_notice_period.py
from datetime import date
import pytest
from bayyina.rules_logic.notice_period import evaluate


@pytest.mark.parametrize(
    "served,verdict,days",
    [
        (date(2026, 1, 1), "valid", 90),  # exactly 90
        (date(2025, 12, 1), "valid", 121),
        (date(2026, 1, 2), "invalid", 89),  # one day short
        (date(2026, 3, 1), "invalid", 31),
    ],
)
def test_the_ninety_day_boundary(served, verdict, days):
    r = evaluate(date(2026, 4, 1), served, 90)
    assert (r.verdict, r.days_notice) == (verdict, days)


def test_the_canonical_demo_case():
    """Expiry 30 Nov, served 20 Sep -> 71 days, insufficient."""
    r = evaluate(date(2026, 11, 30), date(2026, 9, 20), 90)
    assert r.verdict == "invalid" and r.days_notice == 71 and r.shortfall_days == 19


def test_valid_notice_has_zero_shortfall():
    assert evaluate(date(2026, 4, 1), date(2026, 1, 1), 90).shortfall_days == 0


def test_notice_served_after_expiry_is_invalid():
    r = evaluate(date(2026, 4, 1), date(2026, 5, 1), 90)
    assert r.verdict == "invalid" and r.days_notice < 0
```

- [x] **Run, confirm failure**
- [x] **Implement** — `days_notice = (expiry - served).days`;
      `shortfall = max(0, required - days_notice)`
- [x] **Run, confirm pass** — 7 passed

**DoD:** The 89/90/91 boundary is explicit. The demo case is a named test.

---

## T1.5 — Evaluator and evaluation record

**Files:** `src/bayyina/registry/evaluator.py`, `src/bayyina/audit.py`
**Test:** `tests/registry/test_evaluator.py`, `tests/test_audit.py`, `tests/conftest.py`

**Interfaces produced:**
- `EvaluationRecord` — Pydantic, per [ARCHITECTURE.md](docs/ARCHITECTURE.md) §5.4.
  **`citation` is non-nullable** and every field inside it has a minimum length
- `Citation.from_rule(rule)`, `MarketEvidence(contract_count, snapshot_id)`,
  `OutcomeState` — `CLEAR` / `CLEAR_WITH_CONDITIONS` / `HUMAN_REVIEW_REQUIRED`
- `Evaluator(rules, *, settings=None).evaluate(rule_id, inputs, input_sources, *, market=None)`
- `AuditLog.append(record)` — append-only, hash-chained; `verify_chain()`

- [x] **Write the failing tests** — 37 for the evaluator, 10 for the audit log
- [x] **Run, confirm failure** — `ModuleNotFoundError: bayyina.registry.evaluator`
- [x] **Implement** — dispatch on `rule.logic` through `_DISPATCH`, which a test
      asserts is total over `RuleLogic`; `eval_id` is `ev_` + uuid4; `created_at`
      is UTC-aware. Inputs are coerced by their declared type, and money given as
      a float is refused
- [x] **Enforce G5 structurally** — below the evidence threshold the rule is not
      run, and the record type refuses a `HUMAN_REVIEW_REQUIRED` record carrying
      a verdict, a computed figure, or a confidence number (D-030)
- [x] **Enforce G9** — every supplied input must carry a recorded source; the
      audit log chains each entry to the digest of the one before it (D-032)
- [x] **Prove the guardrails fail when broken** — deleting the state validator,
      the citation minimum length, the provenance check, or the record from the
      chain digest each turns its test red
- [x] **Run, confirm pass** — 152 backend tests

**DoD:** `EvaluationRecord` cannot be constructed without a citation. That is G1,
enforced by a type rather than a habit. ✅ And a record cannot claim human review
while carrying a number — G5, same mechanism.

---

## T1.6 — Write and sign the two rules

**Files:** `rules/rent_increase.dubai.decree_43_2013.v1.yaml`,
`rules/notice_validity.dubai.law_26_2007_a14.v1.yaml`
**Test:** `tests/test_corpus.py`

> **Run before T1.5.** T1.5's tests load the production corpus rather than a
> stub, and T1.6 depends on nothing T1.5 produces (D-033).

- [x] **Write the failing test** — `rules/` was empty, so `EmptyCorpusError`
- [x] **Write both YAML files** per [ARCHITECTURE.md](docs/ARCHITECTURE.md) §5.1.
      `approval.status: provisional`. Twelve `review_notes` between them, each an
      open question a reviewer must close (D-029)
- [x] **Sign both:** `python scripts/sign_rule.py rules/<file>.yaml`
- [x] **Keep the signed file readable** — the signer re-emits multi-line strings
      in block style, so a five-clause verbatim quote survives as a readable diff
- [x] **Remove `--allow-empty` from the CI corpus step.** The corpus now exists,
      so an empty `rules/` means a deleted file or a container build that did not
      copy it. That must turn CI red rather than pass
- [x] **Run, confirm pass** — 8 corpus tests

**DoD:** `verify_corpus.py rules/` exits zero and prints both signatures. ✅
Both rules render complete provenance. The tamper demo runs against the real
corpus: one digit changed → `CORPUS REJECTED`, exit 1.

---

## T1.7 — API: `/evaluate` and `/healthz`

**Files:** `src/bayyina/api/{app,routes_evaluate}.py`, `src/bayyina/observability.py`,
`src/bayyina/rules_logic/errors.py`
**Test:** `tests/api/test_evaluate.py`, `tests/api/test_boot.py`

**Interfaces produced:**
- `create_app(*, rules_dir=None, audit_path=None, settings=None) -> FastAPI` —
  loads and verifies the corpus **before returning an app**
- `POST /evaluate` — `{rule_id, inputs, input_sources, market?}` → `EvaluationRecord`
- `GET /healthz` — status, `checks`, `not_yet_checked`, every rule and signature
- `RuleInputError` / `RuleLogicError` — whose problem a failure is

- [x] **Write the failing tests** — 30 across boot and the endpoints
- [x] **Run, confirm failure** — `ModuleNotFoundError: bayyina.api`
- [x] **Implement.** `create_app()` calls `load_rules()` before the app exists —
      not in a startup event, which would leave a constructed app behind on
      failure. `bayyina.api.app:app` resolves through a module `__getattr__`, so
      the documented uvicorn command still refuses to start on a bad corpus while
      importing the module stays free of side effects
- [x] **Add response timing** — `x-response-ms` on every response, errors included
- [x] **Separate whose problem a failure is** — `RuleInputError` → 422,
      `UnknownRuleError` → 404, `RuleLogicError` → **500**. A corpus defect
      reported as a 4xx would send a caller into retrying forever
- [x] **Amounts cross the wire as strings or ints, never floats** — refused at the
      request model, so a rounding artefact cannot reach the number someone acts on
- [x] **G5 over HTTP is a 200** — `HUMAN_REVIEW_REQUIRED` is an outcome; a 4xx
      would teach every client to treat honesty as a fault
- [x] **G9 over HTTP** — every evaluation appended to the chained audit log before
      the response leaves; refused requests write nothing
- [x] **Prove the mechanisms** — moving the corpus check after app construction,
      removing the timing middleware, dropping the audit append, or mapping
      `RuleLogicError` to 422 each turns its tests red
- [x] **Wire the logging that T1.7 introduced** — the timing lines had no handler
      and emitted nothing under uvicorn, which uvicorn's own access log hides.
      Found by running the real server, not by the tests (D-044)
- [x] **Gitignore the audit log** — `backend/data/audit.jsonl` holds caller-stated
      rents and dates. It must never reach the repository
- [x] **Refuse a non-HTTPS base URL in production** — that URL becomes the SMS
      link to a resident's evidence pack (D-045)
- [x] **Implement the public rate limit** — `public_rate_limit_per_minute` had
      been advertised as an abuse guard since T1.1 with nothing behind it, and
      `/evaluate` goes public at T1.9. `/healthz` is exempt (D-047)
- [x] **Distinguish a missing corpus directory from an empty one** — the failure
      T1.9 is most likely to hit, with the resolved path in the message (D-046)
- [x] **Hold `.env.example` and `Settings` together** — two tests, and every
      declared-but-unread field now names the task that reads it (D-048)
- [x] **Run, confirm pass** — 218 backend tests

**DoD:** `/healthz` fails on an unsigned corpus. ✅ Every response is timed from
day one — we do not add observability later. ✅ The tamper demo runs through the
documented entry point: one digit changed → `verify_corpus` exits 1 and
`uvicorn bayyina.api.app:app` raises `TamperedRuleError`.

**Not done here, deliberately:** G3's confirmation token (Phase 3, and
ARCHITECTURE §9 now says the endpoint does not enforce it); `GET /rules` public
transparency (T2.6); rate limiting (`public_rate_limit_per_minute` is still
unread config).

---

## T1.8 — Minimal web checker

**Files:** `frontend/src/components/Checker.tsx`, `frontend/src/api/client.ts`,
`frontend/src/test/phone-safety.test.ts`
**Modify:** `backend/src/bayyina/api/app.py` to serve the built frontend,
`backend/src/bayyina/registry/evaluator.py` for named conditions

A single form: current rent, proposed rent, and a **manually entered** market
average with a note that automatic comparables arrive in T2.3. Displays verdict,
computation, cited clause and `review_status`.

- [x] **Build the form and wire it to `/evaluate`**
- [x] **Name the condition rather than inventing evidence.** The market average
      is typed by the reader, so the request carries no `contract_count`. The
      outcome is `CLEAR_WITH_CONDITIONS` naming `market_average_not_derived`.
      Sending a fabricated count to obtain a clean `CLEAR` would be the exact
      fabrication G5 exists to prevent (D-049)
- [x] **Verify by hand against three cases** — permitted, not permitted, and the
      one-fils edge. Run against the real backend, not mocks:
      exactly at AED 88,000.00 → permitted; AED 88,000.01 → not permitted
- [x] **Render human review as considered, never as failure** — the review
      colour, no `alert` role, and no banned word. Proven: switching it to the
      danger colour turns the test red
- [x] **Refuse to print a figure the outcome forbids** — the interface is the
      last surface before a person reads a number, so it drops computed figures
      on `HUMAN_REVIEW_REQUIRED` even if the payload carries them
- [x] **Serve the built frontend from the API process** — mounted last so it can
      never shadow a route; absent in development, where Vite serves it
- [x] **Confirm it is readable on a phone** — viewport declared, 44px tap
      targets, no fixed pixel widths, and the 71-character signature broken so it
      cannot widen the page. Enforced by `phone-safety.test.ts`, not remembered
- [x] **Fix two silent failures found by running it** — `/evaluate` missing from
      the dev proxy, and every colour class emitting no CSS under Tailwind v4.
      Both now have tests; every suite had passed while the product was broken
      (D-058)
- [x] **Fix the language switch** — it offered three languages and delivered
      one. Arabic differed from English in 1 of 57 strings, Malayalam in
      **zero**, so the button changed nothing on screen. First fix disclosed the
      gap (D-059); **superseded** — a caption on a broken control is still a
      broken control. The switcher now offers only what the interface can render
      and disappears at one language, derived from `_TRANSLATION_STATUS` so a
      finished locale makes its own button appear (D-065). Arabic and Malayalam
      stay in `LANGUAGES`, the templates and the voice scripts: they are the
      product, and the blocker is that the **official Arabic** of Decree 43/2013
      exists and must be sourced, not drafted. The choice is also persisted —
      every reload silently reverted to English
- [x] **Run, confirm pass** — 331 backend, 70 frontend

**DoD:** A stranger can reach a correct verdict without instructions. ✅ Verified
end to end as one process: `GET /` serves the app, `POST /evaluate` answers from
the same origin, no CORS.

**Not done here, deliberately:** the notice-validity check (the plan scopes T1.8
to the rent rule); Arabic and Malayalam copy, which needs a human translator per
D-013 and is gated on the glossary, not on code.

---

## T1.9 — Deploy ⚠ THIS IS BOX N

**Files:** `Dockerfile`, `.dockerignore`, `docs/CANVAS.md`

- [ ] Write the Dockerfile — Python 3.11-slim, install the backend package, copy
      `backend/rules/` and the built `frontend/dist/`, run uvicorn
- [ ] **TLS.** Terminate at the platform edge (Railway/Render/Fly all do), never in
      this process. Run uvicorn with `--proxy-headers --forwarded-allow-ips='*'`
      so the app sees the original scheme instead of assuming http
- [ ] **Set `BAYYINA_ENV=production` and an https `BAYYINA_BASE_URL`.** Settings
      refuses to boot otherwise (D-045), so this is checked rather than remembered
- [ ] Add HSTS and the standard security headers, and verify the certificate chain
      from outside the platform dashboard
- [ ] **Confirm HTTPS before Phase 3:** Twilio and ElevenLabs both require https
      webhook endpoints, so this is a hard prerequisite, not a polish item
- [ ] Deploy to a public host (Railway, Render or Fly.io free tier)
- [ ] **Verify `/healthz` reports `corpus_signed: true` in production**
- [ ] Record the live URL in `docs/CANVAS.md` box N

**DoD:** A public URL returns a correct verdict. **Box N is no longer blocked and
Stage 1 cannot score zero on it.** This is the single most important gate in the
plan.

---

# PHASE 2 · Real Data and the Artifact

## T2.0 — Design system and RTL foundation · Track C

**Files:** `frontend/src/index.css`, `docs/DECISIONS.md` — **partly done at the FE/BE split**

This product asks people to trust a legal determination. **A page that looks like
an unstyled template undermines the claim before a word is read.** One deliberate
visual pass now, reused by the checker, the provenance pages, the officer
dashboard and the PDF.

- [x] Define tokens: type scale, spacing, colour with **WCAG AA contrast
      verified**, and a state palette where `HUMAN_REVIEW_REQUIRED` reads as
      *considered*, not as *error*
- [x] Choose and bundle the type family — Noto Sans, Noto Sans Arabic, Noto Sans
      Malayalam, so web and PDF render identically
- [x] Build the RTL foundation: `dir="rtl"` mirrors layout, not just text. Use
      logical properties (`margin-inline-start`, not `margin-left`)
- [x] Build at 360 px first, then widen
- [x] Record the visual direction in `docs/DECISIONS.md` — D-080 to D-083

**Two accessibility defects found by measuring rather than asserting:**

- [x] **`ink-300` at 2.46:1**, under AA, used by nothing. Deleted — a token that
      exists will be reached for
- [x] **`rule` at 1.26:1, on the rent input's border.** The one field a person
      has to find and type into had a boundary they could not see. Split into
      `rule` (decorative hairline) and **`edge` at 3.6:1** (any boundary that
      must be findable — WCAG 1.4.11). Every ratio is now recomputed from
      `index.css` on each run, not asserted in a comment (D-080)
- [x] **A test fixture was adding a rule to the production stylesheet.** Tailwind
      v4 scans every project file, so the test documenting the banned v3 syntax
      taught Tailwind to emit it — invalid CSS, shipped, from the test that
      exists to ban it (D-083)

**Typography:** Noto across all three scripts, **175 KB bundled, no third-party
request** — the CSP forbids one and the PDF pipeline needs the same faces on
disk. 400 and 600 only. Body at 17px with loose leading, because the audience
reads in a second or third language on a phone.

**DoD:** ⚠️ **Partly met, and the gap is stated.** `specimen.html` is a second
Vite entry built from the product's own `index.css`, showing three 360 px panes,
the outcome states, the scale and the swatches with live contrast ratios. Its
Arabic pane is genuinely `dir="rtl"`, so the mirroring is real.

It is **not** "one page in all three languages": Arabic and Malayalam are not
translated (D-065), so those panes carry typographic text that says so. What is
demonstrated is that the three script stacks render at the same sizes with the
same rhythm. The translated page is T2.7 plus a translator.

**Screenshots are yours to take** — open `http://localhost:5173/specimen.html`
(or `/specimen.html` on the deployed container, which ships it). No headless
browser is installed and adding one for three screenshots is not worth 300 MB.

---

## T2.1 — Ingest with data-quality validation ✅

**Files:** `src/bayyina/market/{ingest,normalise,errors}.py`, `scripts/ingest_market.py`
**Test:** `tests/market/{test_ingest,test_normalise,test_release}.py` — **71 tests**

Ingestion is not `read_csv`. **Bad data produces confident wrong verdicts**, which
is the worst failure this product can have.

**The rules below were measured from the real file (2026-09-09).**
Source: `rent_contracts_20260226.parquet`, 9,798,685 rows, sha256 `72d347b2…`
— confirmed by the pipeline, not assumed.

- [x] **Exclude non-tenancy "residential" stock.** Worse than estimated:
      `Room in labor Camp` is **978,610 contracts at a median of AED 504,000**
      (the plan said 455,009), `Labor Camp` 134,334 at 816,000,
      `Staff Accommodatoion` *(misspelt in source)* 8,671 at 2,274,500. Scope is
      an **allowlist** and the **intersection** of property type and sub-type,
      because neither is sufficient: 'Room in labor Camp' appears 3,234 times
      under `Flat`, and `Studio` 6,552 times under `Labor Camps` (D-063)
- [x] **⚠ Exclude whole-block contracts — the plan did not have this rule and it
      matters most.** `annual_amount` is the total for every property on the
      contract, not one home's rent: 2-bed medians run AED 66,000 at one property
      and **AED 596,904 at ten**. **1,375,195 residential rows** carry it. Left
      in they inflate every median *and* count one contract once per property
      (D-060)
- [x] **Normalise area names — the plan had this inverted.** 'Al Barsha South
      Third' does not exist in this release; Barsha's eight sub-areas are spelled
      inconsistently across **genuinely different neighbourhoods**, and merging
      them would corrupt eight medians at once. The key case-folds and collapses
      doubled letters so a resident's spelling reaches DLD's, and **all 213 area
      names are asserted to merge exactly one pair** — 'AL QUSAIS' (148,665) with
      'Al Qusais' (11), the same place under two codes (D-060)
- [x] **Normalise sub-types.** There is no bedrooms column; the count lives in
      free text. `1bed room+Hall` → 1, `2 bed rooms+hall+Maids Room` → 2 (a
      maid's room is not a bedroom), `Studio` → **0, which is a real count and
      not a missing value**
- [x] **Reject implausible rents.** Absolute bounds 1,000–10,000,000. Measured:
      32 non-positive, 915 below floor, 103 above ceiling
- [x] **Per-cell IQR trimming**, per `(area, type, bedrooms, **year**)`. The year
      is not optional: Al Barsha First 2-beds ran 90,000 in 2017, 65,000 in 2021
      and 88,000 in 2026, so a fence across the whole corpus describes no year in
      it. Cells under 8 contracts are left alone (D-062). **198,625 trimmed**
- [x] **Reject** null or non-positive rent, end date not after start, missing
      area. **`contract_id` is not a key** — 8,178,976 distinct ids over
      9,798,685 rows; rejecting duplicates as the plan said would have discarded
      1.62M real tenancies. De-duplication is by `(contract_id, line_number)`
      (D-060)
- [x] Ingest → DuckDB with `snapshots`, `rejections`, `areas`, `contracts`;
      snapshot records `snapshot_id`, `computed_at`, `source`, `source_sha256`,
      `row_count`, `rejected_count` and every stage count
- [x] **Guard the allowlist.** An unrecognised property type holding ≥1% of a
      release stops the ingest — otherwise a `Flat` → `Apartment` rename would
      empty the table silently and look fine (D-063)
- [x] Record final counts in `docs/CANVAS.md` box D

**Measured result** — `python scripts/ingest_market.py data/raw/rent_contracts_20260226.parquet`, 27 s:

| Stage | Rows | |
|---|---:|---|
| Read | 9,798,685 | |
| Excluded | 4,296,572 | not a single-unit residential tenancy |
| In scope | 5,502,113 | |
| **Rejected** | **1,050** | **0.019%** of in-scope, against a 5% budget |
| Trimmed | 198,625 | outside 1.5×IQR within their cell-year |
| **Stored** | **5,302,438** | across **184 areas** |

**DoD:** ✅ Rejection rate **0.019%**, well under 5%, and measured against
in-scope rows rather than the file — 56% of the release is out of scope, so the
wrong denominator would have made the number meaningless (D-061).

✅ **The industrial-area check, which is the one that would have hurt real
residents:** raw `Residential` in Jabal Ali Industrial has a median of **AED
829,720**. After scope rules: **AED 32,000**. A caller asking whether their
32,000 rent may rise to 38,000 would have been told the market rate was three
quarters of a million — with a correct citation and signed arithmetic attached.
Asserted in `test_release.py`, not merely observed.

**Also found here:**

- **Five scope tests passed while proving nothing.** Deleting a scope rule let
  the hazard row into scope, where the *outlier fence* removed it instead, so
  "not in the table" held either way. The tests now assert `in_scope_rows`, which
  only scope can satisfy. All seven rules re-verified by deletion (D-064)
- **Box D's headline figure counted rows, not homes.** 743,740 residential
  registrations in twelve months, of which **567,652** are single-unit homes;
  the rest are 124,399 labour-camp and 146,489 whole-block contracts. Both
  numbers are true and they answer different questions
- **The release is 6.5 months old** (contracts to 2026-02-26, today 2026-09-09).
  T2.2's rolling twelve months must run to the **snapshot date**, not to today,
  or it silently halves its own evidence — 271,538 rows instead of 567,652

**Hardening pass (2026-09-10), after the audit:**

- [x] **The write is one transaction.** Contracts, areas, rejections and the
      snapshot row were written in sequence, so a crash between them left
      **comparable figures with no source, no digest and no date** — invisible,
      because every query still returns plausible rows. Two invariants now
      asserted: no orphan contract, and a mid-store failure leaves all four
      tables empty (D-066)
- [x] **The digest is validated as a digest**, `^sha256:[0-9a-f]{64}$` rather
      than `min_length=64`, which accepted a truncated value in the one field
      that carries a snapshot's traceability
- [x] **Cleared three stale deferral markers** naming T2.1 for work that is
      actually T2.3 — `market_snapshot_max_age_days`, the `/healthz` deferral,
      and the README. Two tests now hold the line: a `NOT YET CONSUMED` marker
      may not name a completed task, and may not name a task the plan does not
      contain (D-067)
- [x] **`ARCHITECTURE.md` named a database the code never writes**
      (`rent_contracts.duckdb` against `market.duckdb`). Nothing caught it,
      because a filename is neither a module nor a script. Now guarded
- [x] **Documented the pipeline** — README build command with the four-stage
      table, ARCHITECTURE §8 with the real schema and the scope reasoning

**Not done here, deliberately:** aggregation and the 20 ms lookup are T2.2; the
G5 thresholds that decide whether a thin cell may be quoted at all, and the
staleness check that finally consumes `market_snapshot_max_age_days`, are T2.3.

---

## T2.2 — Pre-aggregated comparables ⚠ LATENCY-CRITICAL

**Files:** `src/bayyina/market/aggregate.py`
**Test:** `tests/market/test_aggregate.py`

**A `GROUP BY` over 9.8M rows at call time cannot meet the 150 ms budget.**
Materialise medians at build time into a small indexed table.

- [x] Write a test asserting the aggregate table has one row per
      `(area, property_kind, bedrooms)` with `median_annual_rent`,
      `contract_count`, `snapshot_id`
- [x] **Write a performance test asserting lookup completes in under 20 ms**
- [x] Implement aggregation over a rolling 12-month window ending at the
      snapshot date
- [x] Bake the aggregate into the Docker image at build time

**Measured:** window 2025-03-01 .. 2026-03-01, **555,607 contracts**, 1,324 cells,
**841 quotable** at or above 10 contracts. **p95 lookup 7 µs** — 2,778× inside the
20 ms budget, because the table is read once at boot and held in memory.

**Two things the plan did not anticipate, both found by building it:**

- [x] **The window must end at the data, not at today.** A rolling twelve months
      to `now()` slides off the end of a release: six months after publication it
      would cover 267,252 contracts instead of 555,607 and keep shrinking, with
      no error and no signal. Anchoring on `max(contract_start_date)` is worse —
      one contract in the file starts **2204-10-04**, and a window ending there
      holds exactly one row, silently emptying the entire table. The snapshot now
      carries a `data_horizon` (99.9th percentile), dates beyond it are rejected,
      and both window ends are stored so a past answer reproduces (D-069)
- [x] **The build database is 359 MB; the request path reads 1,324 rows.** Baking
      it whole would ship 5.3M individual tenancy records in a public image to
      serve a few hundred numbers. `export_for_serving` writes a **1.3 MB**
      database — comparables, areas and provenance only, **271× smaller** — and
      that is what the image carries. Contracts stay in the build database, where
      re-aggregating and auditing a figure back to its rows are still possible

**DoD:** ✅ A measured lookup far under 20 ms. Deferred to T1.9: the same
measurement on the deployed instance.

---

## T2.3 — Comparables API with G5 thresholds

**Files:** `src/bayyina/market/comparables.py`, route in `routes_evaluate.py`
**Test:** `tests/market/test_comparables.py`

- [x] Write tests for the three bands: ≥30 → `ok` full confidence; 10–29 → `ok`
      reduced confidence; <10 → `insufficient_data` with
      **`median_annual_rent is None`**. Boundaries pinned at 9/10/29/30/31
- [x] Write a test asserting a stale snapshot (older than
      `market_snapshot_max_age_days`) returns `stale` and no figure
- [x] Implement; wire into `/evaluate` so a thin comparable forces
      `HUMAN_REVIEW_REQUIRED`
- [x] **`GET /comparables`** — the lookup as its own route, for the voice agent
      and the provenance page. **Always 200**: `insufficient_data`, `stale` and
      `unknown_area` are each a thing the agent has to say aloud, and returning
      them as 4xx would teach every client to treat our honesty as a fault
- [x] **`POST /evaluate` accepts a `dwelling`** — area, kind, bedrooms — and
      derives the figure itself. **This is the point of the task**: a resident no
      longer types their own market average, so the answer stops being
      `CLEAR_WITH_CONDITIONS / market_average_not_derived` and becomes `CLEAR`.
      Supplying both a figure and a dwelling is refused, because with both nobody
      could tell which number the answer used
- [x] **A fourth status the plan did not name: `unknown_area`.** "Not enough
      contracts in your area" and "which area?" are different problems and only
      one of them the caller can fix

**Three findings while wiring it:**

- [x] **A missing derived input was blaming the caller.** `_coerce_inputs` raised
      `MissingInputError` for any absent required input, derived ones included —
      so "we have too little market data" would have arrived as a 422 about a
      field the resident was never asked for. A derived input may now be absent;
      grading turns that into HUMAN_REVIEW_REQUIRED, and a second check refuses
      to run the rule if grading ever says answerable with a hole (D-073)
- [x] **Market data is optional at boot**, and `/healthz` names its absence with
      two separate checks — `market_data_loaded` and `market_data_fresh`. A
      loaded-but-stale snapshot answers every lookup with `stale`, which reads as
      a broken service unless health says why. **This retires the last
      `not_yet_checked` entry**, deferred there since T1.7 (D-074)
- [x] **G5 is a property of the type here.** `Comparable` cannot be constructed
      holding a figure unless its status is `ok`, so every refusal path is
      structurally unable to carry a number (D-071)

**DoD:** ✅ No code path returns a number below the threshold — asserted at the
boundaries, at the type, and by breaking each guard and watching a test go red.

**Production audit of T2.1-T2.3 (2026-09-10).** Two real defects, both in things
that already worked and passed every test:

- [x] **The disclosed age was wrong for 11.7% of cells.** D-076 built two
      freshness thresholds on `age_days`, and `age_days` was the *snapshot's*
      age. Of 841 quotable cells, 98 trail the release by more than a month and
      one — 72 contracts in Al Rowaiyah First — is **418 days old inside a
      release we call 193 days old**, past our own refusal threshold and quoted
      with a "193 days" label. Each cell now records its own newest contract, and
      that decides both the disclosure and the refusal. Verified: that cell now
      returns `stale` with no figure (D-078)
- [x] **`unknown_area` was a dead end.** We told a caller we could not resolve
      their area and offered nothing next, which on a phone call is where people
      hang up. `GET /areas` returns all 184 by display name, with a test that
      every listed name actually resolves (D-079)
- [x] **Punctuation was an outcome rather than a bad request.** `"   "` and
      `"!!!"` passed `min_length=1`, normalised to the empty key and came back
      as `unknown_area` — which implies we looked. Now a 422 pointing at
      `/areas`, on both routes
- [x] `aggregate()` validates its window up front instead of running the SQL and
      letting the model object afterwards; the build now reports
      `oldest_quotable_contract`, so it says at build time whether it has
      produced figures already too old to quote
- [x] Checked and found **correct**, so left alone: money crosses the wire as a
      string (`"85000.00"`), the store is immutable after construction and needs
      no lock, and the 503 for missing market data leaks no filesystem path

**Freshness, resolved (2026-09-10).** The open question here was whether to
refuse everything or raise the threshold. Neither: staleness now has **two**
thresholds and a middle band.

- [x] **Measured the cost of staleness** rather than guessing it. Median cell
      drift: 3.4% at three months, 4.3% at six, 6.1% at twelve. **The rent-cap
      bands are five percentage points wide**, so past a year a stale median can
      flip a verdict; under four months it cannot
- [x] `market_snapshot_fresh_days` (120) — under this, quote plainly.
      `market_snapshot_max_age_days` (365) — past this, quote nothing. Between
      them the answer carries `MARKET_DATA_AGEING` naming the date it rests on.
      The old 120 had **no recorded rationale anywhere**; it survives as the
      disclosure point because the measurement supports it (D-076)
- [x] Depth and recency **accumulate rather than rank** — a thin *and* ageing
      comparable owes the listener both facts
- [x] `/healthz` reports `market_data_usable`, not `market_data_fresh`. Freshness
      as a pass/fail check would have reported `degraded` for eight months of
      every publication cycle
- [x] **Verified on the real release**: 193 days old, `CLEAR_WITH_CONDITIONS`,
      `not_permitted`, AED 85,000 from 5,019 registered contracts, condition
      `market_data_ageing`. The product answers, and says what it rests on

> **Still operator-owned:** `www.dubaipulse.gov.ae` refuses connections from two
> independent networks. `dubailand.gov.ae` is live and its Real Estate Data
> portal bulk-exports the same registry — a Transactions pull on 2026-09-10 ran
> to that day, 154,262 rows, uncapped. **Download the Rents tab**, dates only,
> every other filter blank, then `python scripts/inspect_release.py <file>`.
>
> It needs an adapter: the portal has no contract identifier (a surrogate hash
> of the identifying fields, which undercounts rather than over-), different
> column names, and current-year data only, so it supplements the Pulse history
> rather than replacing it (D-077).
>
> **Local `.env` pins `MARKET_SNAPSHOT_MAX_AGE_DAYS=120`** and overrides the new
> default. Set it to 365 and add `MARKET_SNAPSHOT_FRESH_DAYS=120`.

---

## T2.4 — Evidence pack generator (G10)

**Files:** `src/bayyina/evidence/{pack,render}.py`, `templates/{en,ar,ml}/`
**Test:** `tests/evidence/test_pack.py`

**Interface produced:** `build_pack(records, caller_ref, language) -> EvidencePack`

- [x] **Write the failing tests**

```python
def test_generator_rejects_anything_but_evaluation_records():
    """G10: no free text can enter the document path."""
    with pytest.raises(TypeError):
        build_pack(["some free text"], caller_ref="x", language="en")


def test_pack_marks_caller_stated_facts_as_unverified(rent_eval):
    text = build_pack([rent_eval], "x", "en").render_text()
    assert "as stated by the caller" in text.lower()


def test_pack_carries_rule_version_and_signature(rent_eval):
    pack = build_pack([rent_eval], "x", "en")
    assert pack.signatures[rent_eval.rule_id].startswith("sha256:")


def test_pack_states_it_is_not_official(rent_eval):
    assert (
        "not an official determination" in build_pack([rent_eval], "x", "en").render_text().lower()
    )


def test_pack_renders_in_every_supported_language(rent_eval):
    for lang in ("en", "ar", "ml"):
        assert build_pack([rent_eval], "x", lang).render_text().strip()
```

- [x] Implement `build_pack` accepting **only** `EvaluationRecord` instances —
      raise `TypeError` otherwise. Jinja templates only; **no LLM import may exist
      in this module**
- [x] Add a test asserting the `evidence` package imports no LLM client

- [x] Implement `build_pack` accepting **only** `EvaluationRecord` instances.
      Every shape a composed answer plausibly arrives in is tested — a string, a
      dict shaped like a record, a list of them — because **pydantic would have
      coerced a mapping into an `EvaluationRecord`**, and a verdict assembled by
      hand or by a model would then have been indistinguishable from a computed
      one
- [x] Add a test asserting the `evidence` package imports no LLM client
- [x] **Vocabulary moved out of the templates** into `wording.py`. The first pack
      printed `Gap pct: 0.058824` and `Current annual rent: 80000` — both banned
      by GLOSSARY sections 1 and 4. A field with no wording now raises rather
      than falling back to its own name (D-085)
- [x] **Language is refused, never faked.** `ar` and `ml` raise rather than
      producing an English document, and support is derived from which templates
      exist. Each missing language carries a note saying what is needed and why
      it is blocked (D-084)
- [x] **`pip install .` would have shipped no templates.** setuptools copies
      `.py` and nothing else; the container would have booted clean and failed on
      the first pack. `package-data` declared, swept by a test, verified against a
      real install, and CI now renders a pack **inside the built image** (D-086)

**DoD:** ✅ `grep -r "openai\|anthropic\|elevenlabs" src/bayyina/evidence/`
returns nothing, and the same sweep runs as a test across every source and
template in the package. G10 is verified by inspection *and* by the type at the
door.

---

## T2.5 — PDF rendering and font validation ⚠ WILL BITE — DEFERRED by decision

**Files:** `src/bayyina/evidence/render.py`, `assets/fonts/`
**Test:** `tests/evidence/test_render.py`

**Malayalam and Arabic will render as blank boxes without the right fonts.**
Discovering this during the demo is unacceptable.

- [ ] Bundle Noto Sans, Noto Sans Arabic and Noto Sans Malayalam
- [ ] Write a test rendering each language and asserting the PDF contains no
      `.notdef` glyphs
- [ ] Verify Arabic renders right-to-left correctly
- [ ] **Visually inspect all three PDFs.** Automated glyph checks miss layout
      failures

**DoD:** Three PDFs, opened and read by a human. Arabic is RTL. Malayalam
conjuncts render.

---

## T2.6 — Provenance pages

**Files:** `backend/src/bayyina/api/routes_provenance.py`, `frontend/src/components/Provenance.tsx`

- [x] Render encoded logic beside the verbatim clause, with the official link,
      signature and approval status
- [x] Test that an unknown rule returns 404 and that the page shows `provisional`

**DoD:** A lawyer who has never seen the codebase can verify an encoding against
source in under a minute. **Time this with a real person.**

---

## T2.7 — Web checker v2 — ✅ except the three-language switcher (blocked on translation)

- [x] Full flow: property details → automatic comparable → verdict → pack download
- [x] Render the `HUMAN_REVIEW_REQUIRED` state properly — **it is a feature, not
      an error page**
- [ ] Language switcher for all three languages — **BLOCKED.** Needs reviewed
      ar/ml locales. Machine translation is refused by test (D-099); the
      machinery is ready and waiting on a native speaker.

**DoD:** The complete Mode A journey works without a phone call.

---

## T2.8 — Comprehension test ⚠ CUSTOMER GATE — BLOCKED on ar/ml templates

**No code. This is the customer-first gate.**

**BLOCKED ON A TRANSLATOR, not on engineering.** `build_pack(...,
allow_draft=True)` renders an unreviewed template so this gate can run
before approval, and `_TRANSLATION_STATUS` keeps it undeliverable until
it passes. What is missing is the ar/ml templates themselves, which a
native speaker must write (D-099).

- [ ] Give the Malayalam pack to someone who reads Malayalam and **not** English.
      Ask them: what is the answer, and what do you do next?
- [ ] Repeat for Arabic
- [ ] Record every point of confusion and fix the templates

**DoD:** Two non-English readers correctly state the verdict and the next step
without help. **If they cannot, the product does not work — regardless of what the
tests say.**

---

## T2.9 — Case store, migrations, correlation · Track A

**Files:** `src/bayyina/store/{db,migrations,cases,consent,deadlines}.py`,
`migrations/001_initial.sql`
**Test:** `tests/store/test_{migrations,cases,consent}.py`

**This was missing from the earlier plan.** `consent.py` and `deadlines.py` were
listed in the file structure with nothing creating the storage they depend on.

**Interfaces produced:**
- `get_db()` — SQLite connection with `journal_mode=WAL` and a busy timeout
- `run_migrations(db)` — forward-only, numbered, idempotent
- `Cases.create(pack, call_id) -> Case` with `status="awaiting_review"`
- `Consent.record(call_id, granted)` · `Consent.opt_out(call_id)` · `Consent.has(call_id)`
- `Deadlines.arm(case_id, due, rule_id)`

Tables: `cases`, `evidence_packs`, `deadlines`, `consent`, `audit`, `idempotency`.
**Every table carries `call_id`** so one identifier threads the whole journey.

- [x] **Write the failing tests**

```python
# tests/store/test_migrations.py
def test_migrations_are_idempotent(tmp_path):
    """Running twice must not fail or duplicate."""
    db = get_db(tmp_path / "t.db")
    run_migrations(db)
    run_migrations(db)
    assert table_exists(db, "cases")


def test_wal_mode_is_enabled(tmp_path):
    """Default journal mode locks under concurrent calls."""
    db = get_db(tmp_path / "t.db")
    assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
```

```python
# tests/store/test_consent.py
import pytest
from bayyina.store.consent import Consent, NoConsentError


def test_opt_out_is_irreversible(db):
    Consent(db).record("call-1", granted=True)
    Consent(db).opt_out("call-1")
    Consent(db).record("call-1", granted=True)  # attempt to re-grant
    assert Consent(db).has("call-1") is False


def test_opt_out_is_written_to_the_audit_trail(db):
    Consent(db).record("call-1", granted=True)
    Consent(db).opt_out("call-1")
    assert any(r["event"] == "opt_out" for r in audit_entries(db, "call-1"))
```

```python
# tests/store/test_cases.py
def test_no_agent_reachable_status_is_terminal(db, sample_pack):
    """G4: the agent can never move a case to a decided state."""
    from bayyina.store.cases import Cases, TERMINAL_STATUSES

    case = Cases(db).create(sample_pack, call_id="call-1")
    assert case.status not in TERMINAL_STATUSES
```

- [x] **Run, confirm failure**
- [x] **Implement.** `TERMINAL_STATUSES = frozenset({"approved", "rejected",
      "amended"})` — set only through the officer interface. `Cases.create()` has
      no parameter that can produce one
- [x] **Run, confirm pass**

**DoD:** Opt-out is irreversible and proven by test. WAL is on. Migrations run
twice without error. G4 is asserted, not assumed.

---

## T2.10 — Failure taxonomy and tool behaviour ⚠ VOICE-CRITICAL · Track A — ✅ except `/dispatch` and `/deadline`, which are Phase 3 tools

**Files:** `src/bayyina/api/errors.py`, `agent/scripts/*/failures.md`
**Test:** `tests/api/test_failures.py`

**A webhook that hangs during a live call produces dead air, and the caller hangs
up.** Every tool needs a defined failure behaviour and a line for the agent to say.

- [x] Define the taxonomy, and for each: HTTP status, agent behaviour, spoken line

| Failure | Status | The agent says |
|---|---|---|
| Comparable not found | 200, `insufficient_data` | The G5 thin-data script — not an error |
| Rule evaluation error | 500 | *"Something went wrong on my side. I'm not going to guess at your answer — let me pass you to someone."* |
| Timeout (> 3 s) | — | Filler line, then one retry, then escalate |
| SMS dispatch failed | 502 | *"I couldn't text that through. I can read out the key points, or try another number."* |
| Corpus unsigned at boot | — | Service does not start. No call is answered |

- [x] Add explicit timeouts to every outbound call
- [ ] Add `Idempotency-Key` to `/evidence-pack`, `/dispatch` and `/deadline`;
      **test that a replayed key returns the prior result rather than acting twice**
- [x] Add rate limiting to public endpoints
- [ ] Write the failure lines into the T0.6 script set, in all three languages

**DoD:** Every tool has a tested failure path and a spoken line. **A replayed
dispatch sends one SMS, proven by test.** No failure produces silence.

---

## T2.11 — README and API documentation · Track D

**Files:** `README.md`

Written now, not in the final week. It is a **Stage 2 deliverable** and it is also
how a judge forms their first impression of the engineering.

- [x] Write `README.md`: what it is, the one sentence, quickstart from
      `.env.example`, architecture in one diagram, the guardrail table, how to
      sign a rule, how to run the tests, the latency budget as a stated commitment
- [x] Curate the FastAPI OpenAPI output — every endpoint gets a description and an
      example
- [x] **Include the tamper demo as a documented, reproducible procedure** — a
      reader must be able to run the wow moment themselves in three commands

**DoD:** A stranger clones the repo and has it running from the README alone. The
tamper demo is reproducible from the documentation.

---

# PHASE 3 · Voice

**3a (23–30 Sep)** runs on the free tier while awaiting the shortlist.
**3b (30 Sep–10 Oct)** is the build sprint.

- [ ] **T3.1** Agent workflow skeleton in English: greet, disclose, triage, one
      slot-fill path. Proves the webhook tool contract before the sprint clock starts
- [ ] **T3.2** All seven webhook tools wired and contract-tested
- [ ] **T3.3** `guardrails/triage.py` — G2 interpretive classifier and G6 distress
      detection, against a labelled set of **≥ 60 utterances per language, both
      classes**. Report precision and recall, not accuracy
- [ ] **T3.4** Slot-fill in **four turns** with one batched readback (T0.6 scripts)
- [ ] **T3.5** Pack dispatch by SMS **during the call**. Delivery to the calling
      number requires no OTP; a different number does
- [ ] **T3.6** Arabic and Malayalam, including mid-call language switching
- [ ] **T3.7** Deadline arming with opt-in and irreversible opt-out (G8)
- [ ] **T3.8** **Measure end-to-end latency against the budget.** Report p50/p95
      for first audio. If p95 exceeds 1.5 s, fix before adding features

**DoD for Phase 3:** A live number runs the full journey in three languages, and
measured latency is recorded against the published budget.

---

# PHASE 4 · Evidence, Demo, Hardening

- [ ] **T4.1** Agent Testing suites: primary flow, multi-run pass rates
- [ ] **T4.2** Adversarial suites — advice-seeking, contradictory numbers,
      mid-call language switch, distress, opt-out, thin data
- [ ] **T4.3** **The tamper demo, scripted and rehearsed.** Edit one digit,
      restart, service refuses to boot. Rehearse until it is reliable
- [ ] **T4.4** Demo recording, **built to pitch standard** — the team cannot
      travel, so this recording is the pitch
- [ ] **T4.5** Final pass on the T2.11 README with real numbers filled in; export
      the one-page architecture diagram
- [ ] **T4.6** Observability: latency percentiles, abandonment rate, resolution
      state mix, cost per call. **Measure cost per call and record it**

**DoD:** Every Stage 2 deliverable exists. Latency, abandonment and cost are
measured numbers, not estimates.

---

## Risk Register

| Risk | Trigger to watch | Response |
|---|---|---|
| Dubai Pulse access delayed | No credentials by 12 Sep | Bulk CSV path (already parallel in T0.3) |
| Latency budget missed | T2.2 lookup > 20 ms | Reduce aggregate granularity; cache hot areas in memory |
| Data quality poor | T2.1 rejection rate > 5% | Stop. Investigate before building on it |
| Malayalam rendering fails | T2.5 `.notdef` glyphs | Substitute font; if unresolvable, drop to Hindi and say so |
| Comprehension test fails | T2.8 | **Blocking.** Rewrite templates before Phase 3 |
| No shortlist on 30 Sep | — | Product still ships. Mode A is independent of the competition |
| Canvas rejects tables | T0.2 answer | Reformat D, I, J as prose. Cheap if known early |

---

## Self-Review

Checked against DESIGN.md and ARCHITECTURE.md on 2026-09-09.

**Guardrail coverage — all ten have an implementing task:**

| Guardrail | Implementing task |
|---|---|
| G1 citation-or-silence | T1.5 — citation non-nullable on the record type |
| G2 interpretive tripwire | T3.3 — classifier with precision/recall reported |
| G3 confirmed data only | T3.4 — batched readback issues the token |
| G4 never submits | Not implemented **by design**; asserted by test in T3.2 |
| G5 insufficient data | T1.5 — the rule is not run below threshold, and the record type refuses a figure. T2.3 supplies the real contract counts |
| G6 distress detection | T3.3 |
| G7 unsigned-rule refusal | T1.2 loader + CI, and boot-time test in T1.7 |
| G8 consent and opt-out | T3.7 |
| G9 auditable lineage | T1.5 — hash-chained append-only audit, plus a required source per input |
| G10 states, never argues | T2.4 — rejects non-records; verified by import inspection |

**Customer journey coverage:** disclosure timing T0.6 · language recovery T0.6/T3.6
· four-turn diagnosis T0.6/T3.4 · answer-first T0.6 · thin-data script T0.6/T2.3 ·
pack in language T2.4/T2.5 · **comprehension verified T2.8** · deadline T3.7 ·
escalation T3.3 · **failure never produces silence T2.10**.

**Discipline review — what each function added on the final pass:**

| Function | Gap found | Task |
|---|---|---|
| Backend | **No case store existed**, though `consent.py` and `deadlines.py` depended on one | T2.9 |
| Backend | No failure taxonomy — a hung webhook meant dead air on a live call | T2.10 |
| Backend | No idempotency; a platform retry would double-send SMS | T2.10 |
| Backend | No secrets handling, no migrations, SQLite default journal mode locks | T0.9, T2.9 |
| Frontend | RTL treated as a font problem when it is a layout problem | T2.0 |
| Frontend | No visual identity — an unstyled page undermines a trust product | T2.0 |
| Frontend | `HUMAN_REVIEW_REQUIRED` declared "a feature" but never designed | T2.0 |
| PM | No parallelisation; no stated critical path | Workstreams |
| PM | Canvas treated as a by-product rather than the Stage 1 deliverable | Track D |
| PM | No decision log — settled questions would be re-litigated | T0.9 |
| Docs | No glossary; four surfaces × three languages would drift | T0.8 |
| Docs | README was a Stage 2 deliverable scheduled for the final week | T2.11 |

**Type consistency:** `Rule` (T1.2) → `Evaluator` (T1.5) → `EvaluationRecord` →
`build_pack` (T2.4) → `render` (T2.5). `Band` defined once in `registry/schema.py`
and consumed by T1.3. No orphan references.

**One documentation change to fold back:** ARCHITECTURE.md §7 places OTP
verification before the verdict. T3.5 moves it — the pack goes to the calling
number without OTP, since being on the call proves control of it, and OTP triggers
only for delivery elsewhere. **This is less friction for no loss of safety.**
Update ARCHITECTURE.md §7 and the API table before the canvas is finalised.

**Known gap, accepted:** Phase 3 tasks carry deliverables and DoD but not TDD
steps, because the ElevenLabs Workflows builder is not yet in hand. Expanding them
into false detail now would be fiction. They expand on 30 September.
