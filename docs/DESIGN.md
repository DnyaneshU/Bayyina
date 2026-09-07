# Bayyina — Design & Concept Study

> **Status:** Living document. Source of truth for *what* we are building and *why*.
> Feeds Idea Canvas boxes A–E and J–L. Last updated: 2026-09-07.

---

## 1. Summary

**Bayyina** (بيّنة — "clear evidence") is a **rights resolution service**, not a
rights answering service.

A Dubai resident calls one number in their own language. The agent checks their
situation against published rules, **assembles the evidence pack, lodges the
filing into the government review queue on the call, registers the statutory
deadline, and calls back before it closes.**

Every verdict is computed by a signed, versioned rules registry — never by a
language model. Every action lands in a human officer's queue — never in a final
decision.

**Track:** Ignyte × ElevenLabs, Track 2 — Rights Checks & Dispute Prevention.

---

## 2. The Gap

### 2.1 The reframe

The gap is not "residents don't know their rights." That framing caps out as a
charity hotline. The actual gap is infrastructural:

> Governments publish regulation as prose. Every party downstream — landlords,
> property managers, employers, brokers and residents — re-implements that prose
> by hand, independently, from memory, and gets it wrong. There is no canonical,
> versioned, machine-executable form of *what the rule actually says*.

Dubai Decree 43/2013 exists as a PDF. From that single document, four separate
private implementations are maintained: the property manager issuing notices, the
broker advising the landlord, the tenant guessing, and the Rental Dispute Centre
adjudicating the disagreements this produces.

**The fourth implementation is a court.** The dispute system is functioning as the
reconciliation layer for a missing piece of infrastructure.

### 2.2 Why nobody has fixed it

The work is unglamorous. Encoding regulation correctly, keeping it current as it
amends, and holding an audit trail proving which version applied on which date is
tedious, ongoing, expert-dependent labour. It is not a weekend project — which is
precisely why it is defensible.

---

## 3. Problem Statements

### PS-1 · The rent increase asymmetry

A tenant receives a demand for a 20% increase. Whether it is lawful is fully
determined by public data — the RERA index and a five-band table. The landlord's
agent knows this. The tenant usually does not. Outcome today: capitulate and
overpay, or file at the Rental Dispute Centre at 3.5% of annual rent and wait.
**Both outcomes are failures of information, not of justice.**

### PS-2 · The notice-period trap

Changes to tenancy terms require 90 days' notice before expiry. A late or
improperly served notice is invalid — a fact that resolves the dispute outright,
and one almost nobody checks. **And the window to respond is itself time-bound:**
a resident who learns their rights on day 88 has learned them too late.

### PS-3 · The gratuity miscalculation

21 days' **basic** wage per year for years 1–5, 30 days thereafter, capped at two
years' pay. Most UAE SMEs have no in-house HR and compute on *total* salary, or
omit the post-five-year uplift. Workers accept the number handed to them. MOHRE
absorbs the difference as complaints that are arithmetic, not disputes.

### PS-4 · The dispute system as a helpdesk

Cases arrive at RDC and MOHRE that a sixty-second check would have prevented — and
those that *should* arrive often arrive malformed, missing the Ejari reference or
the index comparison, and bounce back to the resident.

### PS-5 · The channel and language gap

The Dubai REST calculator exists and is unreachable for the population that needs
it most — phone-first, functioning in Malayalam, Hindi, Urdu, Tagalog and Bengali.
No government line staffs those. And a web form cannot help someone who does not
know that "basic versus total salary" is the field that decides their answer.
**A dialogue can, because it asks only what the rule needs.**

### PS-6 · Nobody closes the loop

Even a resident who gets the right answer is then left alone to assemble
documents, file correctly, and track a deadline across a system they do not
understand, in a language they do not read. **The answer is not the outcome.**

---

## 4. Track 2 Qualification Filter

Every candidate problem statement must clear this bar before it is considered.
These are gates, not preferences. Bayyina is scored against them below, honestly.

