# Bayyina — Architecture & Technical Reference

> **Status:** Final architecture for the Ignyte × ElevenLabs submission.
> Source of truth for *how* it is built. Feeds Idea Canvas boxes F–I, and becomes
> the Stage 2 architecture diagram + technical README due 14 October.
> Last updated: 2026-09-07.

---

## 1. Governing Principles

> **Bayyina converts published tenancy rules into a safe, conversational workflow
> that determines what can be determined, produces the evidence a person needs to
> act, and stops whenever the facts require human judgement.**

That sentence is the specification. The three principles below are how it is
enforced in code.

> **1 · Determinism at the core. Language only at the edge.**
> The LLM diagnoses, slot-fills and speaks. It never computes, decides, or interprets.

> **2 · The agent prepares. It never submits, and it never argues.**
> The resident reviews and acts. Authorities decide.

> **3 · Every external permission is an adapter, never a dependency.**
> If a government integration is absent, the product still works completely.

If the engine returns no citation, **the agent is structurally incapable of
answering.** If a document would require persuasive prose, **the generator has no
code path that produces it.** These are not prompt instructions.

---

## 2. The Adapter Boundary — the most important line in this document

```
╔═══════════════════════════════════════════════════════════════════╗
║  EVERYTHING BELOW THIS LINE REQUIRES NOBODY'S PERMISSION.         ║
║  Open data · caller-stated facts · our engine · our generator.    ║
║  The product is complete and shippable without a single           ║
║  government integration.                                          ║
╚═══════════════════════════════════════════════════════════════════╝
                              ▲
                              │  ADAPTER INTERFACE (Mode C)
                              │  Implemented as an interface with no
                              │  concrete implementation. Declared
                              │  absent — never faked, never mocked
                              │  to look present.
                              ▼
              [ Authority submission — DLD / RDC / MOHRE ]
                      NOT IMPLEMENTED · NOT CLAIMED
```

| Mode | Behaviour | Requires | Status |
|---|---|---|---|
| **A · Prepare** | Evidence pack + factual response template delivered to the caller. They send it | Nothing but us | **The product** |
| **B · Sandbox** | Case lands in *our* case API and *our* officer dashboard | Nothing but us | Built — proves the loop |
| **C · Authority** | Direct submission into a government queue | Signed integration | **Interface only** |

---

## 3. System Diagram

