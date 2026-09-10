# Idea Canvas — Working Draft

> **Rebuilt 2026-09-09 against the official template.** The brief described 14
> boxes (A–N); the actual canvas has **17 (A–Q)** across five sections, with far
> tighter limits and three boxes we had not planned for.
> **Deadline: 23 September 2026.**

## Scoring — from the template itself

| Criterion | Weight | Boxes |
|---|---|---|
| Problem fit and depth of institutional understanding | **25%** | B, C, D, **F, G, H** |
| Agent design and use of the ElevenLabs stack | **25%** | I, J, L |
| Guardrail and compliance design | **20%** | K, N |
| Commercial viability and readiness to build | **20%** | E, M, O |
| Team | **10%** | P, Q |

## Hard rules on the template

- **Box A is pass/fail.** *"Incomplete submissions are screened out before scoring."*
- **Box F may be verified.** *"We may contact them. Desk research alone scores in the bottom band."*
- **Box G is a trap for teams without research.** *"If nothing changed, you have not spoken to enough people."*
- **D cross-checks against M** (not J). M allows **max 3 KPIs**.
- **Box K rows are prescribed.** We do not choose them.
- **Box J:** *"Ticking everything scores lower than ticking four with reasons."*
- **Box Q requires two links**, one being a 60-second video.
- Box C: *"Do not describe your solution here."*
- Box B: *"No adjectives."*

## Status

| Box | Limit | Status |
|---|---|---|
| A Submission details | Structured · **pass/fail** | ⛔ Team details |
| B Idea in one line | **25 words** | ✅ **23** |
| C What breaks today | **120 words** | ✅ **117** |
| D Today's baseline | Numbers only | ✅ Verified |
| E Who buys this | **60 words** | ✅ **54** |
| **F Who you spoke to** | Structured | 🔴 **ZERO CONVERSATIONS — critical** |
| **G What you got wrong** | **50 words** | 🔴 **Blocked on F** |
| **H Workflow today** | Diagram | 🟡 Drafted below, needs drawing |
| I Call flow | **15 words × 5** | ✅ Drafted |
| J Components | Tick + **60 words** | ✅ 8 ticked, **59** |
| K Guardrails | **20 words × 6** | ✅ Mapped to prescribed rows |
| L Architecture | Diagram | 🟡 Have the content, needs drawing |
| M Success metrics | **Max 3 KPIs** | ✅ All three tie to D |
| N Risks | **25 words × 3** | ✅ Drafted |
| O Working by 14 Oct | **60 words** | ✅ **53** |
| P Team | Structured | ⛔ Team details |
| Q Proof of build | **Two links** | ⛔ Deployed URL + 60s video |

---

# 01 · The Opportunity

## A — Submission details ⛔ pass/fail

| Field | Answer |
|---|---|
| Team name | **NEEDED** |
| Contact email | **NEEDED** |
| Track | **2** |
| Based in | **NEEDED** |
| Use case (1–8) | **8** — Rights Checks & Dispute Prevention |
| Stage | **NEEDED** (pre-seed / idea) |
| Languages covered | **English, Arabic (Gulf), Malayalam** |
| Prior ElevenLabs use | **NEEDED** (Y/N) |
| Team size / based in | **NEEDED** |
| Website or repo | **NEEDED** — the T1.9 deployment |

## B — The idea in one line · 25 max · **23 words** ✅

> An agent that checks rent increases against Dubai's rules for tenants, so that
> they learn their position and act before the deadline passes.

## C — What breaks today · 120 max · **117 words** ✅

> A Dubai tenant receives a rent increase by WhatsApp or a landlord's letter.
> Whether it is lawful is fixed by Decree 43 of 2013 and the rental index — a
> table lookup and arithmetic. The tenant cannot perform it. The published
> calculator asks for a comparable market value, which is the one thing they do
> not know; it cannot ask a follow-up question, and it exists only in English and
> Arabic. So they either pay, or they file at the Rental Dispute Centre: 3.5% of
> annual rent, AED 500 to 20,000, and 30 to 90 days waiting. The registrar then
> processes a question a table already settled. Meanwhile the 90-day window to
> contest the notice closes, uncounted.

## D — Today's baseline · numbers only · must match M

| What you measured | Value today | Where the number comes from |
|---|---|---|
| Cost to a tenant of getting an answer | **3.5% of annual rent · min AED 500 · max AED 20,000** | RDC filing fee schedule |
| Time from question to first-instance answer | **30–90 days** (up to 6 months contested) | RDC published practice |
| Residential tenancy contracts registered per year | **743,740** | **Our own query** of 9,798,685 contract-level Ejari records, DLD open data, 12 months to 2026-02-26 |
| ...of which are single-unit homes a resident rents | **567,652** | The same query after T2.1 scope rules: excludes labour camps, staff accommodation, and whole-block contracts |
| Phone channels answering this in Malayalam | **0** | DLD/RERA publish in English and Arabic only |
| Services that track a tenant's 90-day window | **0** | None exists |

