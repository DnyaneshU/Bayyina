# Idea Canvas — Live Working Draft

> **Status:** Living document. This is the **Stage 1 submission**, drafted
> incrementally so nothing is written the night before.
> **Deadline: 23 September 2026.** Last updated: 2026-09-07.

## How this document is used

1. Download the official ElevenLabs Idea Canvas template (see Task 0 in
   [plan.md](../plan.md)) and **record the exact word limit for each box below.**
2. Draft here. Iterate here. Keep the word count current in every box header.
3. In the final week, transcribe the approved text into the official template.
   **Submissions not made on the canvas are not reviewed** — this file is a
   drafting surface, never the submission itself.

## Marking rules taken directly from the brief

- Word limits are enforced. **Text beyond the limit is not assessed.**
- **Boxes D and J are cross-checked.** Baseline figures in D must be the figures
  the KPIs in J are measured against. Keep them in sync or lose credibility.
- **Box G is scored on selection, not coverage.** Selecting every component
  without justification scores lower than a smaller, reasoned selection.
- **Box I requires mechanisms.** Statements of intent are not scored.
- **Box N requires a working link.** No link = zero for that box.
- One canvas, one use case, one team.

## Status tracker

| Box | Topic | Criterion (weight) | Limit | Status |
|---|---|---|---|---|
| A | Submission details | — | *from template* | Not started |
| B | The idea in one line | Problem fit (25%) | *from template* | **Draft ready** |
| C | What breaks today | Problem fit (25%) | *from template* | **Draft ready** |
| D | Today's baseline | Problem fit (25%) | *from template* | Draft — **figures need sourcing** |
| E | Who buys this | Commercial (20%) | *from template* | **Draft ready** |
| F | Call flow in five steps | Agent design (25%) | *from template* | **Draft ready** |
| G | ElevenLabs components + why | Agent design (25%) | *from template* | **Draft ready** |
| H | How it integrates | Agent design (25%) | *from template* | **Draft ready** |
| I | Guardrail table (six rows) | Guardrails (20%) | *from template* | **Draft ready** |
| J | Success metrics | Commercial (20%) | *from template* | Draft — **must match D** |
| K | Risks | Guardrails (20%) | *from template* | **Draft ready** |
| L | Working by 14 October | Commercial (20%) | *from template* | **Draft ready** |
| M | Your team | Team (10%) | *from template* | **Blocked — needs team details** |
| N | Proof of build | Team (10%) | *from template* | **Blocked — needs deployed link** |

---

# Page 01 · The Opportunity

## Box A — Submission details

> **Blocked.** Team name, contact, track selection.
> Track: **Track 2 — Government Services · Rights Checks & Dispute Prevention.**

## Box B — The idea in one line

> *Draft:*

A multilingual voice line that checks a Dubai resident's rent, notice or
end-of-service position against published rules, then **assembles the evidence,
lodges the filing into the government review queue on the call, tracks the
statutory deadline and calls back before it closes** — every verdict computed by a
signed rules registry, every decision left to a human officer.

## Box C — What breaks today

> *Draft:*

Whether a rent increase is lawful is fully determined by public data: the RERA
index and the five-band table in Decree 43 of 2013. Whether a notice is valid is
date arithmetic under Law 26 of 2007. Whether a gratuity is correct is arithmetic
under Article 51 of Federal Decree-Law 33 of 2021.

None of these require judgement — yet a resident can only obtain the answer by
hiring an expert or by filing a formal dispute. **The Rental Dispute Centre is
being used as an information-retrieval system.** Cases arrive that a sixty-second
check would have prevented, and, invisibly, residents with valid positions
capitulate because nobody told them.

Three compounding failures put the answer out of reach. The published channels
operate in English and Arabic, while the affected population functions in
Malayalam, Hindi, Urdu, Tagalog and Bengali. A web form cannot help someone who
does not know that "basic versus total salary" is the field that decides their
answer — a dialogue can, because it asks only what the rule needs.

And nobody closes the loop. Even a resident who obtains the right answer is then
left to assemble documents, file correctly and track a statutory deadline across a
system they do not understand, in a language they do not read. **The answer is not
the outcome.** A resident who learns on day 88 that they had 90 days has learned
nothing useful.

## Box D — Today's baseline

> ⚠ **Every figure here must be sourced before 23 September, and must be the same
> figure the box J KPI is measured against.**