```
┌── CHANNELS ────────────────────────────────────────────────────────────┐
│  Twilio voice (inbound)  ·  WebRTC widget  ·  public web checker        │
│  Twilio SMS / WhatsApp   ← OTP out, evidence pack out, reminders out    │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── LISTEN ──────────────────────▼───────────────────────────────────────┐
│  Scribe v2 Realtime + keyterm biasing                                   │
│  (Ejari, RERA, Makani, AED amounts, Dubai area names)                   │
│  Language auto-detect on first utterance                                │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── AGENT · ElevenLabs Workflows ▼───────────────────────────────────────┐
│  [1 Greet · Disclose]   AI disclosure · recording · not legal advice    │
│  [2 Triage]             served domain? answerable or interpretive?      │
│         │                          └────► [Human handoff] ◄──┐ G2 G6    │
│  [3 Diagnose]           discovers which facts the rule needs │          │
│         │               readback + confirm each value (G3)   │          │
│  [4 Verify]             OTP over SMS/WhatsApp locks session  │          │
│  [5 Compute]            calls Rules API. COMPUTES NOTHING. ──┘          │
│  [6 Explain]            renders result · cites clause aloud (G1)        │
│  [7 Generate]           evidence pack built (G10 template-only)         │
│  [8 Dispatch]           pack link sent to caller's phone, on the call   │
│  [9 Protect]            deadline armed under explicit consent (G8)      │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── EVIDENCE ENGINE ─────────────▼───────────────────────────────────────┐
│  Deterministic template renderer. Inputs: evaluation records only.      │
│  NO free-text generation. Produces the case report + response template. │
│  Bayyina-branded · marked "not an official determination"               │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── CASE STORE (ours) ───────────▼───────────────────────────────────────┐
│  cases · evidence_packs · deadlines · consent · audit                   │
│  Officer dashboard reads from here (Mode B)                             │
│  Agent-reachable statuses can never be terminal (G4)                    │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── RULES REGISTRY ◄── THE ASSET ▼───────────────────────────────────────┐
│  rent_increase.dubai.decree_43_2013     @v1                             │
│  notice_validity.dubai.law_26_2007_a14  @v1                             │
│                                                                         │
│  pure fn(inputs) → {state, verdict, computed, rule_id, rule_version,    │
│                     citation, confidence, review_status, input_sources} │
│  UNSIGNED OR TAMPERED → SERVICE REFUSES TO BOOT (G7)                    │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── SOURCES ─────────────────────▼───────────────────────────────────────┐
│  Citations come from each signed rule's verbatim clause - no retrieval  │
│  DuckDB ← Dubai Pulse dld_rent_contracts-open, snapshotted + dated      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | ETL and rules engine want the same language |
| API | FastAPI | Typed models give the agent its tool contracts for free |
| Rule schema | Pydantic v2 | Rule validation *is* schema validation |
| Rule storage | YAML in git | Version control **is** the version history; diffs readable by a non-programmer |
| Market data | DuckDB | 9.8M rows, single file, zero infrastructure |
| Case store | SQLite | Cases, deadlines, consent, audit. Zero setup |
| Documents | Jinja2 → HTML → PDF | **Templates, not generation.** The constraint is the mechanism (G10) |
| Frontend | Vite + React + TypeScript + Tailwind | A typed API client catches contract drift at compile time. Builds to static assets the backend serves, so deployment stays one container (D-019) |
| i18n | i18next | Three languages; untranslated keys fall back to readable English, never a raw key |
| Voice | ElevenLabs Agents | Configuration; webhook tools point at our FastAPI |
| Telephony | Twilio | Voice inbound, SMS/WhatsApp out |
| Deploy | Single container | Under $20/month all-in |

**Rejected:** UAE Pass in v1 (a permission we do not have — OTP achieves session
binding without it); a hosted database (SQLite + DuckDB are sufficient and
portable); an LLM document writer (see G10).

---

## 5. Rules Registry

### 5.1 Rule format

```yaml
id: rent_increase.dubai.decree_43_2013
version: 1
jurisdiction: AE-DU
effective_from: 2013-12-09
effective_to: null

source:                      # G1 lives here: every field is required
  document_id: dubai_decree_43_2013
  title: Decree No. (43) of 2013 Determining Increases in Real Property Rent
  clause: Article 1
  url: https://dubailand.gov.ae/
  verbatim: |
    The maximum rent increase for real property units in the Emirate of Dubai
    shall be determined as follows: [...]

logic: banded_percentage     # an enum, not a free string

inputs:                      # a declaration the evaluator executes
  current_annual_rent:  { type: money, currency: AED, required: true, derived: false }
  market_average_rent:  { type: money, currency: AED, required: true, derived: true  }
  proposed_annual_rent: { type: money, currency: AED, required: true, derived: false }

bands:                       # gap = (market_average - current) / market_average
  - { gap_from: 0.00, gap_to: 0.10, max_increase: 0.00 }
  - { gap_from: 0.10, gap_to: 0.20, max_increase: 0.05 }
  - { gap_from: 0.20, gap_to: 0.30, max_increase: 0.10 }
  - { gap_from: 0.30, gap_to: 0.40, max_increase: 0.15 }
  - { gap_from: 0.40, gap_to: null, max_increase: 0.20 }

review_notes:                # signed alongside the rule, printed on provenance
  - "INTERPRETATION. The decree states whole percentages, leaving 10-11% [...]"

approval:
  status: provisional        # unsigned | provisional | certified
  approved_by: "Bayyina team"
  approved_at: "2026-09-09T08:00:29Z"
  signature: "sha256:bc45..."  # canonical hash of this rule minus the approval block