> ✅ **The contract figure is now ours, not a secondary source** — computed
> 2026-09-09 from the DLD contract-level dataset (SHA256-verified), rolling
> twelve months. 743,740 independently corroborates the 742,000 published for
> 2023, which is the best kind of cross-check. Satisfies decision D-012.
>
> **The second row is the one that matters, and building T2.1 is what produced
> it.** "Residential" in DLD's schema includes 124,399 labour-camp and
> staff-accommodation contracts and 146,489 whole-block agreements covering more
> than one property. Those are real registrations and belong in the headline
> figure; none of them is a household ringing about a rent increase. **567,652
> is the population this product actually serves** — and knowing the difference
> is the difference between quoting a market average and quoting a labour camp's
> rent. See D-060.

## E — Who buys this · 60 max · **54 words** ✅

> Dubai Land Department, Rental Dispute Centre. The Senior Director for rental
> regulation and disputes signs. It comes from the customer-happiness and
> case-management operating budget, not innovation funding — the line that already
> pays for call-handling and registrar time. Earlier revenue comes from property
> managers verifying a notice before issuing it, from their compliance budget.

---

# 02 · The Evidence 🔴

## F — Who you spoke to · **CRITICAL GAP**

> **We have conducted zero primary research.** This box is verifiable, sits inside
> the 25% problem-fit criterion, and the template warns that desk research alone
> scores in the bottom band.

| Name and role | Organisation type | Date | The one thing they said that changed your idea |
|---|---|---|---|
| **NEEDED** | | | |
| **NEEDED** | | | |
| **NEEDED** | | | |

**Target: three conversations minimum, by 18 September.** Reachable channels, in
order of likelihood:

1. **Ignyte mentor directory** — 550+ mentors, filtered for real estate, property
   management, legal, regtech. **Same outreach as the T0.5 legal reviewer, so one
   effort serves both boxes**
2. **Dubai property managers** via LinkedIn — they issue the notices, and a dispute
   costs them
3. **Lawyers who file at the RDC** — they see the malformed cases directly
4. **Ejari typing-centre staff** — they watch tenants fail at this daily

## G — What you got wrong · 50 max · 🔴 **blocked on F**

> Cannot be written honestly until the conversations happen. **Do not fabricate
> this** — it is the box that catches teams who skipped the research.

## H — The workflow today · diagram

**Draft content. Must be drawn into the template's swimlanes.**

| Lane | 1 · Notice | 2 · Confusion | 3 · Search | 4 · Give up or file | 5 · Wait | 6 · Ruling |
|---|---|---|---|---|---|---|
| **Customer** | Receives increase by WhatsApp | Asks friends, agent, Google | Tries the DLD calculator, **needs a comparable value they do not have** | Pays, or files at RDC | **Chases for updates** | Receives ruling |
| **Front-line** | — | — | Call centre: English/Arabic only | RDC filing counter | — | — |
| **Back office** | — | — | — | Case registered | Mediation, then First Instance | Registrar rules |
| **Systems** | Ejari | — | Dubai REST / rental index | RDC portal | RDC case system | RDC |
| **Elapsed** | Day 0 | Days 1–7 | Days 7–14 | Day 14 | **30–90 days** | Day 45–104 |

**Checklist the template requires:**
- ☑ Every handoff — tenant → call centre → RDC counter → registrar
- ☑ Where it waits — 30–90 days at First Instance
- ☑ Where the customer chases — stage 5, repeatedly
- ☑ Systems by name — Ejari, Dubai REST, rental index, RDC portal
- ☑ **The step that fails most — stage 3.** The calculator needs a comparable
  market value, which is the fact the tenant lacks. This is the whole thesis
- ☑ Total elapsed — **45 to 104 days**, against a 90-day contest window that is
  running in parallel and uncounted

---

# 03 · The Agent

## I — The call flow · 15 words per step

| Step | What happens |
|---|---|
| **1** | Agent states it is AI, gives published-rule information not legal advice, call recorded. |
| **2** | Discovers the facts the rule needs across four questions; reads all seven back once. |
| **3** | Signed rules engine computes; agent states the result, then cites the governing clause. |
| **4** | Evidence pack and factual response sent to the caller's phone during the call. |
| **5** | Deadline reminder armed on explicit opt-in. Interpretive or distress questions transfer **(H)**. |

## J — ElevenLabs components · tick + 60 words

☑ Agents Platform ☑ Agent Workflows ☐ Sub-agents ☑ Eleven v3 TTS
☐ Voice Design ☑ Scribe v2 STT ☐ Knowledge base + RAG ☑ Server / client tools
☐ MCP servers ☑ Telephony (Twilio / SIP) ☐ Batch calling ☑ Agent Testing
☑ Post-call webhooks ☐ WhatsApp ☐ Web / mobile SDKs ☐ Bring-your-own LLM