| Baseline | Value | Source status |
|---|---|---|
| Registered Dubai rental contracts, rolling 12 months | ~600,000 | ✅ Verified — Dubai Pulse `dld_rent_contracts-open` |
| RDC filing fee | 3.5% of annual rent (min/max caps apply) | ⚠ **Verify against DLD published schedule** |
| RDC annual case volume | — | ⚠ **SOURCE REQUIRED** |
| Share of RDC cases resolvable by a rules check | — | ⚠ **SOURCE REQUIRED, or state as the hypothesis under test** |
| Languages served by existing rental/labour phone channels | English, Arabic | ⚠ **Verify** |
| Time from question to answer today | Days to weeks (via filing) | ⚠ **Verify** |

**Honesty rule for this box:** where we cannot source a figure, state it as an
explicit hypothesis to be measured in the pilot rather than inventing a number.
An invented baseline that box J then "improves" is exactly what the cross-check
is designed to catch.

## Box E — Who buys this

> *Draft:*

Four buyers, one engine, in order of how quickly money moves.

**Property managers and owners' associations** pay to verify a rent increase is
lawful *before* the notice is issued — a dispute costs the landlord fees and
months, so the incentive is direct and the budget is operator-held, requiring no
procurement cycle. **PRO firms and payroll platforms** embed the gratuity check;
an incorrect final settlement creates MOHRE exposure. **Residents** use the voice
line free at the point of use. **DLD/RDC and MOHRE** are the anchor deflection
customers — the largest budget and the slowest cycle, approached with a track
record rather than a pitch deck.

The government is the eventual anchor customer, not the first one.

---

# Page 02 · The Agent

## Box F — The call flow in five steps

> *Draft:*

**1 · Greet and disclose.** The agent states that it is an AI, that it provides
information from published rules and not legal advice, and that the call is
recorded. Language is detected from the caller's first utterance.

**2 · Triage.** The agent classifies the situation into a served rule domain and,
critically, classifies it as *answerable from published rules* or *requiring
interpretation*. Interpretive questions are handed to a human immediately.

**3 · Slot-fill.** A per-domain sub-agent collects exactly the inputs the rule
declares — no more. Every amount and date is read back and confirmed in the
caller's language before it can be used.

**4 · Evaluate and explain.** The agent calls the rules registry, which computes
the verdict. The agent renders the returned result and cites the clause aloud:
"Under Decree 43 of 2013, Article 1 — because your rent is within 10% of the
market average, no increase is permitted this year."

**5 · Act, confirm and follow up.** Where there are grounds, the agent assembles
the evidence pack on the call — Ejari reference, index comparison, notice-date
analysis, computed figures, rule version and signature — reads it back, and lodges
it into the authority's officer review queue under two-key confirmation. It then
registers the statutory deadline and, under consent recorded at the start of the
call, calls back before that window closes and again when the status changes.
Where there are no grounds, it explains why, with the rule.

**The agent prepares and coordinates. A qualified officer decides. Always.**

## Box G — ElevenLabs components and why

> *Draft — scored on selection, not coverage. Six selected, three declined.*

**Agent Workflows with sub-agents and per-node tool scoping** — the
triage/verdict/action separation *is* the guardrail architecture. The triage node
physically cannot reach the filing tool.

**Scribe v2 Realtime with keyterm biasing** — "Ejari", "Makani", "Tawtheeq" and
AED amounts across five accents. A misheard number is a wrong verdict, not a
clumsy sentence.

**Eleven v3 text-to-speech, multilingual** — Malayalam, Hindi and Urdu are the
entire reason the answer does not currently reach the affected population.

**Webhook (server) tools** — the rules registry is external and deterministic by
design. This is the seam that keeps the language model out of the computation.

**Knowledge base with source attribution** — supplies the verbatim clause text so
the agent can report which document it used. It never produces the verdict.

**Agent Testing and post-call webhooks** — multi-run pass rates, adversarial
suites, and the production audit trail.

**Declined:** Voice Design — the Voice Library suffices and a bespoke voice adds
nothing to a rights line. Batch calling — we are inbound-only by design;
unsolicited outbound calls about a person's legal position is a conduct risk we
will not take. MCP — no tool-discovery requirement; three fixed webhook tools.

## Box H — How it integrates

> *Draft:*

Telephony via the native Twilio integration, with a WebRTC widget and WhatsApp as
additional channels. The agent reaches three webhook tools on our FastAPI service:
triage classification, rule evaluation, and filing preparation.

Market comparables are derived from Dubai Pulse `dld_rent_contracts-open` — 4.2
million registered Ejari contracts, ingested into DuckDB and snapshotted with an
immutable date, so any past answer is exactly reproducible. Every evaluation
records **which source produced the market average**: today
`dld_open_rent_contracts_derived`, and on institutional partnership
`rera_official_index`. The verdict logic is byte-identical either way — the pilot
upgrade is a single input source the architecture already models.

