# Bayyina · بيّنة

**Bayyina converts published tenancy rules into a safe, conversational workflow
that determines what can be determined, produces the evidence a person needs to
act, and stops whenever the facts require human judgement.**

A Dubai resident calls in English, Arabic or Malayalam and describes a rent
increase. The agent works out which facts the rule actually needs, computes the
result on a signed deterministic rules engine, cites the governing clause aloud,
and sends a complete evidence pack to their phone **before the call ends**.

> **Nothing in the core product requires anyone's permission.** Open data,
> caller-stated facts, our own rules engine, our own evidence generator. Every
> government integration is an adapter that can be plugged in later — never a
> dependency the product waits on.

*Built for the Ignyte × ElevenLabs Future of Voice AI Challenge, Track 2.*

---

## Status

🚧 **Phase 0 complete. Phase 1 (walking skeleton) done through T1.8. Phase 2
in progress — T2.1, T2.2 and T2.3 complete.**

The engine is real and reachable: two signed rules, a deterministic evaluator, a
hash-chained audit log, and a live `POST /evaluate` · `GET /healthz`, under **331
backend and 70 frontend tests**, with a working web checker the whole product
serves from a single process. A verdict takes **5.9 ms at p95** against a 150 ms budget, and
the public routes are rate limited.

**Real market data is in, and the product answers from it.** 9,798,685
registered tenancy contracts ingested to 5,302,396 comparable records across 184
areas, aggregated into 1,324 cells of which 841 hold enough contracts to quote.
A resident no longer types their own market average: `POST /evaluate` accepts
the area, kind and bedroom count and derives the figure, so the answer stops
being conditional. **A lookup costs 7 microseconds at p95** against a 20 ms
budget, because the table is read once at boot and never touched again. Next is
deployment (T1.9). This README is expanded with real measurements at T2.11.

---

## Tech stack

Two independent toolchains, one deployment. `frontend/` builds to static assets
that `backend/` serves in production, so the split is a development concern and
the whole product still ships as **a single container**.

### Backend — `backend/`

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | The ETL and the rules engine want the same language |
| API | **FastAPI** | Typed request/response models become the agent's tool contracts for free |
| Validation | **Pydantic v2** | Rule validation *is* schema validation. A malformed rule fails at load, not at runtime |
| Rule storage | **YAML in git** | Version control **is** the version history; a non-programmer can read the diff |
| Market data | **DuckDB** | 9.8M contract rows, analytical queries, single file, zero infrastructure |
| Case store | **SQLite** (WAL) | Cases, deadlines, consent, audit. Zero setup, and correct at this scale |
| Documents | **Jinja2 → WeasyPrint** | Templates, not generation. **The constraint is the mechanism** (G10) |
| Tests / lint | **pytest · ruff** | — |

### The design system

```bash
cd frontend && npm run dev      # then open /specimen.html
```

`specimen.html` is a second Vite entry built from the product's own
`src/index.css`, so it cannot drift from what ships. Three 360 px panes — the
width this is designed at — the outcome states, the type scale, and swatches
whose contrast ratios are computed live rather than typed.

**Every colour pair is asserted against WCAG AA on every test run.** Two were
failing when the palette was first measured: a token at 2.46:1 that nothing
used, and — worse — the rent input's border at **1.26:1**, a field a person has
to find and type into. Boundaries now come in two weights: `rule` for decorative
hairlines, `edge` at 3.6:1 for anything a person must be able to see.

Noto covers all three scripts with one design, **bundled at 175 KB rather than
fetched** — the CSP forbids a third-party font request, and the PDF pipeline
needs the same faces on disk.

The Arabic pane is genuinely `dir="rtl"`. It is *not* a translated page: Arabic
and Malayalam are pending a native speaker (D-065), so those panes carry
typographic text that says so.

### Frontend — `frontend/`

| Layer | Choice | Why |
|---|---|---|
| Build | **Vite** | Builds to static files the backend serves. Dev server proxies `/api`, so **no CORS to maintain** |
| UI | **React 18 + TypeScript** | A typed API client catches contract drift at compile time rather than at demo time |
| Styling | **Tailwind CSS v4** | Design tokens in one place; logical properties give RTL mirroring rather than a font swap |
| i18n | **i18next** | Three languages, with untranslated keys falling back to readable English |
| Tests | **Vitest + Testing Library** | — |

