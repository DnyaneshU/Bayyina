# Bayyina — Design & Concept Study

> **Status:** Final concept for the Ignyte × ElevenLabs submission.
> Source of truth for *what* we are building and *why*. Feeds Idea Canvas boxes
> A–E and J–L. Last updated: 2026-09-07.

---

## 1. Summary

**Bayyina** (بيّنة — "clear evidence") is a rights resolution workflow: it settles
the *factual position* and prepares the *case*. It does not resolve disputes —
authorities do that.

### The one sentence

> **Bayyina converts published tenancy rules into a safe, conversational workflow
> that determines what can be determined, produces the evidence a person needs to
> act, and stops whenever the facts require human judgement.**

This sentence appears in all three documents. If a decision cannot be justified
against it, the decision is wrong.

### Two layers, deliberately different

| | |
|---|---|
| **What a resident hears** | *"Call Bayyina when your landlord raises your rent or sends you a notice. It checks what the published rules say, explains why, and sends you the evidence and your next step."* |
| **What the company is** | Executable regulation as callable infrastructure — the compiler between published law and working software |

The consumer proposition is not the infrastructure thesis, and conflating them
produces marketing that speaks to nobody.

A Dubai resident calls in their own language and describes a rent increase. The
agent works out which facts the rule actually needs, collects only those, computes
the result on a signed deterministic rules engine, explains it with the clause
cited aloud, and **sends a complete evidence pack to the caller's phone before the
call ends.**

**The governing constraint, and the reason this is real:**

> **Nothing in the core product requires anyone's permission.**
> Open data, caller-stated facts, our own rules engine, our own evidence
> generator. Every government integration is an **adapter** that can be plugged in
> later — never a dependency the product waits on.

**Track:** Ignyte × ElevenLabs, Track 2 — Rights Checks & Dispute Prevention.

---

## 2. The Gap

### 2.1 What actually breaks

Whether a Dubai rent increase is lawful is fully determined by public data: the
RERA index and the five-band table in Decree 43 of 2013. Whether the notice was
validly served is date arithmetic under Law 26 of 2007, Article 14.

Neither requires judgement. Both are, in practice, unreachable.

**The resident is asked to do the hardest part themselves.** Existing digital
tools — the rent calculator, the published decree — assume you already know which
facts matter. They ask for a market area and a comparable value. A resident who
does not know that the *gap between their rent and the market average* is the
deciding variable cannot use a tool built around that variable. They do not know
what they do not know.

And the formal channel begins downstream. The Rental Dispute Centre engages
*after* the resident has already failed to resolve it — at a filing fee of 3.5% of
annual rent. **The dispute system is being used as a helpdesk**, absorbing cases a
sixty-second check would have settled, and receiving others so poorly prepared
they bounce.

Both sides lose. The resident who had a valid position capitulates because nobody
told them. The registrar processes a case that should never have been filed.

### 2.2 Why nobody has fixed it

Encoding regulation correctly, keeping it current as it amends, and holding an
audit trail proving which version applied on which date is tedious,
expert-dependent, unglamorous labour. It is not a weekend project — which is
precisely why it is defensible.

---

## 3. Problem Statements

Four, consolidated. Each is one we can independently evidence.

### PS-1 · The translation gap
The rule is deterministic; the resident cannot apply it. Published tools require
the user to already know which facts decide the answer. **A form cannot ask a
follow-up question. A conversation can.**

### PS-2 · The notice-period trap
Changes to tenancy terms require 90 days' notice before expiry. An invalid notice
settles the matter outright — and almost nobody checks. **The window to act is
itself time-bound.** A resident who learns on day 88 that they had 90 days has
learned nothing useful.

### PS-3 · Poorly prepared disputes
Cases reach the RDC missing the Ejari reference, the index comparison or the
notice analysis, and bounce back to a resident who does not know what was wrong.
**This is the institution's pain, not the resident's** — and it is the one a
Director of Rental Disputes will recognise as their own.