Consented access to a caller's own Ejari or MOHRE record runs through UAE Pass:
per-call, scoped and logged, with no back-door held by us. Post-call webhooks push
transcript and evaluation record to the audit store. All integration is documented
REST with typed request and response models.

## Box I — Guardrails

> *Draft — every row states the enforcing mechanism. No statements of intent.*

| Requirement | Mechanism that enforces it |
|---|---|
| The agent never answers without a citation | The explain tool's response schema requires a non-null citation; on null the workflow branches to escalation. **The answer path does not exist** |
| The agent never answers an interpretive question | Per-turn classifier for interpretation-seeking language fires a transfer from any node in the workflow |
| The agent never computes on unconfirmed data | Amounts and dates issue a confirmation token only after spoken readback; `/evaluate` rejects requests without one |
| The agent can never file on a caller's behalf | The filing tool requires that confirmation token **and** writes only to a human review queue. No code path files directly |
| The agent never calls a resident without consent | An outbound callback requires a consent token recorded on the inbound call. An opt-out ends the session immediately, writes a suppression record, and no further call can be scheduled |
| Unreviewed rule logic can never run | The loader verifies each rule's signature against a canonical hash of its body. Unsigned or tampered → **the service fails to boot** |

> Also enforced, behind these six: thin or stale market data returns
> `insufficient_data` and no number may be quoted; and every evaluation *and every
> tool call* writes an append-only record carrying inputs, rule version, signature
> and source attribution.

---

# Page 03 · The Case

## Box J — Success metrics

> ⚠ **Must be measured against the box D baselines. Keep in sync.**

| Metric | Definition | Measured against D |
|---|---|---|
| Rule coverage | Share of inbound questions inside a served deterministic domain | Baseline: none served by phone today |
| Verdict agreement rate | Engine verdict vs. eventual expert or RDC outcome | The honest accuracy number; accrues over time |
| Filing completeness | Share of lodged cases accepted without a bounce for missing evidence | Baseline: current RDC bounce rate for incomplete filings |
| Deadline saves | Consented callbacks made before a statutory window closed | Baseline: zero — no channel tracks this today |
| Officer time per case | Minutes to review a case the agent prepared vs. one filed unaided | Baseline: current officer handling time |
| Escalation precision | Of calls transferred, share that genuinely required a human | Both directions matter: over-escalation kills the economics, under-escalation kills the company |
| Containment | Answered in one call with no callback | vs. days-to-weeks via filing |
| Time to answer | Call start to verdict spoken | vs. the D baseline |
| Corpus freshness | Median days from published amendment to signed rule version | Baseline: no versioned corpus exists |

## Box K — Risks

> *Draft:*

**Comparable-unit matching is the fuzziest step** — the index is by area, type and
size, so mapping a caller's unit to the right comparable carries error. Mitigated
by preferring the Ejari number, publishing a confidence band, and refusing to
answer below a contract-count threshold.

**We hold no retained legal counsel.** Rather than rest on a disclaimer, every rule
ships a public provenance record placing the encoded logic beside the verbatim
source clause, so any reader can verify it in under a minute. The signing gate is
built and enforced at load time; reviewer appointment is a named pre-launch gate
and the seat is currently declared empty.

**Being mistaken for legal advice** is the material conduct risk. Mitigated
structurally: deterministic domains only, spoken disclosure on every call, and a
full transcript-plus-evaluation-record audit trail for any conversation.

## Box L — What will be working by 14 October

> *Draft:*

A live, callable agent running the rent-increase flow end to end in English,
Arabic and Malayalam — check, assemble the evidence pack, lodge to the officer
review queue under two-key confirmation, register the statutory deadline, and
schedule the consented callback — backed by all three signed rules and market
comparables derived from 4.2 million registered Ejari contracts.

Demonstrated failure paths: an interpretive question triggering escalation; a
tool-call test proving the filing tool refuses without a confirmation token; and a
tampered rule file causing the service to refuse to start.
Agent Testing suites with multi-run pass rates, transcripts and post-call analysis
for every demo conversation, a one-page architecture diagram, and a technical
README. The public web checker and the rule provenance pages remain live
throughout.

## Box M — Your team

> **Blocked — needs team names, roles and relevant experience.**

## Box N — Proof of build

> **Blocked — needs the deployed URL.**
> Target: public web checker + `/provenance` pages live **before 23 September**.
> Repository link also goes here. **This box scores zero without a working link.**