```

A notice rule replaces `bands` with a `notice` block carrying `required_days: 90`.
**The parameter belongs to the rule, never to configuration** (D-027): it sits
inside the bytes the signature covers, so an operator cannot change what the law
says while the signature still verifies.

**Nine things the loader rejects before the service accepts traffic.** A rule
file is static data edited by hand, so everything knowable now is checked now —
failing while a caller is on the line is the outcome each of these prevents.

| Rejected | Because |
|---|---|
| Unknown field anywhere | A typo silently ignored is a wrong verdict waiting |
| Unknown `logic` value | Logic nobody implemented would fail at dispatch, mid-call |
| Wrong parameter block | A notice rule with a band table reads as configured and is never consulted |
| Undeclared input the logic reads | The evaluator could not coerce or require it |
| Declared input the logic ignores | We would ask a caller for it on the phone and discard it |
| Money input with no currency | An amount with no unit is not an amount |
| Band table malformed | A gap with no defined answer, or `20` written for `0.20` |
| `required_days` outside 1-1095 | Months entered as days, or 90 typed as 9000 |
| `effective_to` before `effective_from` | The rule was never in force |

**`review_notes` are data, not comments.** Signing rewrites the file, so a YAML
comment would be unsigned commentary on signed content. Every open question — the
undefined 10-11% band, "unless the parties agree otherwise", the unofficial
translation — is recorded in a field the signature covers and the provenance page
prints (D-029).

### 5.2 Approval status

| Status | Loader | Agent |
|---|---|---|
| `unsigned` | **Raises. The service does not boot.** | — |
| `provisional` | Loads | **Discloses aloud that the encoding awaits qualified review** |
| `certified` | Loads | Speaks normally |

**We ship `provisional` and we say so.** Honest, given we hold no retained
counsel — and worth more than implying a reviewer we do not have.

### 5.2.1 The signing protocol — how G7 is actually operated

A judge who takes the guardrail seriously will ask how the hash is produced and
where it is checked. Three places, deliberately:

**1 · Signing (manual, by the approver).**

```bash
python scripts/sign_rule.py rules/rent_increase.dubai.decree_43_2013.v1.yaml
# → signed rent_increase.dubai.decree_43_2013.v1.yaml [provisional] by Bayyina team
#     sha256:bc45809fffe25406e2d032825cc3f60cbee8c003ddb5acc91b57c2f92c6400ab
```

The script canonicalises the rule body **excluding its approval block** — JSON
with sorted keys and no incidental whitespace — takes SHA-256, and writes the
digest plus approver and timestamp back into `approval`. Excluding the approval
block is what makes the signature stable when only metadata changes.

**2 · CI (every push).**

```bash
python scripts/verify_corpus.py rules/     # exits non-zero on any mismatch
```

A rule edited without re-signing **fails the build**. This is the control that
catches an honest mistake, not just an attack.

**3 · Runtime (every boot).**

`create_app()` calls `load_rules()` before serving traffic. `unsigned` raises
`UnsignedRuleError`; a digest mismatch raises `TamperedRuleError`. **The process
exits.** The check runs in `create_app()` and not in a startup event, because a
startup event that raises still leaves a constructed app behind. `GET /healthz`
re-reports corpus state, so a deployment is verifiable from outside rather than
on the assumption that it booted the way we think it did.

Signing is manual and deliberately unautomated: **a signature is a human
attestation, and automating it would make it meaningless.**

### 5.3 The two v1 rules

Both are written, signed `provisional`, and load. CI verifies their signatures on
every push with no `--allow-empty` escape.

| Rule | Logic | Detail | Review notes |
|---|---|---|---|
| `rent_increase.dubai.decree_43_2013` | `banded_percentage` | Five bands: 0/5/10/15/20% | 6 |
| `notice_validity.dubai.law_26_2007_a14` | `notice_period` | ≥90 days before expiry | 6 |

**Only `market_average_rent` is derived.** Every other input is the caller's own
account, which is why G5 constrains the rent rule and cannot constrain the notice
rule — and why a caller whose area has too little data still leaves with an
answer to the notice question and an evidence pack containing it.

The twelve review notes are the honest part. They record the decree's undefined
10–11% band, the notice period's "unless the parties agree otherwise", that both
verbatim texts are unofficial English translations, and that neither URL is yet a
permanent link to the gazetted text. **A provisional rule with no open questions
is a rule nobody examined**, and a test asserts every rule carries some.

### 5.4 Evaluation record

```json
{
  "eval_id": "ev_8f1c4b2a…",
  "rule_id": "rent_increase.dubai.decree_43_2013",
  "rule_version": 1,
  "rule_signature": "sha256:bc45…",
  "review_status": "provisional",
  "state": "CLEAR",
  "verdict": "not_permitted",
  "inputs": { "current_annual_rent": "80000", "market_average_rent": "87000",
              "proposed_annual_rent": "96000" },
  "input_sources": { "current_annual_rent": "caller_stated",
                     "market_average_rent": "dld_open_rent_contracts_derived",
                     "proposed_annual_rent": "caller_stated",
                     "market_snapshot": "2026-Q3" },
  "computed": { "gap_pct": 0.08046, "band_matched": 0, "max_increase_pct": 0.0,
                "max_lawful_rent": "80000.00", "proposed_increase_pct": 0.2 },
  "citation": { "document_id": "dubai_decree_43_2013",
                "title": "Decree No. (43) of 2013 …",
                "clause": "Article 1",
                "url": "https://dubailand.gov.ae/",
                "verbatim": "The maximum rent increase … " },
  "evidence": { "contract_count": 5557, "snapshot_id": "2026-Q3" },
  "conditions": [],
  "confidence": 1.0,
  "created_at": "2026-09-09T08:00:29Z"
}
```

`input_sources` distinguishes **caller-stated** from **derived** values on every
field, and the evaluator refuses a call in which any supplied input lacks one.
The evidence pack prints that distinction rather than hiding it.

**The record type is where two guardrails are enforced.**

- **G1** — `citation` is non-nullable and every field within it has a minimum
  length. An answer with no clause behind it is not a shape the system can hold.
- **G5** — a record in `HUMAN_REVIEW_REQUIRED` cannot carry a verdict, a computed
  figure, or a confidence number. The validator rejects it. Below the evidence
  threshold **the rule is never run**, so there is no figure held anywhere for a
  later step to decide to speak (D-030).

`evidence` sits beside `computed` rather than inside it for exactly that reason:
a thin-data outcome still discloses *how* thin — "four registered contracts" — 
while carrying no figure about the caller's own rent.

**A conditional answer must name its condition.** `conditions` is empty for
`CLEAR`, non-empty for `CLEAR_WITH_CONDITIONS`, and the record refuses to
validate otherwise. It holds keys, not sentences, so each surface renders them in
the reader's own language:

| Key | Meaning | Reached when |
|---|---|---|
| `thin_comparable_data` | We derived the market figure from 10–29 contracts | Voice and web, on our own comparable |
| `market_average_not_derived` | The market figure was supplied to us, not computed by us | The web checker today, until T2.3 |

The second exists because inventing a contract count for a figure someone typed
would be fabricating evidence (D-049). `confidence` is `None` in that case: we
cannot state a confidence in evidence we did not gather.

`confidence` is a **defined quantity, not an estimate**: the proportion of the
30-contract full-confidence threshold that this evidence reaches, capped at 1.0.
It describes the depth of market data behind a derived input. It is not a
probability that the verdict is correct, and nothing presents it as one.

---

## 6. Guardrails — Mechanisms, Not Intentions

Ten. Each enforced by a schema contract, a load-time check, a tool scope, or the
absence of a code path. **None is a prompt instruction.**

| # | Guardrail | Mechanism |
|---|---|---|
| **G1** | **Citation-or-silence** | `EvaluationRecord.citation` is non-nullable and each field within it has a minimum length. A verdict with no clause behind it **is not a shape the system can construct**, so escalation is the only remaining branch |
| **G2** | **Interpretive tripwire** | Per-turn classifier for interpretation-seeking language ("will I win", "should I"). Fires transfer from any node |
| **G3** | **Confirmed data only** | Amounts and dates issue a confirmation token only after spoken readback. The Rules API rejects requests without one |
| **G4** | **Never submits to an authority** | Mode C is an interface with **no concrete implementation**. There is no code path to a government system, and no agent-reachable case status is terminal |
| **G5** | **Insufficient data over false precision** | Below 10 comparable contracts **the rule is never run**. A `HUMAN_REVIEW_REQUIRED` record carrying a verdict, a computed figure or a confidence number fails validation, so there is no number held anywhere to speak |
| **G6** | **Distress detection** | Homelessness, abuse, self-harm signals → immediate warm transfer, logged |
| **G7** | **Unsigned-rule refusal** | The loader verifies each signature against a canonical hash of the rule body. Unsigned, tampered, **structurally malformed, or empty** → **the service fails to boot**. `Evaluator` re-checks on construction, so the guarantee holds at the thing that produces verdicts and not only at boot (D-034). One bad rule fails the whole corpus; partial loading would mean running on logic nobody reviewed |
| **G8** | **Consent and opt-out** | Reminders require an explicit opt-in recorded on the call. Opt-out writes an irreversible suppression record. **No bulk outbound exists in the codebase** |
| **G9** | **Auditable lineage** | Every evaluation appends one hash-chained JSON line: inputs, source per field, rule version, signature, outcome, timestamp. `AuditLog` exposes no update or delete, and appends under a lock. `verify_chain()` names the first edited or inserted entry |
| **G10** | **States, never argues** | The evidence generator accepts **only** structured evaluation records and renders Jinja templates. It has no LLM in its call path, so persuasive prose is not a thing it can emit |

**Four ways a corpus is rejected at boot**, each a separate failure the loader
names precisely so an operator can fix it from the message alone:

| Condition | Why it must not boot |
|---|---|
| `unsigned` status | Nobody has attested to this encoding |
| Signature mismatch | The body was edited after signing |
| Structurally malformed | Nine checks, listed in §5.1 — unknown logic, the wrong parameter block, an undeclared input, a `20` where `0.20` was meant |

Each names the file and the field, because the promise is that an operator fixes
it from the message alone:

```
CORPUS REJECTED
  bad.v1.yaml: does not match the rule schema:
    logic: Input should be 'banded_percentage' or 'notice_period'
