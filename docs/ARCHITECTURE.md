# Bayyina — Architecture & Technical Reference

> **Status:** Living document. Source of truth for *how* it is built.
> Feeds Idea Canvas boxes F–I, and becomes the Stage 2 architecture diagram +
> technical README required on 14 October. Last updated: 2026-09-07.

---

## 1. Governing Principles

> **1 · Determinism at the core. Language only at the edge.**
> The LLM triages, slot-fills, and speaks. It never computes, decides, or interprets.

> **2 · The agent acts, but never decides.**
> It assembles, lodges, tracks and follows up. Every determination belongs to a
> human officer.

If the engine returns no citation, **the agent is structurally incapable of
answering** — it is not restrained by a prompt, it has nothing to say. If an
action would constitute a decision, **there is no code path that performs it.**

---

## 2. System Diagram

```
┌── CHANNELS ────────────────────────────────────────────────────────────┐
│  Twilio inbound  ·  consented outbound callback  ·  WhatsApp           │
│  WebRTC widget   ·  public web checker                                 │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── LISTEN ──────────────────────▼───────────────────────────────────────┐
│  Scribe v2 Realtime + keyterm biasing                                   │
│  (Ejari, RERA, Makani, Tawtheeq, MOHRE, gratuity, AED amounts)          │
│  Language auto-detect on first utterance                                │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── AGENT · ElevenLabs Workflows ▼───────────────────────────────────────┐
│                                                                         │
│  [1 Greet · Disclose · Consent] AI disclosure · recording · callback    │
│           │                      consent captured and logged (G8)       │
│  [2 Triage] served domain? answerable or interpretive?                  │
│           │                        └──────► [Human handoff] ◄──┐        │
│           ▼                                                    │ G2 G6  │
│  [3 Slot-fill sub-agent] readback + confirm → token (G3)       │        │
│           ▼                                                    │        │
│  [4 Verdict] calls registry. COMPUTES NOTHING. ────────────────┘        │
│           ▼                                                             │
│  [5 Explain] renders verdict · cites clause aloud (G1)                  │
│           ▼                                                             │
│  ══ THE ACTION LAYER — why this is not a chatbot ══                     │
│  [6 Assemble] builds the evidence pack on the call                      │
│           ▼                                                             │
│  [7 Lodge]    two-key submit → review queue (G4)                        │
│           ▼    TOOL-SCOPED: only this node holds the filing tool        │
│  [8 Track]    registers the statutory deadline                          │
│           ▼                                                             │
│  [9 Follow-up] consented outbound callback before the window closes     │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── HUMAN-IN-THE-LOOP ───────────▼───────────────────────────────────────┐
│  OFFICER REVIEW QUEUE — every lodged case lands here                    │
│  The agent prepares. A qualified officer approves, amends or rejects.   │
│  NO CODE PATH BYPASSES THIS QUEUE.                                      │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
                                ▼   (post-approval, out of our scope)
                     Execution in the authority's own system

┌── CONSENTED IDENTITY (sandboxed in v1) ────────────────────────────────┐
│  UAE Pass — caller authorises access to their own Ejari / MOHRE record  │
│  Per-call, scoped, logged. We hold no back-door.                        │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── REGULATORY RULES REGISTRY ◄── THE ASSET ─────────────────────────────┐
│  rent_increase.dubai.decree_43_2013      @v1                            │
│  notice_validity.dubai.law_26_2007_a14   @v1                            │
│  gratuity.uae.decree_33_2021_a51         @v1                            │
│                                                                         │
│  pure fn(inputs) → {verdict, computed, rule_id, rule_version,           │
│                     citation, confidence, review_status, input_sources} │
│  UNSIGNED OR TAMPERED → SERVICE REFUSES TO BOOT (G7)                    │
│  every evaluation and every tool call → immutable record (G9)           │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
┌── SOURCES ─────────────────────▼───────────────────────────────────────┐
│  Source-law corpus → RAG for CITATION ONLY, never computation           │
│  DuckDB: dld_rent_contracts-open → comparable medians, snapshotted      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack and Why

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | The work is data + rules; the ETL and the engine want the same language |
| API | FastAPI | Typed request/response models give the agent tool contracts for free |
| Rule schema | Pydantic v2 | Rule validation *is* schema validation. Malformed rule = load failure |
| Rule storage | YAML in `rules/`, in git | Version control **is** the version history. Diffs are reviewable by a non-programmer |
| Market data | DuckDB | 4.2M rows, analytical queries, single file, zero infrastructure |
| Frontend | Static HTML/CSS/JS + Jinja | No build step. The provenance page renders from the same YAML the engine loads |
| Tests | pytest | — |
| Voice | ElevenLabs Agents | Configuration, not code. Webhook tools point at our FastAPI |
| Deploy | Single container | Web checker, API and agent webhooks in one service |

**Rejected:** a separate SPA framework (build complexity for no gain); a hosted
database (a read-only DuckDB file is simpler); a rules DSL (YAML + Pydantic is
enough for three rules; a DSL is premature abstraction).

---

## 4. Repository Structure

```
IgNyte/
├── plan.md
├── README.md                        # Stage 2 technical README
├── docs/
│   ├── DESIGN.md                    # what and why
│   ├── ARCHITECTURE.md              # this file — how
│   └── CANVAS.md                    # live Stage 1 submission draft
├── rules/                           # THE CORPUS — signed, versioned
│   ├── rent_increase.dubai.decree_43_2013.v1.yaml
│   ├── notice_validity.dubai.law_26_2007_a14.v1.yaml
│   └── gratuity.uae.decree_33_2021_a51.v1.yaml
├── src/bayyina/
│   ├── registry/
│   │   ├── schema.py                # Pydantic rule models
│   │   ├── signing.py               # canonical hash, sign, verify
│   │   ├── loader.py                # G7 — refuses unsigned or tampered
│   │   └── evaluator.py             # dispatch inputs → verdict
│   ├── rules_logic/
│   │   ├── banded_percentage.py
│   │   ├── notice_period.py
│   │   └── gratuity.py
│   ├── actions/                     # THE ACTION LAYER
│   │   ├── evidence_pack.py         # assemble the filing document
│   │   ├── review_queue.py          # lodge — the only write path
│   │   └── deadlines.py             # register and schedule callbacks
│   ├── market/
│   │   ├── ingest.py
│   │   └── comparables.py
│   ├── guardrails/
│   │   ├── triage.py                # G2 interpretive, G6 distress
│   │   ├── tokens.py                # G3 confirmation tokens
│   │   └── consent.py               # G8 consent and opt-out
│   ├── audit.py                     # G9 evaluation + tool-call trace
│   └── api/
│       ├── app.py
│       ├── routes_evaluate.py
│       ├── routes_agent.py
│       ├── routes_filing.py
│       └── routes_provenance.py
├── web/
├── agent/
└── tests/
```

---

## 5. Rule Specification

### 5.1 Format

```yaml
id: rent_increase.dubai.decree_43_2013
version: 1
jurisdiction: AE-DU
effective_from: 2013-12-09
effective_to: null