### Voice and infrastructure

**ElevenLabs Agents** (Workflows, Scribe v2 STT, Eleven v3 TTS) · **Twilio**
(inbound voice, SMS/WhatsApp out) · **Docker**, one container · Railway, Render
or Fly.io.

**Deliberately not used:** UAE Pass (a permission we do not have), a hosted
database (DuckDB + SQLite are sufficient and portable), an LLM anywhere in the
document path (G10), RAG (each rule file carries its own verbatim clause).

---

## Repository layout

```
IgNyte/
├── backend/          Python — rules registry, API, market data
│   ├── src/bayyina/  registry · rules_logic · market · evidence · api
│   ├── rules/        THE CORPUS — signed, versioned YAML
│   ├── scripts/      sign_rule · verify_corpus · explore
│   ├── tests/        mirrors src/
│   └── data/         parquet + duckdb (gitignored)
├── frontend/         Vite + React + TypeScript
│   └── src/          api · i18n · components
├── agent/            ElevenLabs config and call scripts (neither FE nor BE)
├── docs/             DESIGN · ARCHITECTURE · GLOSSARY · DECISIONS · CANVAS
└── plan.md
```

### Running both

```bash
# terminal 1
cd backend && pip install -e ".[dev]" && uvicorn bayyina.api.app:app --reload

# terminal 2
cd frontend && npm install && npm run dev      # proxies /api to :8000
```

---

## The governing principle

**Determinism at the core. Language only at the edge.**

The LLM diagnoses, slot-fills and speaks. **It never computes, decides, or
interprets.** A signed, versioned rules registry computes every verdict and returns
a citation. If the engine returns no citation, the agent is *structurally* incapable
of answering — it is not restrained by a prompt, it has nothing to say.

---

## Performance budgets — stated commitments

These are budgets we hold ourselves to, measured and reported, not aspirations.

| Budget | Target | Rationale |
|---|---|---|
| **Our webhook, end to end** | **< 150 ms p95** | We own one hop of a < 1.5 s first-audio budget; STT, LLM and TTS consume the rest |
| First audio to the caller | < 1.5 s p95 | Voice quality and latency is 20% of Stage 2 scoring |
| Rule evaluation | < 5 ms | Pure functions, corpus held in memory from boot |
| Comparable lookup | < 20 ms | Pre-aggregated and indexed. **Never a `GROUP BY` over 9.8M rows at call time** |
| Evidence pack render | < 2 s | Runs after the verdict is spoken, so it is off the critical path |
| Cost per completed call | < $0.50 all-in | Measured, not assumed |
| Hosting | < $20 / month | Single container |

Every API response carries an `x-response-ms` header. We measure from the first
deployment, not retrospectively.

---

## Guardrails

Ten mechanisms, each enforced by a schema contract, a load-time check, a tool
scope, or the deliberate absence of a code path. **None is a prompt instruction.**

| # | Guardrail | Enforced by |
|---|---|---|
| G1 | Citation-or-silence | `EvaluationRecord.citation` is non-nullable, and blank fields inside it are rejected. A verdict with no clause is not a shape the system can build |
| G2 | Interpretive tripwire | Per-turn classifier; fires transfer from any node |
| G3 | Confirmed data only | Confirmation token issued only after spoken readback |
| G4 | Never submits to an authority | Mode C has **no concrete implementation**. No agent-reachable case status is terminal |
| G5 | Insufficient data over false precision | Below 10 comparable contracts **the rule is never run**, and the record type refuses to hold a verdict, a figure or a confidence number |
| G6 | Distress detection | Immediate warm transfer, logged |
| G7 | Unsigned-rule refusal | **The service fails to boot** on an unsigned, tampered, malformed or empty corpus. The evaluator refuses to hold one too |
| G8 | Consent and opt-out | Explicit opt-in; opt-out writes an irreversible suppression record |
| G9 | Auditable lineage | Hash-chained append-only log, written under a lock; `verify_chain()` names the first edited entry. Every input must carry a recorded source |
| G10 | States, never argues | The evidence generator has **no LLM in its call path** |

### The tamper demo

G7 is reproducible in three commands. Change one digit in a signed rule and the
service refuses to start:

```bash
cd backend
sed -i 's/max_increase: 0.05/max_increase: 0.99/' \
  rules/rent_increase.dubai.decree_43_2013.v1.yaml
python scripts/verify_corpus.py rules/     # exits non-zero
uvicorn bayyina.api.app:app                # TamperedRuleError - process exits
```

An AI system that will not run on unreviewed logic.

---

## The API

Every endpoint is documented at `/docs`, with a request example you can copy. A
test asserts each one carries a summary, a description and a working example, and
another asserts the examples name inputs the signed rules actually declare — so
the docs cannot drift from what the service accepts.

| Endpoint | What it is for |
|---|---|
| `POST /evaluate` | Run a rule and get the evaluation record, with the clause it came from. |
| `POST /evidence-pack` | The same evaluation, rendered as the document a resident takes to a hearing. |
| `GET /evidence-pack/languages` | Which languages a pack can be produced in. Derived from the templates on disk. |
| `GET /provenance` | Every rule in the corpus, with its approval state. |
| `GET /provenance/{rule_id}` | One rule: the clause verbatim, our encoding of it, and the signature. |
| `GET /comparables` | What places like this rent for, or why we will not say. |
| `GET /areas` | Every area a comparable can be looked up for. |
| `GET /healthz` | Corpus signature state, rule count, and whether market data is loaded. |

### Checking our encoding against the decree

`GET /provenance/{rule_id}` is the page a lawyer opens. It puts the published
clause beside our encoding of it, **generated from the same band table the
evaluator reads** — five bands in Decree 43, five steps on the page — so a
summary cannot drift from the logic that runs.

```bash
curl -s localhost:8000/provenance/rent_increase.dubai.decree_43_2013 | jq '.encoded'
```

The signature on that page is **recomputed on every request**, never echoed from
the file: a tampered rule carries a tampered signature block quite happily. The
review notes are published rather than hidden, because they record where the
decree is ambiguous and we had to choose.

### The document a resident takes away

```bash
curl -s -X POST localhost:8000/evidence-pack   -H 'Content-Type: application/json'   -H 'Idempotency-Key: call-1-pack-1'   -d '{"rule_id":"rent_increase.dubai.decree_43_2013",
       "inputs":{"current_annual_rent":"80000","proposed_annual_rent":"96000",
                 "market_average_rent":"87000"},
       "input_sources":{"current_annual_rent":"caller_stated",
                        "proposed_annual_rent":"caller_stated",
                        "market_average_rent":"user_supplied"},
       "market":{"snapshot_id":"user_supplied"},
       "caller_ref":"BYN-4821","language":"en"}'
```

It takes **inputs, never a record.** A verdict posted over HTTP would arrive
looking exactly like one we computed, carrying our citation and our name, so the
endpoint recomputes instead. There is no request shape that lets a caller choose
what the document says.

Send `Idempotency-Key` and a retry replays the first document rather than
producing a second — the stored bytes, not a fresh render that happens to match.
The same key with a *different* body is a **409**, because without that check a
client reusing a key by mistake receives somebody else's document.

A `HUMAN_REVIEW_REQUIRED` outcome still produces a pack. It names which facts
were missing and which rule would have applied, and it is the one a person takes
to the Rental Dispute Centre when we could not answer.

An untranslated language is **refused, not silently Englished**: an English pack
for a Malayalam reader is a failed delivery, and a fallback is how that happens
without anyone noticing.

---

## Quickstart

```bash
cd backend
cp .env.example .env          # fill in; never commit .env
pip install -e ".[dev]"
python scripts/verify_corpus.py rules/
pytest
uvicorn bayyina.api.app:app --reload
```

```bash
cd frontend
npm install
npm run dev                   # proxies /api to :8000
```

`GET /healthz` reports corpus signature state, every loaded rule with its
signature, and — in `not_yet_checked` — anything it did **not** verify. Database
readability and snapshot age land there at T2.3, when a request can read the
comparables database and a stale snapshot has to stop being quoted.

**A green health check that lies is worse than none**, so unverified things are
named rather than omitted.

---

## Deployment

One container. The frontend is built in a Node stage and copied into the Python
runtime as static files, so a single process serves the interface and the API
from one origin — no CORS, and one thing to deploy.

```bash
docker build -t bayyina .
docker run -p 8000:8000 bayyina        # http://localhost:8000
```