**Why these two — 60 words:**

> **Agent Workflows** is the guardrail, not a convenience: node-scoped tools mean
> triage physically cannot reach the evidence generator. **Server tools** are the
> seam keeping the model out of computation — verdicts come from a signed rules
> engine, never the LLM. We skip RAG: each rule carries its own verbatim clause,
> so retrieval would add uncertainty to a deterministic citation.

## K — Guardrails · 20 words per row · **prescribed rows**

| Requirement | How your design enforces it |
|---|---|
| **Opening disclosure** | Fixed eight-second script, first turn, every call. Logged with the recording. Agent cannot proceed without completing it. |
| **Consent to be called** | Reminders require an opt-in token recorded on the call. No token, no scheduled contact. No bulk-calling code exists. |
| **Verification without secrets** | Pack goes to the calling number, which the caller demonstrably controls. We never request passwords, PINs or ID numbers. |
| **Human approval point** | No code path submits to any authority. The resident reviews the pack and acts. Registrars decide. |
| **Opt-out path** | STOP writes an irreversible suppression record. Re-granting is refused in code, not by policy. |
| **Escalation trigger** | Per-turn classifier on interpretation-seeking and distress language transfers immediately from any node, mid-turn. |

---

# 04 · The Architecture

## L — Technical architecture · diagram

**Draft content for the template's three zones. Filled dot ● = personal data
crosses a boundary.**

| Zone | Contents |
|---|---|
| **Caller and channel** | Inbound phone (Twilio) · SMS/WhatsApp out · public web checker |
| **ElevenLabs platform** | Agents Platform · Agent Workflows (triage → diagnose → compute → explain → dispatch) · Scribe v2 STT · Eleven v3 TTS · server tools · Agent Testing · post-call webhooks |
| **Institution systems** | **Our** rules registry, DuckDB comparables, evidence generator, case store, officer dashboard · **DLD open data (read-only)** · *authority submission adapter — declared unimplemented* |

**Labelled arrows:**
`caller → ElevenLabs` speech ● · `ElevenLabs → rules engine` slot values ● ·
`rules engine → ElevenLabs` verdict + citation · `generator → Twilio` pack link ● ·
`ElevenLabs → audit store` transcript ● · `DLD open data → DuckDB` bulk contracts
(no personal data) · `case store ⇢ authority` **unimplemented, marked absent**

**Checklist:**
- ☑ Every ticked box-J component appears
- ☑ Direction labelled on every arrow
- ☑ Personal-data boundaries marked ● (four crossings)
- ☑ Human approval gate — resident reviews the pack; no automated submission
- ☑ **Dependency down:** thin or unavailable comparables return *human review
  required* and no figure is spoken; SMS failure falls back to reading key points
  aloud; unsigned rule corpus refuses to boot

---

# 05 · The Case

## M — Success metrics · **max 3 KPIs** · baselines from D

| KPI | Baseline (from D) | Target | How it is measured |
|---|---|---|---|
| Time to answer | **30–90 days** | **Under 3 minutes** | Call start to verdict spoken, from post-call webhooks |
| Cost to the tenant | **3.5% of annual rent, AED 500–20,000** | **AED 0** | Free at point of use; no filing required to learn the position |
| Deadline awareness | **0 services track it** | **90%+ of eligible callers opt in** | Opt-ins recorded per call where a window is still open |

## N — Risks · 25 words per row

| Risk | How you handle it |
|---|---|
| **1** · The response we generate reads as legal drafting, making us an unlicensed legal service | Generator takes only structured records and renders fixed templates. No language model in that path. Advocacy is not producible. |
| **2** · Our comparable is derived from open contract data, not the official RERA index figure | Source named aloud and printed on every pack. Verdict logic is identical when an official feed replaces it. |
| **3** · Rule encodings are not yet reviewed by a qualified lawyer | Unsigned rules refuse to load; provisional status is disclosed aloud every call. Encodings published beside source clauses for verification. |

## O — What will be working by 14 October · 60 max · **53 words** ✅

> End to end and live: inbound call in English, Arabic and Malayalam; four-turn
> diagnosis; two signed rules computing against 9.8 million registered contracts;
> spoken citation; evidence pack delivered by SMS mid-call; deadline opt-in; test
> suites with pass rates. Mock: the officer dashboard queue. Absent by design and
> declared: submission to any government system.

## P — Team ⛔

| Name | Role on this build | Shipped previously (link) |
|---|---|---|
| **NEEDED** | | |

## Q — Proof of build ⛔ · two links, both required

1. **Deployed link** — the T1.9 public checker. Target live before 23 September
2. **60-second video** — a team member walking through the Box L diagram.
   **New deliverable.** Record after L is drawn; one take, one person, screen plus
   voice