### PS-4 · The language and channel gap
Published channels operate in English and Arabic. The affected population
functions in Malayalam, Hindi, Urdu, Tagalog and Bengali, and is phone-first, not
app-first. This is not an accessibility nicety — **it is why the answer does not
arrive.**

---

## 4. Track 2 Qualification Filter

Gates, not preferences. Bayyina scored honestly.

| # | Criterion | Bayyina |
|---|---|---|
| 1 | Real, quantifiable government pain | ✅ PS-3; 746,853 residential contracts/yr, our own query |
| 2 | **The agent must *do* something** | ✅ Diagnoses, computes, generates the evidence pack, dispatches it to the caller's phone, arms the deadline |
| 3 | Strong reason for voice | ✅ PS-1 — the caller cannot fill a form because they do not know which field decides |
| 4 | Clear end-to-end call flow | ✅ [ARCHITECTURE.md](ARCHITECTURE.md) §7 |
| 5 | **Legitimate integration** | ✅ Dubai Pulse open data (real, 9,798,685 contract records), Twilio voice + SMS/WhatsApp (real), our own case API (real). **Government adapters declared absent, not faked** |
| 6 | Intelligent human-in-the-loop | ✅ We never submit to an authority. The resident reviews and sends. Officers decide |
| 7 | Measurable before vs. after | ✅ Box D drives Box J by construction |
| 8 | Multilingualism genuinely valuable | ✅ PS-4 is a problem statement, not a feature |
| 9 | Scales to UAE population volumes | ✅ Every tenancy renewal in Dubai |
| 10 | Guardrails demonstrable | ✅ Ten mechanisms, schema- or load-time-enforced |
| 11 | Obvious institutional buyer | ✅ "Senior Director, rental regulation & disputes" — named in the brief |
| 12 | Killer demo | ✅ §6.2 |
| 13 | Wow moment | ✅ §6.3 |

### 4.1 Red flags this design must never drift into

"AI government information assistant" · "voice chatbot for FAQs" · anything where
voice is just another UI · anything where the agent cannot produce or change
anything · anything whose core value is summarisation.

**And one more, specific to us:** any claim of government access we do not have.
A design that depends on a permission we have not been granted is vaporware,
however impressive the diagram.

---

## 5. The Product

### 5.1 The three-mode architecture — the whole strategy in one table

| Mode | What happens | Requires | Status |
|---|---|---|---|
| **A · Prepare** | Caller receives the evidence pack and a factual response template. **They** send it | Nothing but us | **This is the product. Live day one** |
| **B · Sandbox** | Case submitted to *our* case API and appears on *our* officer dashboard | Nothing but us | Built for the demo; proves the full loop |
| **C · Authority** | Case submitted directly into a government queue | A signed government integration | **Adapter interface only. Deliberately unimplemented** |

Mode C is a socket, not a promise. The demo runs A and B end to end, and we say
plainly that C is absent.

### 5.2 What the agent actually does

| # | Step | Produces |
|---|---|---|
| 1 · **Diagnose** | Discovers which facts the rule needs by asking, not by presenting a form | A filled slot set, each value read back and confirmed |
| 2 · **Verify** | Locks the session to the caller's number by OTP over SMS/WhatsApp | A signed session the evidence pack is bound to |
| 3 · **Compute** | Signed deterministic rules engine evaluates | A verdict, a citation, and a confidence |
| 4 · **Explain** | Renders the result in the caller's language, clause cited aloud | An answer the caller understands |
| 5 · **Generate** | Builds the evidence pack | **A document** — §5.4 |
| 6 · **Dispatch** | Sends the pack to the caller's phone *during the call* | Something in their hand |
| 7 · **Protect** | Arms the statutory deadline | A reminder before the window closes |

**Step 6 is the one that makes this a product rather than a helpline.** The call
ends with an artifact, not a memory.