| # | Criterion | Bayyina |
|---|---|---|
| 1 | **Real, painful, quantifiable government pain** — not "AI could help" | ✅ RDC used as an information-retrieval system; ~600k rental contracts/yr |
| 2 | **The agent must *do* something** — resolve, initiate, coordinate, verify, prepare, follow up | ✅ §5.3 — assembles evidence, lodges filing, tracks deadline, calls back |
| 3 | **A strong reason for voice** — if a web form is trivially better, drop it | ✅ Caller does not know which fields decide their answer; phone-first, multilingual population |
| 4 | **A clear end-to-end call flow** — trigger → identify/consent → understand → retrieve → act → confirm → follow up | ✅ [ARCHITECTURE.md](ARCHITECTURE.md) §8 |
| 5 | **Legitimate government system integration** via documented APIs/webhooks | ⚠ One real (Dubai Pulse, 4.2M contracts), two sandboxed (Ejari via UAE Pass, RDC filing queue). **Stated honestly, not disguised** |
| 6 | **Intelligent human-in-the-loop** — the AI is never the government officer | ✅ Strongest area. Two-key filing; officers decide, always |
| 7 | **Measurable before vs. after** | ✅ Box D baselines drive Box J KPIs by construction |
| 8 | **Multilingualism genuinely valuable**, not bolted on | ✅ It *is* PS-5 — the language gap is part of the problem |
| 9 | **Scales to UAE population volumes** | ✅ Every tenant and every departing employee in the UAE |
| 10 | **Guardrails obvious and demonstrable** | ✅ Nine mechanisms, all enforced by schema or load-time check |
| 11 | **Obvious institutional buyer** | ✅ "Senior Director, rental regulation & disputes" and "Director of Labour Relations" are named in the brief |
| 12 | **Killer 3–5 minute demo** | ✅ §5.4 |
| 13 | **A "wow, I didn't know voice AI could do that" moment** | ✅ §5.5 — the live tamper demo |

### 4.1 Red flags this design must never drift into

- "AI government information assistant" · "Voice chatbot for FAQs"
- "AI that tells citizens what documents they need"
- Anything where voice is just another UI
- Anything where the agent cannot access or change anything
- Anything whose core value is summarisation

**Criterion 2 is the one we nearly failed.** An early draft treated filing as a
tail step. It is now the spine — see §5.3. If a future change reduces Bayyina to
answering questions, that change is wrong.

---

## 5. The Product

### 5.1 The asset — the Regulatory Rules Registry

Rules as signed, versioned, executable data. Each rule is:

- **Executable** — a pure function, inputs → verdict, not a paragraph
- **Versioned and effective-dated** — a 2024 contract is judged by the 2024 rule
- **Signed** — loadable only when an approver has signed that exact version
- **Cited** — every output carries source document and clause
- **Logged** — every evaluation is immutable: inputs, version, output, timestamp

This is the company. It compounds, it cannot be cloned in a sprint, and it makes
every action above it defensible.

### 5.2 The interfaces

| Interface | Segment | Status |
|---|---|---|
| **Voice agent** | Residents | v1 — the competition build |
| **Public web checker** | Residents; property managers informally | v1 — ships first, is the Box N link |
| **REST API / batch** | Property managers, payroll providers | Designed for, not built |

### 5.3 What the agent actually does — the spine

Answering is step one of five. Steps 2–5 are why this is not a chatbot.

| # | Action | What it produces | Boundary |
|---|---|---|---|
| **1 · Check** | Situation evaluated against the signed rule | Verdict + cited clause + computed figures | Deterministic domains only |
| **2 · Assemble** | Evidence pack built on the call | A document: Ejari reference, index comparison, notice-date analysis, computed figures, rule version and signature | The agent drafts; it never argues |
| **3 · Lodge** | Filing submitted to the government review queue | A queued case with a two-key confirmation token | **A human officer decides. Always.** |
| **4 · Track** | Statutory deadline registered | A dated obligation (e.g. the 90-day notice window) | Only deadlines fixed by published rule |
| **5 · Follow up** | Consented callback before the window closes, and on status change | An outbound call under recorded consent | Consent captured on the inbound call; opt-out honoured immediately and logged |