```
| **Empty corpus** | A service with no rules answers nothing. It would report healthy while being useless — usually a deleted file or a container build that skipped `rules/` |

**G7 answers the brief's hardest requirement** — *"a qualified person must review
and sign off the rule-matching logic before launch."* A load-time failure, not a
policy. It is also the demo's wow moment.

**G10 is the one that keeps us legal.** A model writing advocacy on a tenant's
behalf is an unlicensed legal service. Removing the model from that path is the
only reliable way to prevent it.

### 6.1 The G5 fallback — what the agent actually says when data is thin

A guardrail that has no voice script is a guardrail that breaks the call. When
comparables fall below threshold, the agent must degrade gracefully rather than
stall, and it must **never** quote a number it does not have.

| Contracts found | Engine returns | Agent behaviour |
|---|---|---|
| ≥ 30 | `CLEAR`, confidence ≥ 0.9 | Normal flow |
| 10–29 | `CLEAR_WITH_CONDITIONS`, reduced confidence | States the comparable **and its thinness** before the verdict |
| < 10 | `HUMAN_REVIEW_REQUIRED` | **No number may be spoken or printed.** Offers the two recovery paths below |

**Below threshold, the agent says (English; equivalents authored per language):**

> *"I can apply the rule, but I don't have enough registered contracts for a
> property like yours in that area to give you a reliable market comparison — and
> I won't quote you a percentage I can't stand behind.*
>
> *Two things I can still do. If you have your Ejari number, I can narrow it to
> your exact building. Otherwise I can send you everything I do have — the rule,
> the notice check, and what to ask for — and connect you to someone who can
> review the comparison."*

**Three properties make this work as a guardrail rather than a dead end:**

1. It **names the limit** — thin data, not a system failure
2. It **offers recovery** — the Ejari path, which usually resolves it
3. It **still delivers the artifact** — the notice check is independent of market
   data, so the caller is rarely left with nothing

The notice-validity rule requiring no market data at all is why this degrades
gracefully. **Below-threshold calls still produce a usable evidence pack**, which
is a design consequence worth stating rather than a happy accident.

### 6.2 Provenance-verifiability

`GET /provenance/{rule_id}` renders encoded logic beside the verbatim source
clause, with the official link and the current signature. Anyone verifies an
encoding in under a minute. **Authority replaced by public verifiability.**

---

## 7. Call Flow

Mapped to the canonical Track 2 shape.

| Phase | Nodes | What happens |
|---|---|---|
| **Trigger** | 1 | Resident calls. Agent discloses it is an AI, gives information from published rules and not legal advice, and states the call is recorded. Language detected from the first utterance |
| **Identify** | 4 | OTP over SMS/WhatsApp binds the session to the caller's number and signs the pack. No government identity system required |
| **Understand** | 2–3 | Triage to domain and to answerable-vs-interpretive (G2). **Diagnosis, not form-filling** — the agent discovers which facts the rule needs. Every value read back and confirmed (G3) |
| **Retrieve** | 5 | Rules API computes on snapshotted comparables. Returns state, verdict, citation, confidence |
| **Act** | 6–8 | Result rendered with the clause **cited aloud** (G1). Evidence pack generated from templates (G10) and **dispatched to the caller's phone during the call** |
| **Confirm** | 8 | Readback of what was sent and what it means |
| **Follow up** | 9 | Statutory deadline armed under explicit opt-in (G8). SMS/WhatsApp primary; voice callback optional |

**The highest-value output is "you don't have a case."** It is the deflection, and
it proves this is not a litigation funnel.

---

## 8. Data Pipeline

```
Dubai Pulse dld_rent_contracts-open   (bulk parquet, 9,798,685 rows, 200 MB)
        │
        ▼  market/normalise.py    pure rules: scope, bedrooms, area keys
        ▼  market/ingest.py       ✅ T2.1 · build time only, ~30 s
   DuckDB: data/market.duckdb
     snapshots · contracts · areas · rejections
        │
        ▼  market/aggregate.py    ✅ T2.2 · medians materialised at build time
        ▼  market/comparables.py  ✅ T2.3 · in-memory lookup, 7 µs at p95
   median annual rent BY (area_key, property_type, bedrooms)
   + contract_count, confidence, snapshot_id, computed_at
        │
        ▼
   market_average_rent → Rules API
   input_sources.market_average_rent = "dld_open_rent_contracts_derived"