### 5.3 Three outcomes, and only three

| State | Meaning |
|---|---|
| **CLEAR** | The rule determines the answer on the facts given |
| **CLEAR WITH CONDITIONS** | The answer holds, contingent on a stated fact we could not verify — the condition is named explicitly |
| **HUMAN REVIEW REQUIRED** | The facts do not permit a deterministic answer, or the question is interpretive |

**The third state is a product feature, not a failure.** *"I can compute the
permitted increase, but I don't have a reliable comparable for your building — I
won't give you a percentage based on an uncertain match."* Saying that out loud is
what separates this from a hallucination machine, and judges will notice.

### 5.4 The evidence pack — the central artifact

Not a transcript. A case file.

```
        BAYYINA CASE REPORT              Evaluation ID: ev_01J8X4…
        ───────────────────────────────────────────────────────────
        RESULT     Proposed increase does not appear permitted
        STATE      CLEAR  ·  confidence 1.00 (5,557 comparables)

        RULE       Decree 43 of 2013 — Article 1
                   rule version v1 · sha256:bc45809f… · provisional
        SOURCE     [verbatim clause text] · [official DLD link]

        FACTS AS STATED BY THE CALLER — not independently verified
          Current annual rent      AED 80,000
          Proposed annual rent     AED 96,000  (+20.0%)
          Area / type / bedrooms   Al Barsha · Flat · 2

        MARKET COMPARABLE
          Median annual rent       AED 87,000
          Source                   Dubai Land Department registered
                                   rental contracts (open data)
          Snapshot                 2026-02-26 · 5,557 comparable contracts
          Confidence               1.00

        COMPUTATION
          Gap below market         8.05%  → band 0 (0–10%)
          Permitted increase       0%
          Maximum lawful rent      AED 80,000

        NOTICE ANALYSIS
          Contract expiry          30 Nov 2026
          Notice served            20 Sep 2026
          Interval                 71 days   ·  Required 90 days
          Result                   Notice appears insufficient

        WHAT TO DO NEXT
          [ RDC filing checklist ]  [ Factual response template — enclosed ]

        This is not an official determination. Bayyina is not a
        government entity and does not act for any authority.
```

**Where the outcome is conditional, the pack names the condition** in the same
words the agent spoke — thin comparable data, or a market average the resident
supplied rather than one we derived. A pack that shows a figure without the
condition it rests on is the failure the outcome states exist to prevent.

**The response letter is template-generated and contains three things only:**
facts the caller stated, the verbatim rule text, and the computation. **It states;
it never argues.** No free composition by the language model.

This is not a stylistic choice. A model writing persuasive prose on a tenant's
behalf is an unlicensed legal service — and this constraint is the mechanism that
keeps us the right side of that line. Enforced in code, not by a prompt (G10).

### 5.5 Deadline protection

The caller opts in explicitly: *"remind me before the deadline."* Primary channel
is SMS or WhatsApp; a voice callback is optional and consent-gated per case.

**We do not run outbound campaigns.** Unsolicited bulk calling about a person's
legal position is a conduct risk we will not take. Per-case, consented,
caller-requested contact is a different thing, and the distinction is enforced
(G8).

### 5.6 Why voice, honestly

1. **The caller cannot fill a form, because they don't know which field decides.**
   A conversation discovers the missing fact; a form assumes you already have it.
   This is PS-1, and it is the whole answer to "why voice?"
2. **The affected population is phone-first and multilingual.** Not app-first, not
   English.
3. **Diagnosis is dialogue.** *"Did they give you a percentage, or a new annual
   figure?"* is a question a form cannot ask conditionally.

**Voice is the wrong interface for B2B** — a property manager checking 400 notices
wants an API. Same engine, different surface, later.

---

## 6. Scope, Demo, and the Wow

### 6.1 Locked MVP