`BAYYINA_ENV` is deliberately **not** baked into the image. Setting it to
`production` requires an https `BAYYINA_BASE_URL`, and the platform config sets
the two together because they are only meaningful together.

### Hosting

`fly.toml` and `render.yaml` are both provided; use one. **Fly is recommended**,
for one reason that matters more than it sounds: its machine can be kept warm.

> **A free tier that sleeps is the wrong trade here.** After fifteen idle minutes
> Render's free plan spins down, and the next visitor waits roughly fifty seconds
> for a cold start. That visitor may be the judge opening the Box Q link, and the
> product's entire claim is that it answers quickly.

```bash
fly launch --no-deploy
fly secrets set BAYYINA_BASE_URL=https://<your-app>.fly.dev
fly deploy
```

### TLS

**Terminated at the platform edge, never in this process.** Uvicorn runs with
`--proxy-headers --forwarded-allow-ips '*'` so the original scheme and client
address arrive intact. Without those flags the app would believe every request
is plain HTTP from the proxy, which suppresses HSTS and collapses the rate
limiter onto a single apparent client.

`Settings` refuses to start in production with a non-https base URL. That URL
becomes the SMS link to a resident's evidence pack, so it is checked rather than
remembered.

### What the audit log does *not* do yet

The log is written to the container filesystem, which is **ephemeral: a redeploy
discards it**. G9 guarantees that every evaluation is recorded and that the chain
is verifiable — not that a demo host retains it. Both platform configs carry the
volume setup for a pilot, with the one caveat to check first: the container runs
as uid 10001, and a fresh volume is owned by root.

---

## Documentation

| Document | Contents |
|---|---|
| [docs/DESIGN.md](docs/DESIGN.md) | What we are building and why — problem, product, scope, buyers, metrics |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How it is built — adapter boundary, rules registry, guardrail mechanisms, call flow |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Terminology and content style, three languages. Gates all user-visible copy |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decision log — one line per material choice, with the reason |
| [docs/CANVAS.md](docs/CANVAS.md) | Stage 1 submission working draft |
| [plan.md](plan.md) | Implementation plan — 30 tasks, phased, with checkable Definitions of Done |
| [agent/scripts/en/call-script.md](agent/scripts/en/call-script.md) | The complete call script, with timings |

---

## Data