```

**Nothing above the aggregate runs at request time.** A `GROUP BY` over 9.8M rows
cannot meet the 150 ms budget, so ingest and aggregation happen when the image is
built and a request only ever reads a small indexed table.

### What the ingest stores

| Table | One row per | Why it exists |
|---|---|---|
| `snapshots` | ingest run | Source name, **sha256 of the exact bytes**, `computed_at`, and every stage count. A comparable figure that cannot be traced to a file is not evidence |
| `contracts` | tenancy kept | `area_key`, `property_type`, `bedrooms`, `annual_rent` as `decimal(12,2)`, both dates |
| `areas` | resolvable area | Maps a caller's spelling to a neighbourhood without a fuzzy search at call time |
| `rejections` | reason | Named counts. A rejection nobody can name is a rejection nobody can investigate |
| `aggregates` | aggregation run | The window, the answer floor it was built under, and what it covered |
| `comparables` | (area, kind, bedrooms) | `contract_count` and `newest_contract` always; `median_annual_rent` **only at or above the floor** |

Contracts and their snapshot row are written **in one transaction**. Written
piecemeal, a crash between them leaves figures with no source, no digest and no
date, and they look entirely normal to every query that reads them.

### Scope, and why it is an intersection

`property_usage_en = 'Residential'` is not a residential tenancy. It includes
1,120,410 labour-camp contracts (median **AED 504,000**) and 1,375,195
whole-block agreements whose `annual_amount` covers every property on the
contract, not one home. A row must satisfy **all** of: residential usage, a
dwelling property type, a sub-type carrying a bedroom count, and
`no_of_prop = 1`. Neither type nor sub-type is sufficient alone — 'Room in labor
Camp' appears 3,234 times under `Flat`, and 'Studio' 6,552 times under
`Labor Camps`.

Measured effect: raw `Residential` in Jabal Ali Industrial has a median of AED
829,720; after scope rules, **AED 32,000**.

**G5 thresholds:** under 30 comparable contracts reduces confidence; under 10
returns `HUMAN_REVIEW_REQUIRED` and no number may be spoken or printed.
**Snapshots are immutable and dated**, so any past answer reproduces exactly.

### The four things a lookup can say

| Status | When | What the agent says |
|---|---|---|
| `ok` | At or above the floor, and inside `max_age` | The figure — plus its thinness under 30 contracts, plus its date past `fresh_days` |
| `insufficient_data` | Below the floor, or a cell we hold nothing for | "Only N registered contracts" — never a number |
| `stale` | **This cell's** newest contract is past `market_snapshot_max_age_days` | "Our data for that runs to July" — never a number, however thick the cell |
| `unknown_area` | We cannot resolve the area at all | "Which area?" — and `GET /areas` is what it offers next |

Freshness has two thresholds, not one. Under `market_snapshot_fresh_days` the
figure is quoted plainly; between that and `max_age` it is quoted with
`MARKET_DATA_AGEING` naming the date it rests on; past `max_age` there is nothing
to quote. Measured drift per cell is 3.4% at three months, 4.3% at six and 6.1%
at twelve, against rule bands five percentage points wide — so past a year a
stale median can flip a verdict, and under four months it cannot (D-076).

Depth and recency **accumulate rather than rank**: a thin *and* ageing comparable
carries both conditions, because reporting only the worse one would let someone
act believing they had heard everything wrong with the figure.

Staleness is asked **first**, and measured from **the cell's own newest
contract** — not from `computed_at`, and not from the release's horizon either.
Of 841 quotable cells, 98 trail the horizon by more than a month and one is 418
days old inside a release that is 193 days old. Recency decides refusals, so it
has to be the age of the evidence being quoted (D-078). Re-running the ingest over an old release must not make it
fresh, and telling someone "not enough contracts in your area" when the real
problem is a six-month-old release is both wrong and unactionable.

`Comparable` refuses to hold a `median_annual_rent` unless its status is `ok`, so
G5 at this layer is a property of the type rather than of the branch that built
the object.

---

## 9. API Surface

Seven agent-facing webhook tools, plus public and dashboard routes. **Two are
built** (T1.7); the rest are specified and land in later phases.

| Endpoint | Purpose | Guardrail | Status |
|---|---|---|---|
| `POST /agent/triage` | Domain + answerable/interpretive + distress | G2, G6 | T3 |
| `POST /agent/confirm` | Issue confirmation token after readback | G3 | T3 |
| `POST /agent/otp/send` · `/verify` | Bind session to the caller's number | — | T3 |
| `POST /evaluate` | Run a rule; returns state, verdict, citation | G1, G5, G9 · **G3 not yet enforced** | **built** |
| `POST /evidence-pack` | Render the case report + factual response template | G10 | T2.4 |
| `POST /dispatch` | Send the pack by SMS/WhatsApp | G9 | T3 |
| `POST /deadline` | Arm a reminder; requires opt-in | G8 | T3 |
| `GET /comparables` | Median rent + confidence | G5 | T2.3 |
| `GET /rules` · `GET /provenance/{id}` | Public transparency | §6.2 | T2.6 |
| `GET /officer/cases` | Mode B dashboard | G4 | T2.8 |
| `GET /healthz` | Liveness. **Fails if the corpus is unsigned.** Lists every check performed and, in `not_yet_checked`, every one that is not | G7 | **built** |

**What `/evaluate` enforces today.** G1 — a response cannot exist without a
citation. G5 — thin evidence returns `HUMAN_REVIEW_REQUIRED` **with HTTP 200**,
because it is an outcome and a 4xx would teach every client to treat honesty as a
fault. G9 — the evaluation is appended to the hash-chained audit log before the
response leaves, and every input must carry a recorded source or the request is
refused.

**G3 is specified but not enforced.** The confirmation token issued after spoken
readback arrives with the agent endpoints in Phase 3. Until then `/evaluate`
accepts unconfirmed values, and this table says so rather than implying a control
that does not exist.

**Status codes carry the ownership of a problem.** A caller who sent an unusable
value gets 422 and can fix it. An unknown rule is 404 and names what is loaded. A
rule that passed load-time validation and still cannot answer is **500**: the
corpus is wrong, not the request, and reporting it as a 4xx would send a caller
into retrying a corrected request forever against a defect only we can fix.

---

## 10. ElevenLabs Component Selection

Scored on **selection, not coverage.** Eight chosen, eight declined. This list is
the source of truth for Idea Canvas box J and must stay identical to it.

| Component | Why this use case requires it |
|---|---|
| **Agents Platform** | The conversational runtime |
| **Agent Workflows + per-node tool scoping** | The diagnose/compute/generate separation *is* G1 and G10. Triage physically cannot reach the evidence generator |
| **Scribe v2 Realtime + keyterm biasing** | "Ejari", "Makani", Dubai area names, AED amounts across three accents. A misheard number is a wrong verdict |
| **Eleven v3 TTS + multilingual** | Malayalam and Arabic are why the answer does not reach people today (PS-4) |
| **Server / client tools** | The rules engine is external and deterministic. This seam keeps the LLM out of the computation |
| **Telephony (Twilio / SIP)** | It is a phone line. Also carries the pack and the reminders by SMS |
| **Agent Testing** | Multi-run pass rates and the adversarial suites — the Stage 2 evidence |
| **Post-call webhooks** | Transcript and evaluation record to the audit store (G9) |

**Declined, with reasons:**

- **Knowledge base + RAG** — *each signed rule file carries its own `verbatim`
  clause, so the citation is already deterministic.* Retrieval would add
  uncertainty to the one thing that must never be uncertain.
- **Voice Design** — the Voice Library suffices; a bespoke voice adds nothing to
  a rights line.
- **Batch calling** — reminders are **per-case and opt-in (G8)**. Bulk outbound
  about a person's legal position is a conduct risk we will not take, and no such
  code path exists.
- **MCP servers** — no tool-discovery requirement; seven fixed webhook tools.
- **Sub-agents** — one domain in v1, so there is nothing to delegate to.
- **WhatsApp**, **Web/mobile SDKs**, **Bring-your-own LLM** — not required by the
  v1 flow.

---

## 11. Testing Strategy

**Layer 1 — rule logic.** Every band boundary on both sides. Notice period at 89,
90, 91 days. Pure functions; coverage should be total.

**Layer 2 — registry integrity.** Unsigned rule refuses to load. Tampered body
fails verification. Expired `effective_to` is not selected.

**Layer 3 — API and generator contract.** `/evaluate` rejects a missing
confirmation token. A null citation never accompanies a verdict. Thin comparables
force `HUMAN_REVIEW_REQUIRED`. **The evidence generator rejects any input that is
not a structured evaluation record** (G10). No route reaches a terminal case
status (G4).

**Layer 4 — agent behaviour (ElevenLabs Agent Testing).** Multi-run pass rates on
the primary flow, plus adversarial suites:

- callers requesting advice or outcome prediction → must escalate
- contradictory numbers → must re-confirm
- mid-call language switch
- distress → must transfer (G6)
- opt-out → suppression recorded, irreversible (G8)
- **tool-call test proving the evidence generator refuses without a confirmation
  token, and the tamper test proving the service refuses to boot**

**A judge remembers a negative test.**

---

## 12. Deployment

Single container: FastAPI serving the API, web checker, provenance pages and
officer dashboard. DuckDB baked in read-only at build time. SQLite volume for
cases. Twilio webhooks point at the same host. Runs under $20/month.

One public deployment serves as the Box N working link from 23 September.

---

## 13. Stage 2 Deliverable Mapping

| Required 14 October | Source |
|---|---|
| Live callable agent / hosted deployment | §12 |
| Recorded demo + failure paths | [DESIGN.md](DESIGN.md) §6.2 |
| Agent Testing suite and pass rates | §11 Layer 4 |
| Transcripts and post-call analysis | G9 post-call webhooks |
| One-page architecture diagram | §2 + §3 |
| Short technical README | This document, condensed |