source:
  document_id: dubai_decree_43_2013
  title: "Decree No. (43) of 2013 Determining Increases in Real Property Rent"
  clause: "Article 1"
  url: "https://dubailand.gov.ae/"
  verbatim: |
    Sets maximum permitted percentage increase in property rent by reference to
    how far the current rent falls below the average market rental value for a
    similar property, as determined by the RERA rental index.

logic: banded_percentage

inputs:
  current_annual_rent:  { type: money, currency: AED, required: true }
  market_average_rent:  { type: money, currency: AED, required: true,
                          source_field: market_average_source }
  proposed_annual_rent: { type: money, currency: AED, required: true }

bands:                       # gap = (market_average - current) / market_average
  - { gap_from: 0.00, gap_to: 0.10, max_increase: 0.00 }
  - { gap_from: 0.10, gap_to: 0.20, max_increase: 0.05 }
  - { gap_from: 0.20, gap_to: 0.30, max_increase: 0.10 }
  - { gap_from: 0.30, gap_to: 0.40, max_increase: 0.15 }
  - { gap_from: 0.40, gap_to: null, max_increase: 0.20 }

review_notes:
  - "Band boundaries are inclusive at the upper bound. Confirm with reviewer."

approval:
  status: provisional        # unsigned | provisional | certified
  approved_by: "Bayyina team"
  approved_at: "2026-09-07T00:00:00Z"
  signature: "sha256:..."    # canonical hash of this rule minus the approval block