Market comparables derive from
[`dld_rent_contracts-open`](https://www.dubaipulse.gov.ae/data/dld-registration/dld_rent_contracts-open)
— registered tenancy contracts published as open data by Dubai Land Department.

### Checking a release before you build from it

```bash
cd backend
python scripts/inspect_release.py ~/Downloads/rent_contracts.csv
```

DLD publishes the same registry through more than one channel and **they do not
agree**. The Dubai Pulse bulk file uses `annual_amount` and `no_of_prop`; the
portal on [dubailand.gov.ae](https://dubailand.gov.ae/en/open-data/real-estate-data/)
returns `Annual Amount`, `No of Units`, `Number of Rooms` — and **no contract
identifier at all**, which is what de-duplicates multi-property contracts.

This reports what the file has, which columns need mapping, whether a paginated
export looks truncated, and the horizon — which is the only reason to download a
new one. Reads CSV or parquet. The ingest reads both too, and refuses a file with
a missing column by naming it rather than failing inside a query.

### Building the comparables database

```bash
cd backend
python scripts/ingest_market.py data/raw/rent_contracts_20260226.parquet
```

Roughly a minute, and it writes **two** databases:

| File | Size | What it is |
|---|---:|---|
| `data/market.duckdb` | 359 MB | The build database — every kept contract. Never shipped, never read at request time. Kept so a figure can be audited back to its rows and re-aggregated over a different window |
| `data/comparables.duckdb` | **1.3 MB** | What the service reads and the image carries. Comparables, areas and provenance only |

The split is not housekeeping. The request path reads 1,324 numbers; baking the
build database into a container would ship **5.3 million individual tenancy
records** in a public image to serve them. Both are gitignored — rebuild rather
than commit.

The release itself is 200 MB and also gitignored; nothing at request time touches
it, because a `GROUP BY` over 9.8M rows cannot meet the 150 ms budget.

The ingest separates three things that all remove rows, because conflating them
hides problems in both directions:

| | Rows | What it means |
|---|---:|---|
| **Excluded** | 4,296,572 | Not a single-unit residential tenancy. `property_usage_en = 'Residential'` includes labour camps at a median of AED 504,000, and 1.4M whole-block contracts whose amount covers every property on the contract |
| **Rejected** | 1,050 | In scope but unusable: impossible rent, dates that run backwards. **0.019%** of in-scope rows, against a 5% budget |
| **Trimmed** | 198,625 | Usable, but outside 1.5×IQR within their own area, type, bedroom count **and year** |
| **Stored** | 5,302,438 | Across 184 areas |

Above 5% rejection the ingest **raises** rather than logs, and an unrecognised
property type holding ≥1% of a release stops it too — a `Flat` → `Apartment`
rename would otherwise empty the table silently and look entirely normal.

The aggregation runs in the same command and materialises one row per
`(area, kind, bedrooms)` over a rolling twelve months. **The window ends at the
data, not at today**: the release runs to 2026-03-01, and a window anchored on
`now()` would slide off the end of it — six months after publication it would
cover 267,252 contracts instead of 555,607, shrinking quietly with no error.
Anchoring on `max(contract_start_date)` is no better: one contract in the file
starts in **2204**, and a window ending there holds exactly one row. The horizon
is a high quantile, and dates beyond it are rejected.

Below ten contracts **no median is computed at all** — not computed and withheld,
never computed. The count is kept, because "we found only four" is the honest
thing to say and needs the four.

Each cell also records **its own newest contract**, and that — not the release's
date — is what a lookup reports and what decides a refusal. Of 841 quotable
cells, 98 trail the release by more than a month and one is **418 days old inside
a release that is 193 days old**. Freshness then has two thresholds: quoted
plainly under 120 days, quoted with its date named up to 365, and not quoted at
all past that. Measured drift is 4.3% at six months against rule bands five
percentage points wide.

### Asking what a place rents for

```bash
curl 'http://localhost:8000/areas'          # the 184 we can resolve
curl 'http://localhost:8000/comparables?area=Al+Barsha+South+Third&kind=flat&bedrooms=2'
```

**Always 200.** Four answers, and three of them are refusals: `ok`,
`insufficient_data`, `stale`, `unknown_area`. `/areas` exists because
`unknown_area` without it is a dead end — the agent has told someone we do not
know where they live and has nothing to offer next. Each is a thing the agent has to
say out loud, and returning them as 4xx would teach every client to treat our
honesty as a fault. Note the spelling — DLD files that neighbourhood as *Al
Barshaa* South Third, and a resident has no way to know.

`POST /evaluate` takes the same three fields as `dwelling` and derives the figure
itself, so nobody has to know their own market average:

```json
{ "rule_id": "rent_increase.dubai.decree_43_2013",
  "inputs": { "current_annual_rent": "80000", "proposed_annual_rent": "96000" },
  "input_sources": { "current_annual_rent": "caller_stated",
                     "proposed_annual_rent": "caller_stated" },
  "dwelling": { "area": "Al Barsha First", "kind": "flat", "bedrooms": 2 } }
```

**Market data is optional.** Without it the notice rule and a caller-supplied
figure both still work; `/healthz` reports `market_data_loaded: false` and
degrades `status`, and `/comparables` answers 503 with the command that builds
it. A green health check that lies is worse than none.

Why it matters concretely: raw `Residential` in Jabal Ali Industrial has a median
of **AED 829,720**, because most of it is labour-camp blocks. After the scope
rules: **AED 32,000**. Someone asking whether their AED 32,000 rent may rise to
38,000 would otherwise have been told the market rate was three quarters of a
million — with a correct citation and signed arithmetic attached.

**Our computed comparable is not the official RERA index figure**, and we never
claim otherwise. Every evaluation records which source produced the market
average: `dld_open_rent_contracts_derived` today, `rera_official_index` on
institutional partnership. **The verdict logic is byte-identical either way** — the
pilot upgrade is a single input source the architecture already models.

---

## Licence

MIT — see [LICENSE](LICENSE), which also records what the licence does **not**
cover: the Dubai Land Department open dataset (not redistributed here), and the
legislation quoted in each rule file, which is unofficial English translation and
marked `provisional` pending qualified review.

---

## What this is not

Not legal advice. Not an official determination. Not a filing service — the
resident reviews and acts; authorities decide. Bayyina is not a government entity
and does not act for any authority.