| | |
|---|---|
| Jurisdiction | Dubai |
| Domain | Tenancy |
| Rules | Permitted increase (Decree 43/2013) + notice validity (Law 26/2007 Art. 14) |
| Data | Dubai Pulse `dld_rent_contracts-open`, local DuckDB |
| Languages | English, Arabic (Gulf), Malayalam |
| Output | Evidence pack + factual response template + deadline |
| Integration | Our own case sandbox; government adapter unimplemented |
| Deferred | Gratuity, fines, service charges, Abu Dhabi, B2B API |

**Gratuity moves to Phase 2.** It was insurance against the market-data risk, and
that risk died when Dubai Pulse access was confirmed. Insurance you don't need is
just scope.

### 6.2 The demo — four minutes

1. Malayalam-speaking tenant calls: *"My landlord wants to increase my rent."*
2. Agent **discovers** the facts by asking — *"Did they give you a percentage, or
   a new annual figure?"* — reading back each number in Malayalam.
3. OTP locks the session to the caller's phone.
4. Registry computes: rent sits 8.05% below market → **0% permitted.** Delivered in
   Malayalam, **Article 1 cited aloud.**
5. Notice check: 71 days against 90 → **second, independent ground.**
6. **The evidence pack arrives on the phone, on screen, during the call.**
7. Deadline armed with explicit consent.
8. **Failure path A:** *"Will I win?"* → interpretive tripwire → escalation.
9. **Failure path B:** thin comparable → **HUMAN REVIEW REQUIRED**, no number
   quoted.
10. Switch to the **Mode B sandbox review dashboard** — *our* queue, not a
    government one — showing the prepared case awaiting review.
11. The wow. §6.3.

### 6.3 The wow moment

Live: open the rent rule YAML, change one digit in the band table from `0.05` to
`0.99`, restart the service.

**It refuses to boot.** `TamperedRuleError: body of
rent_increase.dubai.decree_43_2013 v1 does not match its signature.`

Ninety seconds, and the compliance thesis is proved physically rather than
asserted. A room that has spent two years being told AI is "aligned with policy"
has not seen a system that **will not run on unreviewed logic.**

---

## 7. Users and Buyers

**The user:** a Dubai resident, disproportionately a South Asian or Filipino
expatriate, facing a rent demand they cannot evaluate in a language they read.

**The buyers**, in order of how fast money moves:

| # | Buyer | Motion |
|---|---|---|
| ① | Property managers, owners' associations | Verify a notice is lawful *before* issuing it. Operator-held budget, no procurement cycle |
| ② | Legal-service platforms, tenancy brokers | Embedded rule checks |
| ③ | Residents | Free at point of use — brand, data, goodwill |
| ④ | DLD / RDC | Deflection and case quality. Largest budget, 12–24 month cycle |

**The government is the eventual anchor customer, not the first one.** Any plan
starting with "the government will buy it" dies in Q2.

**The pitch to DLD:** *"Your dispute centre is being used as a helpdesk. We'll
give you the helpdesk — and every case that does reach you arrives with the Ejari
reference, the index comparison and the rule version attached."*

### 7.1 The company beyond the MVP

The registry — signed, versioned, cited, executable regulation — is the asset that
compounds. The resident voice line is the first surface on it; a B2B rules API is
the second. **That is the expansion story for Box E, not a second thing we are
building now.**

---

## 8. Verified Facts

Checked 2026-09-07. Re-verify before submission.