**Step 4 is what makes this a coordination product rather than a lookup.** A
resident who learns on day 88 that they had 90 days has learned nothing useful.

### 5.4 The demo — four minutes

1. A Malayalam-speaking tenant calls. Landlord demands 20%.
2. Agent collects the Ejari details, calls the registry: rent sits 7% below market
   → **0% permitted**. Answer in Malayalam, **Article 1 cited aloud.**
3. Agent checks the notice date: served 71 days before expiry → **notice invalid**,
   a second and independent ground.
4. Agent **assembles the evidence pack**, reads back the summary, and **lodges it
   to the review queue** — showing the two-key token on screen.
5. Agent **registers the deadline** and takes recorded consent to call back.
6. **Failure path A:** caller asks *"will I win?"* → interpretive tripwire →
   warm transfer.
7. **Failure path B:** tool-call test showing the filing tool **refusing** without
   a confirmation token.
8. **The wow.** §5.5.

### 5.5 The wow moment

Live on stage: open the rent rule YAML, change one digit in the band table from
`0.05` to `0.99`, restart the service.

**It refuses to boot.** `TamperedRuleError: body of
rent_increase.dubai.decree_43_2013 v1 does not match its signature.`

Ninety seconds, and the entire compliance thesis is proved physically rather than
asserted. A government audience has not seen an AI system that will not run on
unreviewed logic.

### 5.6 Why voice, honestly

1. **The query shape is conversational.** A resident does not know that "basic vs.
   total salary" is the deciding field. They cannot fill a form correctly because
   they do not know what matters. Slot-filling asks only what the rule needs.
2. **The population with the highest information asymmetry is phone-first and
   multilingual.** Not app-first. Not English.
3. **Steps 4 and 5 require an outbound channel.** A deadline callback is a phone
   call; there is no form equivalent.

**Voice is the wrong interface for B2B.** A property manager checking 400 renewal
notices wants an API. The registry serves both; we build one.

---

## 6. Users and Buyers

### 6.1 The user

A Dubai resident — disproportionately a South Asian or Filipino expatriate worker
— facing a rent demand, a notice, or a final settlement, who cannot currently get
a factual answer, let alone a filed case, in a language they speak.

### 6.2 The buyers, in order of how fast money actually moves

| # | Buyer | Motion | Reality |
|---|---|---|---|
| ① | Property managers, owners' associations | Verify a notice is lawful *before* sending | Operator-held budget, no procurement cycle |
| ② | PRO firms, payroll platforms, SME employers | Embedded gratuity verification | Distribution through payroll platforms |
| ③ | Residents | Free at point of use | Builds brand, data, political goodwill |
| ④ | DLD/RDC, MOHRE | Deflection + case-quality contract | Largest, 12–24 month cycle |

**The government is the eventual anchor customer, not the first one.** Any plan
starting with "the government will buy it" dies in Q2.

### 6.3 The pitch to DLD

> "Your dispute centre is being used as a helpdesk. We'll give you the helpdesk —
> and every case that does reach you arrives pre-validated, with the Ejari
> reference, the index comparison and the rule version attached."

Three-sided saving: fewer meritless filings, better-formed filings, fewer bounces.

---

## 7. Verified Facts

Checked 2026-09-07. Re-verify before submission.