```

### 5.2 Approval status — the three states

| Status | Loader behaviour | Agent behaviour |
|---|---|---|
| `unsigned` | **Raises `UnsignedRuleError`. The service does not boot.** | — |
| `provisional` | Loads | **Discloses aloud that the encoding is provisional and pending qualified review** |
| `certified` | Loads | Speaks normally |

**We ship as `provisional` and we say so.** This is the honest position given we
hold no retained counsel ([DESIGN.md](DESIGN.md) §9), and stating it is worth more
than implying a reviewer we do not have.

### 5.3 The three v1 rules

| Rule | Logic | Key detail |
|---|---|---|
| `rent_increase.dubai.decree_43_2013` | `banded_percentage` | Five bands: 0/5/10/15/20% |
| `notice_validity.dubai.law_26_2007_a14` | `notice_period` | ≥90 days before expiry |
| `gratuity.uae.decree_33_2021_a51` | `gratuity` | <1yr none; 1–5yr 21 days/yr; >5yr 21×5 + 30/yr after; capped at 2 years' wage; **basic** salary only |

**Open review note on gratuity:** the daily-wage convention (`basic ÷ 30` vs.
`basic × 12 ÷ 365`) is a genuine ambiguity. v1 encodes `basic ÷ 30` and records
the alternative in `review_notes`. **The provenance mechanism surfacing a question
rather than burying it.**

### 5.4 Evaluation record

```json
{
  "eval_id": "ev_01J8X...",
  "rule_id": "rent_increase.dubai.decree_43_2013",
  "rule_version": 1,
  "rule_signature": "sha256:9f2a...",
  "review_status": "provisional",
  "inputs": { "current_annual_rent": 85000, "market_average_rent": 91000,
              "proposed_annual_rent": 102000 },
  "input_sources": { "market_average_rent": "dld_open_rent_contracts_derived",
                     "market_snapshot": "2026-Q3" },
  "verdict": "not_permitted",
  "computed": { "gap_pct": 0.0659, "band_matched": 0, "max_increase_pct": 0.00,
                "max_lawful_rent": 85000, "proposed_increase_pct": 0.20 },
  "citation": { "document_id": "dubai_decree_43_2013", "clause": "Article 1" },
  "confidence": 0.94,
  "created_at": "2026-09-07T11:04:22Z"
}
```

---

## 6. Guardrails — Mechanisms, Not Intentions

Each is enforced by a schema contract, a load-time check, or a tool scope.
**None is a prompt instruction.** Rows G1–G6 form Idea Canvas box I; G7–G9 are the
architectural controls behind them.

| # | Guardrail | Mechanism | Where |
|---|---|---|---|
| **G1** | **Citation-or-silence** | The Explain tool's response schema requires a non-null `citation`. On null the workflow branches to escalation — **the answer path does not exist** | `api/routes_agent.py` + workflow edge |
| **G2** | **Interpretive tripwire** | Per-turn classifier for interpretation-seeking language ("will I win", "should I"). Fires transfer from any node | `guardrails/triage.py` |
| **G3** | **Confidence floor** | Amounts and dates issue a confirmation token only after spoken readback. `/evaluate` rejects requests without one | `guardrails/tokens.py` |
| **G4** | **Two-key filing** | The filing tool requires that token **and** writes only to the officer review queue. **No code path files directly** | `actions/review_queue.py` |
| **G5** | **Stale / thin data guard** | Snapshots carry a validity window; fewer than 10 comparable contracts returns `insufficient_data` and no number may be quoted | `market/comparables.py` |
| **G6** | **Distress detection** | Homelessness, abuse, self-harm signals → immediate warm transfer, logged | `guardrails/triage.py` |
| **G7** | **Unsigned-rule refusal** | The loader verifies each signature against a canonical hash of the rule body. Unsigned or tampered → **the service fails to boot** | `registry/loader.py` |
| **G8** | **Consent and opt-out** | An outbound callback requires a recorded consent token from the inbound call. Opt-out ends the session immediately, writes a suppression record, and no further call can be scheduled | `guardrails/consent.py` |
| **G9** | **Auditable lineage** | Every evaluation *and every tool call* writes an append-only record: inputs, rule version, signature, source attribution, outcome, timestamp | `audit.py` |

**G7 answers the brief's hardest requirement** — *"a qualified person must review
and sign off the rule-matching logic before launch, not only individual filings."*
It is a load-time failure, not a policy document. **It is also the demo's wow
moment** ([DESIGN.md](DESIGN.md) §5.5).

**G4 is the human-in-the-loop enforcement.** The agent is never the officer.

### 6.1 Provenance-verifiability

`GET /provenance/{rule_id}` renders the encoded logic beside the verbatim source
clause with a link to the official document and the current signature, so **any**
reader verifies an encoding in under a minute. Authority is replaced by public
verifiability.

---

## 7. ElevenLabs Component Selection

Box G is scored on **selection, not coverage.** Six chosen, three declined.

| Component | Why this use case requires it |
|---|---|
| **Agent Workflows + sub-agents + per-node tool scoping** | The triage/verdict/action separation *is* G1 and G4. The Triage node physically cannot reach the filing tool |
| **Scribe v2 Realtime + keyterm biasing** | "Ejari", "Makani", AED amounts across five accents. A misheard number is a wrong verdict |
| **Eleven v3 TTS + multilingual** | Malayalam/Hindi/Urdu is the reason the answer does not reach people today (PS-5) |
| **Webhook (server) tools** | The registry is external and deterministic. This seam keeps the LLM out of the computation |
| **Knowledge base + source attribution** | Supplies the verbatim clause so the agent reports which document it used. It never produces the verdict |
| **Agent Testing + post-call webhooks** | Stage 2 evidence, and the G9 audit trail |

**Declined, with reasons:** *Voice Design* — the Voice Library suffices; a bespoke
voice adds nothing to a rights line. *Batch calling* — outbound is **per-case and
consent-gated (G8)**, never campaign-driven; unsolicited bulk calls about a
person's legal position is a conduct risk we will not take. *MCP* — no
tool-discovery requirement; four fixed webhook tools.

---

## 8. Call Flow

Mapped to the canonical Track 2 shape: **trigger → identify/consent → understand
→ retrieve → act → confirm → follow up.**

| Step | Node | What happens |
|---|---|---|
| **Trigger** | 1 | Resident calls. Agent states it is an AI, provides information from published rules and not legal advice, and that the call is recorded. Language detected from the first utterance |
| **Identify / consent** | 1 | Consent for a follow-up callback is requested and recorded (G8). Optional UAE Pass authorisation for the caller's own Ejari record |
| **Understand** | 2–3 | Triage to a served domain and to answerable-vs-interpretive (G2). Per-domain slot-fill; every amount and date read back and confirmed (G3) |
| **Retrieve** | 4 | Registry computes the verdict. Comparables drawn from the snapshotted contract data |
| **Act** | 5–7 | Verdict rendered with the clause **cited aloud** (G1). Evidence pack assembled. Filing lodged to the officer review queue under two-key confirmation (G4) |
| **Confirm** | 7 | Full readback of what was lodged, and what happens next |
| **Follow up** | 8–9 | Statutory deadline registered; consented callback scheduled before the window closes and on status change |

**The "you have no case" answer is the highest-value output for the buyer.** It is
the deflection, and it proves we have not built a litigation funnel.

---

## 9. Data Pipeline

```
Dubai Pulse dld_rent_contracts-open   (OAuth API or bulk CSV)
        │
        ▼  market/ingest.py
   DuckDB: data/rent_contracts.duckdb
        │
        ▼  market/comparables.py
   median annual rent BY (area, property_type, bedrooms)
   + contract_count, confidence, snapshot_id, computed_at
        │
        ▼
   market_average_rent → registry input
   input_sources.market_average_rent = "dld_open_rent_contracts_derived"