| Fact | Finding | Source |
|---|---|---|
| Rent contract data | **9,798,685 contract-level Ejari records** obtained and SHA256-verified 2026-09-09. 746,853 residential in a rolling 12 months | DLD open data ([mirror](https://github.com/dataengineergaurav/rental-market-dynamics-dubai/releases)) |
| Band methodology current | Smart Rental Index (2025-01-01) changed *valuation*, not the caps. Decree 43/2013 still governs | [DLD](https://dubailand.gov.ae/en/news-media/smart-rental-index-announcement) |
| Malayalam TTS / STT | Supported — Eleven v3, Scribe | [TTS](https://elevenlabs.io/text-to-speech/malayalam) · [STT](https://elevenlabs.io/speech-to-text/malayalam) |
| Non-UAE team eligibility | 90%+ of DIFC ecosystem founders are non-UAE nationals | [Ignyte](https://www.ignyte.ae/) |

### 8.1 Derived, not official — stated everywhere

Our comparable is **not** the official RERA index figure. The registry takes
`market_average_rent` with a `source` field: today
`dld_open_rent_contracts_derived`, on partnership `rera_official_index`. **Verdict
logic is byte-identical either way.** The agent says the source aloud, and the
evidence pack prints it.

This is honest, and it makes the pilot path concrete: **one input source, already
modelled.**

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Comparable matching is fuzzy | High | Confidence band published; below 10 contracts → HUMAN REVIEW REQUIRED, no number quoted |
| **Response letter reads as legal drafting** | **High** | Template-only, three permitted contents, no model composition (G10) |
| **Pack mistaken for an official document** | **High** | Bayyina-branded, explicit non-official notice, never styled as a government instrument |
| No retained legal counsel | High | Rules run `provisional` and the agent discloses it aloud; public provenance page lets anyone verify |
| Caller-stated facts are wrong | Medium | Pack marks every input "as stated by the caller, not independently verified" |
| Team cannot attend Demo Day | Medium | Final five chosen 19 Oct on **remote artifacts only**; recording built pitch-grade from day one |
| Perceived as legal advice | High | Deterministic domain only, spoken disclosure, full audit trail |

---

## 10. Success Metrics

Ordered by what an institutional buyer cares about, not by what is easy to count.
**Each is marked by how it can be measured** — because a KPI we cannot yet measure
should be declared as such, not quietly implied.

### Institutional outcomes — the ones that sell

| Metric | Definition | Measurable |
|---|---|---|
| **Time to deterministic answer** | Call start → verdict spoken, against a baseline of days-to-weeks via filing | ✅ **Self** |
| **Unnecessary-filing deflection** | Callers told they have no case, who consequently do not file | ⚠ **Proxy self-measurable** (callers told "no case"); true deflection needs a DLD pilot |
| **Prepared-case completeness** | Prepared cases accepted without a bounce for missing evidence — **the PS-3 number** | ⚠ **Pilot** — requires an institutional partner |
| **Deadline saves** | Reminders delivered before a statutory window closed. Baseline: zero, because nothing tracks this today | ✅ **Self** |
| **Verdict agreement rate** | Engine verdict vs. eventual expert or authority outcome. The honest accuracy number | ⚠ **Pilot or expert panel** |
| **Escalation precision** | Of calls transferred, the share genuinely requiring a human. Over-escalation kills the economics; under-escalation kills the company | ✅ **Self**, by review sampling |

### Operational health — internal, not headline

Diagnosis completion (calls reaching a determinate state without abandonment) ·
resolution-state mix across CLEAR / CONDITIONS / HUMAN REVIEW, which is the health
signal for the honesty guardrail · pack delivery rate · corpus freshness, the
median days from a published amendment to a signed rule version.

**Being explicit that three of the six headline metrics need a pilot partner is a
strength, not a gap.** It is the difference between a measurement plan and a wish
list, and it gives the institutional conversation a concrete agenda.

---

## 11. Roadmap

**Domains:** rent increase + notice validity → gratuity → fines → service charges.
Each compounds the registry with no new interface work.

**Geography:** *not* cheap. Abu Dhabi is a different regime (Tawtheeq, not Ejari).
**The architecture generalises; the corpus does not.** Each jurisdiction is a fresh
expert build.

**Integration:** Mode C adapters as authorisations are granted, one authority at a
time. **The product never waits on them.**

**The category:** executable regulation as callable infrastructure — the compiler
between published law and working software.