| Fact | Finding | Source |
|---|---|---|
| Rent contract data | `dld_rent_contracts-open` — 4.2M+ registered Ejari contracts back to 1997, free, OAuth API + bulk CSV | [Dubai Pulse](https://www.dubaipulse.gov.ae/data/dld-registration/dld_rent_contracts-open) |
| Band methodology current? | Smart Rental Index (live 2025-01-01) changed *valuation*, not the caps. Decree 43/2013 still governs percentages | [DLD](https://dubailand.gov.ae/en/news-media/smart-rental-index-announcement) |
| Malayalam TTS | Supported, Eleven v3 | [ElevenLabs](https://elevenlabs.io/text-to-speech/malayalam) |
| Malayalam STT | Supported, Scribe | [ElevenLabs](https://elevenlabs.io/speech-to-text/malayalam) |
| Non-UAE team eligibility | 90%+ of DIFC ecosystem founders are non-UAE nationals | [Ignyte](https://www.ignyte.ae/) |

### 7.1 The derived-vs-official distinction

Our computed market average is **not** the official RERA index figure. This must
be explicit, never glossed.

- The registry takes `market_average_rent` **with a `source` field**
- Today: `source = dld_open_rent_contracts_derived`
- On partnership: `source = rera_official_index`
- **Verdict logic is byte-identical either way.** Only the input source changes
- The agent states the source aloud: *"based on registered Ejari contracts for
  comparable units in your area"*

This makes "path to a named institutional pilot" concrete: **the pilot upgrade is
swapping one input source the architecture already models.**

---

## 8. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Comparable-unit matching is fuzzy | High | Prefer Ejari number; publish a confidence band; refuse below a contract-count threshold |
| No qualified legal reviewer | High | Provenance-verifiability replaces authority (§9). Rules run as `provisional` and the agent discloses it aloud |
| Team cannot attend Demo Day | Medium | Final five are chosen 19 Oct on **remote artifacts only**. The recording is built pitch-grade from day one |
| Rule encoding wrong | High | Public provenance record; signature refuses tampered bodies at boot |
| Outbound callback misused | High | Consent captured and recorded on the inbound call; opt-out immediate and logged (G8) |
| Ejari / UAE Pass access unavailable | Low | Not a v1 dependency; caller states details, consented lookup is the enhancement |
| Perceived as legal advice | High | Deterministic domains only; spoken disclosure; full audit trail |

---

## 9. Compliance Posture

We hold no retained counsel. The honest and stronger answer replaces **authority**
with **verifiability**:

- The signing gate is architecture — `approved_by`, `approved_at`, load-time
  refusal. Rules carry a status: `unsigned` (refuses to load), `provisional`
  (loads, and **the agent discloses it aloud on every call**), or `certified`
  (a qualified reviewer has signed).
- **We run as `provisional` and we say so.** That is the honest position, and
  stating it is worth more than implying counsel we do not have.
- Every rule ships a **public provenance record**: encoded logic beside the
  verbatim source clause and a link to the official document. Any reader verifies
  an encoding in under a minute.

The brief demands the boundary be *"held in the design rather than the
disclaimer."* Public, independent verifiability **is** design.

---

## 10. Success Metrics

| Metric | Definition | Ties to Box D baseline |
|---|---|---|
| **Rule coverage** | Share of inbound questions inside a served domain | No phone channel serves these today |
| **Verdict agreement rate** | Engine verdict vs. eventual expert or RDC outcome | The honest accuracy number |
| **Filing completeness** | Share of lodged cases accepted without a bounce for missing evidence | Baseline: current RDC bounce rate |
| **Deadline saves** | Callbacks made before a statutory window closed | Baseline: zero — nobody tracks this today |
| **Escalation precision** | Of calls transferred, share genuinely requiring a human | Over-escalation kills economics; under-escalation kills the company |
| **Containment** | Resolved in one call, no callback | vs. days-to-weeks via filing |
| **Corpus freshness** | Median days from published amendment to signed rule version | Baseline: no versioned corpus exists |

---

## 11. Roadmap

**By domain:** rent increase → notice validity → gratuity → contract-type disputes
→ fine grounds → service-charge disputes. Each compounds the registry with no new
interface work.

**By geography** — *not* cheap. Abu Dhabi is a different regime (Tawtheeq, not
Ejari). Saudi has its own labour law and its own Ejar. **The architecture
generalises; the corpus does not.** Each jurisdiction is a fresh expert build.

**The category:** executable regulation as callable infrastructure — the compiler
between published law and working software.