```

**G5 thresholds:** fewer than 30 contracts in the window reduces confidence; fewer
than 10 returns `insufficient_data`, and the agent must ask for the Ejari number
rather than answer. **Snapshots are immutable and dated**, so any past answer is
exactly reproducible.

---

## 10. API Surface

| Endpoint | Purpose | Guardrail |
|---|---|---|
| `POST /evaluate` | Run a rule | G1, G3 |
| `GET /comparables` | Median rent + confidence for a comparable | G5 |
| `GET /rules` | Loaded rules, versions, approval status | transparency |
| `GET /provenance/{rule_id}` | Encoded logic ↔ verbatim source clause | §6.1 |
| `POST /agent/triage` | Answerable vs. interpretive; distress | G2, G6 |
| `POST /agent/confirm` | Issue a confirmation token after readback | G3 |
| `POST /agent/consent` | Record callback consent or opt-out | G8 |
| `POST /actions/evidence-pack` | Assemble the filing document | — |
| `POST /actions/lodge` | Submit to the officer review queue | G4 |
| `POST /actions/deadline` | Register a statutory deadline and callback | G8 |
| `GET /healthz` | Liveness. **Fails if the corpus is unsigned** | G7 |

---

## 11. Testing Strategy

**Layer 1 — rule logic (pytest).** Every band boundary, both sides. Every gratuity
tier including the two-year cap and the sub-one-year case. Notice period at 89, 90
and 91 days. Pure functions; coverage should be total.

**Layer 2 — registry integrity (pytest).** Unsigned rule refuses to load. Tampered
body fails verification. An expired `effective_to` is not selected.

**Layer 3 — API contract (pytest + TestClient).** `/evaluate` and `/actions/lodge`
reject a missing confirmation token. A null citation is never returned alongside a
verdict. An outbound callback cannot be scheduled without a consent token.

**Layer 4 — agent behaviour (ElevenLabs Agent Testing).** Multi-run pass rates on
the primary flow, plus adversarial suites:

- callers requesting legal advice or outcome prediction → must escalate
- callers giving contradictory numbers → must re-confirm
- callers switching language mid-call
- callers in distress → must transfer (G6)
- callers opting out → session ends, suppression recorded (G8)
- **tool-call test proving the filing tool refuses without a confirmation token**

That last one is the highest-value single test in the project. **A judge remembers
a negative test.**

---

## 12. Deployment

Single container: FastAPI serving the API, the static web checker and the
provenance pages. DuckDB baked in at build time (read-only). Agent webhooks point
at the same host. One public deployment serves as the Box N working link from
23 September.

---

## 13. Stage 2 Deliverable Mapping

| Required 14 October | Source |
|---|---|
| Live callable agent / hosted deployment | §12 |
| Recorded demo + failure paths | [DESIGN.md](DESIGN.md) §5.4 |
| Agent Testing suite and pass rates | §11 Layer 4 |
| Transcripts and post-call analysis | G9 post-call webhooks |
| One-page architecture diagram | §2 |
| Short technical README | This document, condensed to `README.md` |
