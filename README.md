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

🚧 **Phase 0 complete. Phase 1 (walking skeleton) in progress — T1.1–T1.8 done.**

The engine is real and reachable: two signed rules, a deterministic evaluator, a
hash-chained audit log, and a live `POST /evaluate` · `GET /healthz`, under 252
backend and 50 frontend tests, with a working web checker the whole product
serves from a single process. A verdict takes ~3 ms against a 150 ms budget, and
the public routes are rate limited. Next is deployment (T1.9). This README is expanded
with real measurements at T2.11.

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
readability and snapshot age land there when the market data is wired at T2.1.

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
