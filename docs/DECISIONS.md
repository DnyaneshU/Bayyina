# Decision Log

> One line per material decision, with the date and the reason. Settled questions
> stay settled — if a decision is revisited, add a new entry superseding the old
> one rather than editing history.

---

### D-001 · Track 2, Rights Checks & Dispute Prevention
**2026-09-07** — Chosen over Proactive Application Resolution and Life-Event
Orchestration because it is **the only one of the three where public data lets us
build something real.** The other two require access to visa, licence or permit
systems we do not have and would have to mock entirely.

### D-002 · Government integration is an adapter, never a dependency
**2026-09-07** — Mode A (prepare) is the product and requires nobody's permission.
Mode B (sandbox) proves the loop. Mode C (authority submission) is an interface
with **no concrete implementation**, declared absent rather than faked. Judges
penalise hypothetical "future government API access", and more importantly a
product that waits on a permission is not a product.

### D-003 · Dubai tenancy only; gratuity deferred
**2026-09-07** — Gratuity was insurance against the market-data risk. That risk
died when Dubai Pulse access was confirmed. **Insurance you do not need is just
scope.** Two rules, one domain, served deeply.

### D-004 · Rules run as `provisional`, and we say so aloud
**2026-09-07** — We hold no retained counsel. Three statuses: `unsigned` refuses
to load, `provisional` loads with spoken disclosure, `certified` requires a
qualified reviewer. **Stating this is worth more than implying a reviewer we do
not have.** Authority is replaced by public verifiability via the provenance page.

### D-005 · The evidence generator has no LLM in its call path
**2026-09-07** — Guardrail G10. A model writing persuasive prose on a tenant's
behalf is an unlicensed legal service. The only reliable prevention is removing
the model from that path: the generator accepts structured evaluation records and
renders Jinja templates. Verified by import inspection, not by trust.

### D-006 · Comparables are pre-aggregated at build time
**2026-09-09** — Our webhook owns <150 ms of a <1.5 s first-audio budget, and
voice latency is 20% of Stage 2 scoring. **A `GROUP BY` over 9.8M rows at call
time cannot meet that.** Medians are materialised into a small indexed table baked
into the image.

### D-007 · OTP only for a different number
**2026-09-09** — Superseded the original design placing OTP before the verdict. A
caller on the line demonstrably controls that number, and **receiving the SMS is
itself the verification.** OTP triggers only when the caller asks for delivery
elsewhere. Friction proportional to risk. *(Requires ARCHITECTURE.md §7 update.)*

### D-008 · The provisional disclosure attaches to the verdict, not the greeting
**2026-09-09** — It concerns the rule encoding, so it belongs where a rule is
stated. This discloses at the point of relevance **and** keeps the greeting inside
its 8-second budget. Disclosures D1–D3 stay in the greeting; D4 moves to the
verdict.

### D-009 · Four diagnosis turns, one batched readback
**2026-09-09** — Seven slots asked sequentially reads as a form and loses callers;
every turn is an abandonment opportunity. Slots are grouped naturally into four
turns, and G3 is satisfied by a single readback of all seven rather than seven
confirmations. Halves call length without weakening the guardrail.

### D-010 · Walking skeleton before depth
**2026-09-09** — Phase 1 deploys a thin end-to-end slice (one signed rule, manual
comparable, plain form) to a public URL before any thickening. Satisfies Box N
early — which scores **zero** without a link — and proves deploy, config and
boot-time guardrails before they can block anything.

### D-011 · No staging environment
**2026-09-09** — Two environments, `local` and `production`. At this size and
timeline, staging adds ceremony without adding safety. Revisit if a real
institutional pilot begins.

### D-012 · Box D cites our own ingest, not secondary sources
**2026-09-09** — Public sources disagree on annual Ejari registrations (742,000
for 2023; ~240,000 for H1 2025; ~600,000 on our rolling-twelve-month query).
Different periods and definitions. **The authoritative figure is the one our own
ingest produces in T2.1**, cited to the dataset and snapshot date. We do not
launder a secondary source into a baseline.

### D-013 · Translation is never machine-generated
**2026-09-09** — Arabic and Malayalam copy is legal-adjacent. A mistranslated
disclosure is a compliance failure, not a typo. All translation works from
`GLOSSARY.md` and requires a speaker, with a second speaker checking disclosures
D1–D7.

---

## Superseded

| Decision | Superseded by | Date |
|---|---|---|
| OTP verification before the verdict | D-007 | 2026-09-09 |
| Rent + notice + gratuity as launch domains | D-003 | 2026-09-07 |
| Two-state rule approval (`unsigned` / signed) | D-004 | 2026-09-07 |

### D-014 · Data obtained from a GitHub mirror, not Dubai Pulse directly
**2026-09-09** — `dubaipulse.gov.ae` timed out from two independent networks.
Obtained `rent_contracts_20260226.parquet` (208,816,045 bytes,
sha256 `72d347b2…d47c7715`) from the `rental-market-dynamics-dubai` release feed
instead. **Contract-level DLD data, 9,798,685 rows**, verified against the
published checksum. Retry Dubai Pulse before submission to cite the primary
source; the mirror is the working copy, not the citation.

### D-015 · Comparable key is (area, property_type, property_sub_type)
**2026-09-09** — The dataset has **no bedrooms column**; `ejari_property_sub_type_en`
carries it instead ("1bed room+Hall", "2 bed rooms+hall", "Studio"). Values need
normalising — inconsistent spacing and capitalisation, plus variants such as
"2 bed rooms+hall+Maids Room". Area names too: "Al Barsha South Third" and
"Al Barshaa South Third" both occur.

### D-016 · Median, not mean — now empirically forced
**2026-09-09** — Residential `annual_amount` has a mean of AED 471,004 against a
median of AED 67,000: **the mean is 7.0× the median**, driven by a maximum of AED
3.3 billion. Using the mean would have made every comparable roughly seven times
too high, telling tenants their rent was far below market. Median was chosen on
principle; it is now justified by measurement.

### D-017 · G5 thresholds are viable at the chosen values
**2026-09-09** — Measured over a 12-month window across 1,799
(area × type × sub-type) cells: **99.1% of contracts sit in cells with ≥30
comparables**, 0.6% in 10–29, 0.3% below 10. We can quote a figure for **99.7%**
of typical queries, so the honesty guardrail costs almost no coverage.

### D-018 · Frontend and backend split into separate top-level folders
**2026-09-09** — The root had gone flat (`src/`, `tests/`, `scripts/`, `web/`,
`agent/`, `docs/`, `data/`) and would only get worse. Now `backend/` (Python) and
`frontend/` (Vite) with independent toolchains, tests and CI jobs.

**The concern this had to resolve:** a separate frontend app usually means a
second deploy target, CORS configuration and a broken "single container under
$20/month" budget. **Vite avoids all three** — it builds to static files that
FastAPI serves in production, so the split is a development-time concern only.
In development the Vite dev server proxies `/api` to the backend, so there is no
CORS configuration to maintain in either environment.

### D-019 · React + TypeScript over vanilla HTML/JS
**2026-09-09** — Supersedes the earlier "no build step" choice. The earlier
reasoning was that three pages do not need a framework. What changed: three
languages with RTL mirroring, three surfaces (checker, provenance, officer
dashboard), and a **typed API client that catches contract drift at compile
time** rather than at demo time. The build step costs one command and buys
`npm run typecheck` as a CI gate. Assets are still static and still served by the
backend, so nothing about deployment changes.

### D-020 · Untranslated locales fall back to English, visibly
**2026-09-09** — `ar.json` and `ml.json` contain a `_TRANSLATION_STATUS` marker
and nothing else. i18next falls back to English for missing keys, so an
untranslated string renders as readable English rather than a raw key. **This
makes the gap obvious without breaking the interface**, and it prevents anyone
quietly filling the files with machine translation (see D-013).

### D-021 · RTL is enforced by a test, not by discipline
**2026-09-09** — The App test asserts that Arabic sets `dir="rtl"`. That is
necessary but not sufficient: a component using `ml-4` instead of `ms-4` passes
it and still fails to mirror. **RTL regressions are silent** — nothing throws,
the layout is simply wrong, and nobody notices until a demo.

`src/test/rtl-safety.test.ts` scans every source file for physical direction
utilities and CSS properties and names the replacement. Proven to fail on a real
violation. A single line may opt out with `rtl-safe-ignore` plus a reason.

### D-022 · A locale is either declared untranslated, or complete
**2026-09-09** — Nothing previously stopped someone translating 40% of a file,
removing the `_TRANSLATION_STATUS` marker, and shipping a half-Arabic interface
where the untranslated 60% silently renders in English. For a legal disclosure
that is worse than showing nothing.

`src/i18n/locales.test.ts` enforces the invariant: carry the marker, or cover
every key English defines. **No silent half-state.** The test also checks that
the marker itself names the source of truth and forbids machine translation, so
it stays a working instruction to a translator rather than decaying into a TODO.

### D-023 · `typecheck` runs `tsc -b`, matching the build exactly
**2026-09-09** — CI ran `tsc --noEmit`, which is **weaker** than the build. It
silently passed an `erasableSyntaxOnly` violation that `npm run build` rejected,
making the CI gate misleading. Both now run `tsc -b`.

Fixing that surfaced a second issue: the test files needed node types, which the
app project deliberately excludes. Rather than loosen the app config, tests moved
to their own `tsconfig.test.json`. **App code still cannot import `node:fs` —
verified by compile error** — while tests that scan the filesystem can.

### D-024 · Band tables are validated at load, not at evaluation
**2026-09-09** — The malformed-table check was raised inside `evaluate()`, which
meant a bad corpus **booted successfully and failed mid-call**. Band tables are
static data in a signed file, so every property is knowable at load time and now
lives in the schema alongside G7.

Validated: starts at 0.0, contiguous with no holes or overlaps, last band
unbounded, no unreachable band after an unbounded one, and every value a
proportion in [0, 1]. That last bound catches the likeliest encoding mistake —
writing `20` where `0.20` was meant, which would permit a **2000% increase with a
citation attached**. The runtime raise is kept as unreachable defence.

Adding this immediately exposed that a test fixture had never been a legal band
table (a single bounded band).

### D-025 · Property-based tests for the rule logic
**2026-09-09** — Example-based tests cover the boundaries we thought of. For a
rules engine a wrong answer *is* the product failure, and sign errors in numeric
code survive hand-written tests. `hypothesis` now checks six invariants across
generated inputs: the gap is always a proportion; a rent at or above market never
earns an increase; the ceiling never falls below the current rent; the verdict
matches the ceiling; a larger gap never permits a smaller increase; and a
proposal exactly at the ceiling is always permitted.

Proven: removing the `max(0.0, …)` clamp is caught immediately with the minimal
counterexample `gap = -0.001`. **That regression would have inverted the answer
for tenants already paying at or above market** — the people most likely to be
overcharged.

### D-026 · An empty corpus is refused, not tolerated
**2026-09-09** — `verify_corpus` and `load_rules` previously accepted a corpus
with no rules. Harmless while no rule existed, dangerous afterwards: an empty
`rules/` means a deleted file, a bad checkout, or a container build that did not
copy it — **and both the checker and the service would report healthy while able
to answer nothing.** An empty corpus is the ultimate unverified corpus, which is
exactly what G7 exists to prevent.

`load_rules(..., allow_empty=True)` is now an explicit opt-in used only until the
first rule is signed. CI passes the flag today; removing it is a step in T1.6.

### D-027 · Rule parameters never live in configuration
**2026-09-09** — `settings.py` and `.env.example` carried
`notice_required_days = 90`. That is a property of Law 26/2007 Article 14, not an
operational choice, and holding it in config created a real trap: **an operator
could change the law by editing an environment variable while the rule
signature still verified.** The rule file would have become decorative.

Removed, with a test asserting no rule parameter is ever reintroduced into
`Settings`. The distinction that stays: G5 thresholds *are* configuration,
because they are our choices about when we decline to answer — not statements
about what the law says.

### D-028 · The rule schema proves a rule is runnable before the service boots
**2026-09-09** — `logic` was a free string, `inputs` an untyped dict, and the
notice period had nowhere to live inside the signature. Each was a load-time
question deferred to call time. A rule naming `banded_percentages` would have
parsed, signed, loaded, passed CI, and failed at dispatch — with a caller on the
line.

`logic` is now an enum, `inputs` is a typed declaration the evaluator executes,
and each logic declares the parameter block it needs and rejects the others. Nine
structural faults now fail at load, listed in ARCHITECTURE §5.1. Two are worth
naming: a rule that **declares an input its logic never reads** is refused,
because we would ask a caller for it on the phone and discard it; and a rule
carrying the **wrong parameter block** is refused, because it reads as configured
and is never consulted.

### D-029 · Open questions are signed data, not YAML comments
**2026-09-09** — Signing rewrites the rule file, so a comment explaining a band
boundary would be unsigned commentary sitting on signed content, and would not
survive the next signature. Every interpretation, caveat and unresolved question
now lives in `review_notes`, which the hash covers and the provenance page
prints.

Twelve notes across the two rules. They record that the decree leaves 10–11%
undefined and which way we resolved it; that the 90 days apply "unless the
parties agree otherwise" and we cannot see the contract; that both verbatim texts
are unofficial English translations; and that neither URL is yet a permanent link
to the gazetted text. **A provisional rule with no open questions is a rule
nobody examined**, and a test asserts every rule carries some.

### D-030 · G5 is enforced by the record type, and the rule is never run
**2026-09-09** — "No number may be spoken below threshold" was a property of the
call script. A script is an instruction, and this project does not enforce
guardrails with instructions.

Below the evidence threshold the evaluator **does not call the rule at all**, and
`EvaluationRecord` refuses to validate if a `HUMAN_REVIEW_REQUIRED` record
carries a verdict, a computed figure, or a confidence number. There is no figure
held anywhere for a later step to decide to speak. `evidence` sits outside
`computed` so a thin-data outcome can still disclose *how* thin — "four
registered contracts" — while carrying nothing about the caller's own rent.

Proven: deleting the validator turns two tests red immediately.

### D-031 · `confidence` is a defined quantity, not an estimate
**2026-09-09** — The architecture sketch showed `confidence: 0.94`, which invited
us to invent a number. Inventing one is precisely the false precision G5 exists
to prevent.

`confidence` is now the proportion of the 30-contract full-confidence threshold
that the evidence reaches, capped at 1.0. It describes the depth of market data
behind a derived input. **It is not a probability that the verdict is correct**,
and it is `None` whenever no answer was produced. A rule reading no derived input
is 1.0, because nothing about the market can weaken it.

### D-032 · The audit log is hash-chained
**2026-09-09** — G9 claims "auditable lineage". Append-only was true of how we
intended to use the file, not of anything checkable. Each entry now carries the
digest of the entry before it, using the same canonical serialisation as rule
signing, so an edited or inserted entry is detectable and `verify_chain()` names
the first one that disagrees. `AuditLog` exposes only `append`, `entries`,
`verify_chain` and `path` — a test asserts that list, so an update method cannot
be added quietly.

Stated limitation: **a plain chain cannot detect truncation of the tail.** A
shortened log stays internally consistent. Detecting that needs an external
witness, which is a pilot concern and not something we claim today.

### D-033 · T1.6 was completed before T1.5
**2026-09-09** — T1.5's tests were specified to run against the production
corpus rather than a stub, which is right — a stub would let a rule file drift
from the tests that claim to check it. But T1.6 is what creates that corpus, and
T1.6 depends on nothing T1.5 produces. The plan's ordering was simply inverted.

Both are now complete. The `signed_rules` fixture loads `rules/` and verifies
every signature, so editing a rule without re-signing turns the evaluator tests
red, not just the corpus check.

### D-034 · G7 is enforced at both boundaries, not only at boot
**2026-09-09** — An audit of Phase 0–T1.6 found that `Evaluator` would produce a
verdict from a **tampered** rule. Constructed directly with a hand-assembled
rule whose band had been edited after signing, it returned `permitted` and a
maximum lawful rent of AED 159,200 — **with a citation attached.** The unsigned
case failed only by accident, on a minimum-length check for `rule_signature`.

Not reachable in production, where `load_rules` is the only source of rules. But
G7 is the demo's wow moment and the brief's hardest requirement, and it was true
of the loader rather than of the thing that produces verdicts. `Evaluator.__init__`
now refuses any rule that is unsigned or whose body no longer matches its
signature, using the loader's own exception types so there is one vocabulary for
"this rule cannot be trusted". One bad rule blocks the whole evaluator, the same
stance the loader takes.

Proven: disabling the check turns two tests red.

### D-035 · The audit log takes a lock, and says what it still cannot promise
**2026-09-09** — Appending read the chain tip and wrote the next entry as two
separate steps. Four threads writing 100 records produced 100 lines with
duplicate sequence numbers and a broken chain — reproduced, not theorised.
**FastAPI runs handlers in a threadpool, so T1.7 would have hit this.**

`append` now holds a lock across read-tip-and-write. The honest limit is stated
in the class docstring rather than left implied: a lock is per-process, so
several workers against one log file would still corrupt it. One container, one
writer. That constraint is now written down where someone scaling the service
will read it.

### D-036 · A malformed rule file fails by name, not by traceback
**2026-09-09** — G7 promises that a rejected corpus can be fixed from the message
alone. That was true for unsigned, tampered and empty — and false for malformed:
broken YAML, an empty file, or a schema violation escaped as a raw pyyaml or
pydantic traceback, past `verify_corpus.py`'s `except CorpusError`.

CI was never at risk — an uncaught exception still exits non-zero — but the
operator experience was a stack trace where the other three give a sentence.
`MalformedRuleError` now wraps both parse and validation failures and names the
file and the offending field:

```
CORPUS REJECTED
  bad.v1.yaml: does not match the rule schema:
    logic: Input should be 'banded_percentage' or 'notice_period'
```

### D-037 · Repository hygiene is part of the submission
**2026-09-09** — The audit found the Vite starter still in place: `react.svg`,
`vite.svg`, `hero.png` and a sheet of social icons that nothing imported, the Oxc
template favicon, `<title>frontend</title>`, and the untouched "React + TypeScript
+ Vite" README. Also `.hypothesis/` — 18 cache files — was never gitignored.

Removed, replaced, or ignored. A judge who opens the repository sees the project
rather than the scaffold it started from, and the frontend README now documents
the two conventions that are not conventions: RTL as layout, and the
marker-or-complete rule for locale files.

### D-038 · CLEAR_WITH_CONDITIONS means thin comparables, and the script says the count
**2026-09-09** — The call script and the engine had drifted into two different
meanings for the same state. §6b described an *unverified condition* ("it depends
on one thing I can't check"); the engine returns `CLEAR_WITH_CONDITIONS` when the
market figure rests on **10 to 29 comparable contracts**. The agent would have
qualified the verdict with the wrong caveat.

The script now matches the engine: it states the actual contract count from
`evidence.contract_count`, **before** the verdict rather than after — a caller
who hears the number first has already acted on it by the time the caveat
arrives. Vagueness is banned explicitly: "limited data" and "a few" are not the
count, and the count is the only thing that lets a caller judge how much weight
the answer carries.

### D-039 · The corpus is verified before an app object exists
**2026-09-09** — The obvious place for a boot-time check is a FastAPI startup
event. It is the wrong place: a startup event that raises still leaves a
constructed app behind, and what "the service refuses to boot" has to mean is
that no app was ever built.

`create_app()` calls `load_rules()` as its first statement. Unsigned, tampered,
malformed or empty and it raises before a single route is registered.

`bayyina.api.app:app` — the entry point the README documents — resolves through a
module-level `__getattr__` that builds the app on first access. Two things stay
true at once: `uvicorn bayyina.api.app:app` refuses to start on a bad corpus, and
*importing* the module has no side effect, so a broken corpus fails the one
process that asked for an app rather than every test collection that happened to
import `create_app`.

Verified end to end: one digit changed in a signed rule → `verify_corpus.py`
exits 1, and resolving the ASGI target raises `TamperedRuleError`.

### D-040 · Status codes carry whose problem it is
**2026-09-09** — Both "the caller sent a rent of zero" and "a signed band table
has no matching row" were bare `ValueError`. Over HTTP they are opposites. A 422
tells the caller to fix their request; if the real fault is a corpus defect, that
sends them into retrying a corrected request forever against something only we
can fix.

`RuleInputError` and `RuleLogicError` now split them, both still subclassing
`ValueError` so existing callers are unaffected. `RuleInputError` → 422,
`UnknownRuleError` → 404 naming what *is* loaded, `RuleLogicError` → **500**,
logged at error level and returning nothing actionable, because there is nothing
the caller can do.

`required_days <= 0` is a `RuleLogicError`, not an input error: it comes from the
signed rule file, never from the caller.

### D-041 · Thin data answers HTTP 200
**2026-09-09** — `HUMAN_REVIEW_REQUIRED` was tempting to return as a 4xx. It is
not a failure — the rule was applied honestly and the evidence did not support an
answer. Returning it as an error would teach every client, and every agent
workflow built on top, to treat the honest case as a fault to route around.

200, with `verdict: null`, `computed: {}`, `confidence: null`, the citation
intact, and `evidence.contract_count` so the agent can say *how* thin the data
was. The status code says the service worked. The body says what it could and
could not conclude.

### D-042 · Money never crosses the wire as a JSON float
**2026-09-09** — The `/evaluate` request model types input values as `str | int`.
A JSON float is refused with a 422 rather than silently converted.

Rent is currency, and the one place a binary-floating-point artefact is
unacceptable is the number someone is about to act on. A fractional amount is
sent as `"80000.50"`. Responses come back the same way — `max_lawful_rent` is the
string `"80000.00"`, not `80000.0` — so the value the caller reads is the value
the engine computed, digit for digit.

### D-043 · The health check names what it did not check
**2026-09-09** — README claimed `/healthz` reported "corpus signature state,
database readability and snapshot age". Two of those three were not checked and
would not be until T2.1, which is exactly the green-check-that-lies the same
paragraph warns against.

`/healthz` now returns `checks` — every check actually performed, with its result
— and `not_yet_checked`, listing what it did not look at. `status` is `ok` only
when every performed check passes. Adding a subsystem later cannot silently
inherit a green light: it has to move from one list to the other.

### D-044 · The access log had no handler, so it logged nothing
**2026-09-09** — T1.7 added timing lines to `observability.py` and a corpus line
to `create_app`. Running the real server showed uvicorn's own access log and
**not one line of ours**: a library logger with no handler inherits the root
logger, which defaults to WARNING, so every `logger.info` was dropped. `LOG_LEVEL`
was documented in `.env.example` and read by nothing.

The failure mode is the dangerous kind — uvicorn's output looks healthy, so the
absence is easy to miss for weeks. Caught by running the server rather than by
running the tests.

`configure_logging(settings.log_level)` now runs in `create_app`. The handler is
attached **only when the tree would otherwise be silent** — nothing of ours and
nothing on root — so plain uvicorn gets our lines without stealing logs from a
host application that configured its own. Propagation is left on, so an
embedder's handlers and pytest's `caplog` still see the records; a first attempt
set `propagate = False` and silently broke both.

### D-045 · Production refuses to run with a non-HTTPS base URL
**2026-09-09** — TLS is terminated at the platform edge, not in this process, and
that is the right place for it. But `bayyina_base_url` is what goes into the SMS
a resident receives: a link to their own evidence pack, holding the rent they
stated and the case built from it. Sent over `http` it is readable in transit and
the person receiving it has no way to tell.

`Settings` now refuses to construct when `BAYYINA_ENV=production` and the base URL
is not `https://`. Local development may still use http — requiring TLS on
localhost only teaches everyone to disable the check.

This wires two settings that were previously declared and read by nothing. What
it prevents is the app *minting* http links while sitting behind an https edge,
which looks correct in every log and is wrong in the only place that matters.

### D-046 · A missing corpus directory is a different failure from an empty one
**2026-09-09** — Both reported "no rules found in 'rules'". The fixes are not the
same: a missing directory is a wrong working directory or a container `COPY` that
did not happen — **the failure T1.9 is most likely to hit** — and an empty one is
a deleted file. `MissingCorpusError` now says which, and prints the *resolved*
absolute path, because a relative path in the message is useless precisely when
the working directory is the problem.

`allow_empty` forgives an empty corpus and never a missing one.

### D-047 · The public rate limit exists now, and states what it is not
**2026-09-09** — `PUBLIC_RATE_LIMIT_PER_MINUTE` was documented as a "web checker
abuse guard" from T1.1 and implemented by nothing. `/evaluate` is a public POST
that runs a rule and appends to the audit log, and T1.9 puts it on the open
internet, so the control had to exist before the URL did.

A fixed-window, per-client, in-process limiter. **`/healthz` is exempt**: hosting
platforms poll it every few seconds, and limiting it would make the platform
declare a healthy service dead.

Two limits are stated in the module rather than discovered later. It is
**per process**, so two workers means twice the effective limit; and it is a
**fixed window**, so a burst straddling a boundary can briefly exceed it. It is
an abuse guard, not a quota system. Redis would fix both and is not worth adding
to a service that fits in one container.

Client identity comes from `request.client.host`, which behind a proxy is the
proxy — which is why T1.9 runs uvicorn with `--proxy-headers`. Without that flag
every request appears to come from one address and the limit would apply to all
callers collectively.

### D-048 · Configuration and its template are checked against each other
**2026-09-09** — `Settings` uses `extra="ignore"`, which it must: the environment
of any real process contains hundreds of unrelated variables. The cost is that an
unmodelled variable is **silently dropped** — an operator who sets it and sees no
effect cannot tell whether it worked.

Two tests now hold `.env.example` and `Settings` together. Every modelled setting
must appear in the template, so a setting nobody can discover cannot exist. Every
documented variable must be either modelled or listed in `PHASE_3_ENV_VARS`, the
explicit set of things advertised ahead of their implementation.

Fields that are declared but not yet read now name the task that will read them —
`market_snapshot_max_age_days` (T2.1), `tool_timeout_seconds` (T2.10) — so
"declared and unused" is a recorded state rather than something to rediscover.

### D-049 · A conditional answer must name its condition
**2026-09-09** — T1.8 exposed a hole. The web checker's market average is typed
by the reader, not derived by us, and `/evaluate` demanded a `contract_count`
before it would answer a market-dependent rule. The tempting fix was to send a
plausible number. **That is fabricating evidence** — inventing depth for a figure
we did not gather, to make an answer look better supported than it is.

`MarketEvidence.contract_count` is now optional, and absent means *not derived by
us*. The outcome becomes `CLEAR_WITH_CONDITIONS` carrying
`market_average_not_derived`, and `confidence` is `None`, because we cannot state
a confidence in evidence we never gathered.

That required fixing something older. `CLEAR_WITH_CONDITIONS` had meant "thin
comparables" to the engine and "an unverified condition" to the call script
(D-038). Both readings are legitimate; the missing piece was that the state never
carried *which*. `EvaluationRecord.conditions` now holds a vocabulary of keys —
`market_average_not_derived`, `thin_comparable_data` — and the record refuses to
validate when a conditional answer names no condition, or when a clear one names
any. Keys rather than sentences, so each surface renders them in the reader's own
language through the glossary.

Proven: an unnamed condition fails validation; a fabricated `contract_count` in
the request turns a frontend test red.

### D-050 · The interface refuses to print figures the outcome forbids
**2026-09-09** — G5 is enforced by the record type: a `HUMAN_REVIEW_REQUIRED`
record cannot carry computed figures. The interface could still have rendered
them if something upstream regressed, so it does not read `computed` at all in
that state.

The frontend test deliberately feeds it a payload carrying figures the backend
could never produce, and asserts none reach the page. A first version of that
test passed against an empty `computed` and therefore proved nothing — it only
became load-bearing once the payload carried the numbers it must refuse. **The
interface is the last surface before a person reads a number.**

### D-051 · Phone-first is enforced, not remembered
**2026-09-09** — The audience checks a rent increase on a phone, often small and
old, often not in their first language. Layout cannot be verified in jsdom, so
`phone-safety.test.ts` scans the source for what reliably breaks small screens,
the same way `rtl-safety.test.ts` does for Arabic: the viewport declaration, the
44px tap-target floor, fixed pixel widths, and the 71-character rule signature,
which widens the page past the viewport on every phone unless it is explicitly
broken.

### D-052 · The glossary now gates copy instead of asking to be remembered
**2026-09-09** — `docs/GLOSSARY.md` opens with "Gates all user-visible copy."
It gated nothing. Comparing the shipped strings against it found two disclosures
already diverged: `D2` shipped as "Information from Dubai's published rental
rules…" against a glossary form written first person for speech, and `D6` shipped
"As stated by you" against a PDF form that says "the caller".

**Both divergences are correct.** A web page does not say "I", and §5 requires
second person for the person at the keyboard. The fault was the glossary
recording one form while forbidding paraphrase, so the right copy was formally in
breach of the document governing it. Surface variants are now recorded as exact
strings in a table of their own.

`frontend/src/i18n/glossary.test.ts` compares both directions — the shipped
string must match the glossary, and the glossary must still contain that string —
so editing either alone fails the build. It also enforces the banned vocabulary,
with an explicit allowlist for the two keys that contain a banned word because
they *negate* it, and asserts that human review is never worded as an error.

Proven: paraphrasing D4 turns two tests red.

### D-053 · Canvas word limits are checked, not counted by hand
**2026-09-09** — Six boxes carry hard word limits, and going over is a submission
failure. The counts were maintained by hand in a status table, and one had
already drifted — box J read 58 against an actual 59.

`test_docs_consistency.py` now counts the quoted text in each box, asserts it is
within the template's limit, and asserts the status table reports the real
number. The stakes are asymmetric: a box one word over is rejected, and nobody
recounts by hand on the day of a deadline.

### D-054 · One image, and the corpus is verified while building it
**2026-09-09** — The Dockerfile builds the interface in a Node stage and copies
it into the Python runtime as static files, so one process serves the page and
the API from one origin. That is what makes "no CORS to maintain" true rather
than aspirational.

`RUN python scripts/verify_corpus.py rules/` sits in the build. G7 now runs at
four points — signing, CI, image build, and boot — and the image build is the one
that means **an artifact carrying an unreviewed rule cannot exist**, rather than
existing and refusing to start. CI proves it by tampering with a rule and
asserting the build fails.

The container runs as uid 10001. A process that reads signed rules and appends to
an audit log has no reason to be able to modify its own code.

`BAYYINA_ENV` is deliberately absent from the image. Baking in `production` would
make a plain `docker run` crash, because production demands an https base URL
(D-045); the platform config sets the pair together, since they are only
meaningful together.

### D-055 · HSTS is sent only over TLS
**2026-09-09** — The obvious implementation sends the security headers on every
response. `Strict-Transport-Security` must not be: sent from a local dev server
over plain HTTP, a browser pins **localhost** to https, and every other project
on that machine using localhost breaks in a way that is genuinely painful to
undo.

It is emitted only when the request arrived over TLS, read from
`X-Forwarded-Proto` — which is another reason the container passes
`--proxy-headers`. No `preload`: submission to the preload list is effectively
irreversible and this host may move.

The CSP is strict — no `unsafe-inline`, no `unsafe-eval` — and that was
**verified against the built page** before being written, not assumed. The Vite
build emits external scripts and an external stylesheet with nothing inline. A
future build that inlines something will break loudly in development, which is
the right way round.

### D-056 · Line endings are normalised, and the digest survives them
**2026-09-09** — The project is developed on Windows. `.github/workflows/ci.yml`,
the `Dockerfile`, `fly.toml`, `render.yaml`, **and both signed rule files** were
CRLF. On a Linux runner a CRLF `run:` block fails with a syntax error naming a
token nobody wrote, and CI had never run — there is no git repository yet — so
this would have surfaced on the first push, during deployment week.

`.gitattributes` normalises to LF; 29 files converted.

The rule files raised a worse question: **would a line-ending change break every
signature at once?** It does not, because PyYAML normalises line breaks when
parsing, so the digest is computed over identical text either way. That was
checked rather than hoped, and a test now asserts it for every rule in the
corpus. A property this load-bearing should not rest on a library behaviour
nobody wrote down.

### D-057 · The first container run crash-looped, and the guardrail was right
**2026-09-09** — The `image` CI job failed at its smoke test: the container
exited before serving anything, with no visible output.

The cause was `BAYYINA_ENV=production` baked into the image. Production requires
an https `BAYYINA_BASE_URL` (D-045), the image cannot know the hostname, so
`Settings` raised at import and uvicorn exited instantly. **The guardrail did
exactly what it was built to do.** The image was wrong.

Two things made it hard to see, and both are fixed.

**A comment described the opposite of the code.** An earlier edit to remove the
line applied its explanatory comment — "BAYYINA_ENV is deliberately NOT set
here" — and silently failed to remove the assignment sitting four lines below it,
because the replacement was made without asserting that it matched. The file then
read as correct to anyone reviewing it, including the author.

**The diagnostics were collapsed.** `docker logs` ran inside a `::group::`, which
GitHub renders folded, so the traceback was present and invisible. Diagnostics
now print unfolded, and a separate step runs the image in the foreground before
the smoke test so a boot failure prints its own traceback.

`tests/test_deployment_config.py` now asserts what only fails at deploy time: the
image sets no environment name and no base URL, its path variables name real
`Settings` fields, the corpus is verified during the build, the container does
not run as root, uvicorn trusts the proxy headers, the build context excludes
secrets and data, and neither platform config uses a sleeping free tier.

Proven: restoring the offending line turns the test red.

### D-058 · Two silent failures the whole test suite missed
**2026-09-09** — Running the interface for the first time showed both at once:
"Request failed (404)" under the form, and a submit button that was invisible.

**`/evaluate` was not in the Vite dev proxy.** Only `/api` and `/healthz` were.
The page loaded, the health check resolved, and the one button that matters
404ed against the dev server. Neither suite noticed, because **each side was
correct on its own** — the backend served the route, the frontend called it, and
nothing tested the seam. A backend test now reads `vite.config.ts` and asserts
every route FastAPI serves is proxied.

**Every colour class emitted no CSS.** `bg-[--color-ink-900]` is Tailwind v3
syntax; under v4 it produces nothing at all — no error, no warning. The submit
button was white text on a white background, the language buttons were blank
rectangles, and the whole interface rendered unstyled. v4 generates utilities
from `@theme` variables instead (`--color-ink-900` → `bg-ink-900`), which is now
the only form allowed. 37 classes corrected.

The second is the more troubling one: **every test passed while the product was
visually broken.** jsdom asserts structure, not that a class produced a rule. The
new test builds the CSS and checks that every themed utility used in the markup
actually appears in the output — the only check that would have caught it.

Proven: both regressions turn a test red.

### D-059 · An untranslated language discloses itself
**2026-09-09** — The language switch offered three languages and delivered one.
Measured: Arabic differed from English in **1 of 57 strings**, Malayalam in
**zero**. Clicking മലയാളം changed nothing on screen. The mechanism was correct —
`changeLanguage`, `lang` and `dir` all fired — and the content simply did not
exist, which from a user's seat is indistinguishable from a dead button.

D-013 forbids machine-translating legal-adjacent copy, and that decision stands:
a mistranslated disclosure is a compliance failure, not a typo. So the gap is
real and stays until a speaker fills it. **What was wrong was the silence.**

This product's whole stance is disclosing what it has not verified — provisional
rules are announced aloud, an unchecked market average becomes a named condition.
An untranslated interface is the same kind of fact and now behaves the same way:
selecting a language we cannot render explains that English is what will appear,
and why it is missing rather than merely approximate.

`_TRANSLATION_STATUS` (D-022) is the single source of truth. `isTranslated()`
derives from it, and the switcher's mark and the disclosure both derive from
that — so finishing a translation removes the marker and the disclosure vanishes
with it. There is no second place to remember.

Rendered as `role="status"`, never `role="alert"`. A disclosed limitation shown
as a malfunction teaches people to distrust honesty — the same reasoning that
keeps `HUMAN_REVIEW_REQUIRED` off the danger colour.

Two further defects fixed alongside: the choice was **not persisted**, so every
reload silently reverted to English, and storage access was unguarded — a private
window makes `localStorage` throw rather than return null. Auto-detection from
`navigator.language` was deliberately *not* added: greeting an Arabic browser
with a mirrored English page it did not ask for is worse than asking. Detection
belongs with the translations, not before them.

Proven load-bearing: removing the disclosure, hardcoding `isTranslated`, and
dropping persistence each turn tests red.

### D-060 · Three things the plan's ingest rules got wrong
**2026-09-09** — T2.1 was written from measurements taken before the pipeline
existed. Building it against the real file corrected three of them, and one was
dangerous.

**`no_of_prop` was missing entirely, and it matters most.** `annual_amount` is
the total for every property on a contract, not the rent of one home. Measured on
2-bed flats: a one-property contract has a median of AED 66,000; a ten-property
contract, AED 596,904. **1,375,195 residential rows cover more than one
property.** Left in, they inflate every median *and* count one contract once per
property it covers. Nothing in the plan mentioned this.

**`contract_id` is not a key.** The plan said to reject duplicates. There are
8,178,976 distinct ids across 9,798,685 rows, and the natural key is
`(contract_id, line_number)` — the lines of a multi-property contract repeat the
same figures. Rejecting duplicate ids would have thrown away 1.62 million real
tenancies, blown the 5% budget on its own, and looked like a data-quality
problem rather than a modelling error.

**The area-name claim was inverted.** The plan said 'Al Barsha South Third' and
'Al Barshaa South Third' are the same neighbourhood under two codes. They are
not: the first does not exist in this release. Barsha's sub-areas are spelled
inconsistently *across* eight genuinely different neighbourhoods, each with its
own code, and merging them would have corrupted eight medians at once. The one
real duplicate is 'AL QUSAIS' (148,665 contracts) and 'Al Qusais' (11) —
verified by asserting against all 213 area names that the key merges exactly
that pair and nothing else.

The measured contamination was also worse than estimated: 'Room in labor Camp'
is 978,610 contracts at a median of AED 504,000, not the 455,009 recorded.

### D-061 · Exclusions, rejections and trims are counted separately
**2026-09-09** — All three remove rows, and conflating them hides problems in
both directions.

An **exclusion** is out of scope: a labour camp, a whole-block contract, a
penthouse with no bedroom count. Nothing is wrong with the row. A **rejection**
is an in-scope row that is unusable — an impossible rent, a contract ending
before it starts. A **trim** is a usable row sitting far enough from its peers to
move a median we intend to stand behind.

**The rejection rate is measured against in-scope rows, not the file.** 56% of
the release is out of scope, so measured against the file a rejection rate could
triple and still read as a rounding error — the number the DoD turns on would
stop meaning anything. Measured correctly: **1,050 of 5,502,113, or 0.019%**,
against a 5% budget.

Above the budget the ingest **raises** rather than logs. A comparable table
quietly built from a third of the data it should have looks entirely normal from
outside, and every verdict resting on it inherits the problem invisibly.

### D-062 · The outlier fence is drawn within a year, not across the corpus
**2026-09-09** — Rents drift. A 2-bed flat in Al Barsha First had a median of
AED 90,000 in 2017, 65,000 in 2021 and 88,000 in 2026. A fence drawn over the
whole history describes no year in it and would read an ordinary 2026 contract
as an outlier of 2021.

Trimming is per `(area, property type, bedrooms, year)`, and cells with fewer
than 8 contracts are left alone — a quartile over a handful of contracts
describes noise. Whether a thin cell may be quoted at all is T2.3's decision,
which is the honest place for it.

### D-063 · Scope is an allowlist, and an allowlist needs a tripwire
**2026-09-09** — What counts as a dwelling is a list of things people rent and
live in, not a list of things to exclude. A denylist admits whatever category DLD
adds next, and the categories it would admit are exactly the harmful ones.

An allowlist fails silently in the other direction: if DLD renames `Flat` to
`Apartment`, five million rows leave scope, the ingest reports a small clean
table, and nothing looks wrong until a caller is told there is no data for their
area. So an unrecognised property type holding ≥1% of the release stops the
ingest and asks for a decision.

Scope is the **intersection** of property type and sub-type, because neither is
sufficient alone: 'Room in labor Camp' appears 3,234 times under property type
'Flat', and 'Studio' appears 6,552 times under 'Labor Camps'.

### D-064 · Five scope tests passed while proving nothing
**2026-09-09** — Deleting each scope rule in turn should have turned a test red.
Two did not.

With `no_of_prop = 1` removed, the whole-block contract entered scope — and was
then removed by the **outlier fence**, because AED 596,904 sits far outside its
cell. The assertion "this contract is not in the table" held either way. The same
hid the sub-type rule.

A row that is wrong is usually wrong in several ways at once, so an assertion
about the *final* table cannot tell you which mechanism caught it. The scope
tests now assert `in_scope_rows`, which only scope can satisfy. Re-verified:
deleting any of the seven rules turns a named test red.

The fixture had the same flaw from the other side. Its baseline stepped rents by
AED 100, making the interquartile range so narrow that every other row read as an
outlier — a fixture that would have "proved" the fence worked by clipping
everything put in front of it.

### D-065 · The switcher offers only the languages the interface can render
**2026-09-10** — Supersedes the disclosure added in D-059, which explained a
broken control instead of removing it.

Arabic and Malayalam are **not being dropped**. They are the product: no phone
channel in Dubai answers a tenancy question in Malayalam, which is a headline
figure on the canvas and much of why this exists. They stay in `LANGUAGES`, in
the PDF template paths, in the voice scripts, and in the glossary's translation
plan.

What was wrong is shipping a *control* for them. A button that changes nothing on
screen is broken however carefully it is captioned, and a caption is not a
feature. So `AVAILABLE_LANGUAGES` is derived from `_TRANSLATION_STATUS`, the
switcher renders exactly those, and it disappears entirely at one language —
a control with one option is not a choice.

Because it is derived, **filling in a locale file and removing its marker is the
whole of the work**: the button appears on its own, with no component to edit and
no list to remember. `storedLanguage()` checks availability in the same
direction, so a translation withdrawn after review cannot pin a returning reader
to a locale we have stopped standing behind.

**Why we still do not simply translate it.** GLOSSARY §6 rule 3 is the concrete
blocker, not squeamishness: Decree 43/2013 and Law 26/2007 have **official
Arabic** published by Dubai's government, and our English is an unofficial
translation of that Arabic. Drafting Arabic here would be back-translating a
translation of the authoritative text. The correct Arabic already exists and must
be sourced.

RTL coverage moved down a layer rather than disappearing with the buttons.
`src/i18n/language.test.ts` exercises `applyLanguage` directly, so the D-021
guarantee stays checked while Arabic is pending — RTL regressions are silent, and
the day the button returns is the worst day to discover the layout stopped
mirroring.

### D-066 · A comparable and its provenance are written in one transaction
**2026-09-10** — The ingest wrote contracts, then areas, then rejections, then
the snapshot row. A crash anywhere in that sequence left **comparable figures
with no source, no digest and no date**.

A figure that cannot be traced to a file is not evidence, and this failure is
invisible: every query still returns rows, the medians still look reasonable, and
nothing reports a problem. The whole store is now one transaction, and the 200 MB
digest is computed before it opens rather than holding it.

Two invariants are asserted rather than assumed: no `contracts` row exists
without its `snapshots` row, and a failure mid-store leaves all four tables
empty. Proven by removing the transaction — the second turns red immediately.

The digest field was also only `min_length=64`, which accepts a truncated or
reformatted value. It is now `^sha256:[0-9a-f]{64}$`, because that field is the
whole of a snapshot's traceability.

### D-067 · Deferral markers are checked against the plan, not trusted
**2026-09-10** — `NOT YET CONSUMED - T2.1` markers outlived T2.1. Two of them —
on `market_snapshot_max_age_days` and on the `/healthz` deferral — read as
"arriving in the work we just finished", and both actually belong to T2.3.

A reader cannot tell a genuine deferral from a stale one, which is how a
deferral list stops being worth reading. Two tests now hold the line: a marker
must not name a task the plan has ticked, and it must name a task the plan
actually contains. `ARCHITECTURE.md` naming a database file the code never
writes was the same class of drift, caught the same way.

### D-068 · The seam between the checker and the API is tested from one side
**2026-09-10** — `Checker.tsx` sends `market` with only a `snapshot_id`, on
purpose: we did not derive that figure, and inventing a `contract_count` would be
inventing evidence. Nothing asserted that the backend accepts that exact shape.

If `MarketEvidenceIn` ever made the field required, **both suites would still
pass** — the backend builds its own payloads, the frontend mocks `fetch` — while
the one button that matters returned 422. This is the third instance of the same
class: `/evaluate` missing from the dev proxy, Tailwind classes emitting no CSS,
and now this. Each side correct alone; nothing testing the pair.

A backend test now reads the payload literal out of `Checker.tsx` and posts it
for real. It fails if the API tightens, and it fails if the checker starts
claiming a contract count. Both proven.

Found while chasing a 422 that turned out to be a stale server process from an
earlier command — `pkill` does not reach native Windows processes from Git Bash.
The bug was not real; **the missing test was.**

Fixing it exposed a trap next to it: `tests/api/test_evaluate.py` shares one
module-scoped client against the production limit of 30 requests a minute, so the
file was permanently one test away from 429s unrelated to anything it asserts.
That client is now unthrottled, and throttling is tested where it is the subject.

### D-069 · The comparable window ends at the data, never at today
**2026-09-10** — A rolling twelve months is the obvious aggregation, and both
obvious anchors are wrong.

Anchored on `now()`, the window slides off the end of the release. The file runs
to 2026-03-01; six months after publication a window to today covers 267,252
contracts instead of 555,607, and it keeps shrinking — no error, no signal, just
quietly thinner evidence and more cells dropping under the answer floor until
callers start being told there is no data for their area.

Anchored on `max(contract_start_date)`, it is worse. One contract in the real
release starts **2204-10-04**, and a twelve-month window ending there contains
exactly one row. **A single typo would empty the entire comparables table**, and
the ingest would report success.

So the snapshot carries a `data_horizon`: the 99.9th percentile of its own start
dates, which 41 obviously-wrong rows cannot move. Every window is anchored to it
and both ends are stored, so a figure quoted last month can be reproduced next
month. Dates more than a year past the horizon are now rejected outright
(`start_beyond_horizon`, 40 rows) along with two dated before Ejari existed.

### D-070 · Below the floor no median is computed, rather than computed and withheld
**2026-09-10** — G5 says a thin cell produces no figure. There are two ways to
honour that: compute every median and refuse to return the thin ones, or never
compute them. The second is chosen everywhere it is available.

The aggregate writes `median_annual_rent` as NULL below `min_contracts_for_answer`,
so for a four-contract cell **the number does not exist in the database at all**.
Nothing downstream can decide to speak it, log it, or put it on an evidence pack,
because there is nothing there. The contract count is kept — "we found only four"
is the honest thing to say and needs the four.

The floor the table was built under is recorded on the `aggregates` row, so a
figure can be explained later against the rule that produced it, and the lookup
re-checks the count against its own settings in case the two ever differ.

### D-071 · G5 at the lookup is a property of the type
**2026-09-10** — `Comparable` refuses construction if a non-`ok` status carries a
`median_annual_rent`, or a `full_confidence` flag. Every refusal path — thin,
stale, unknown area — is one `return` away from carrying a number by accident,
and this makes the accident impossible to express rather than merely absent from
the current code.

Same shape as `EvaluationRecord`, and for the same reason: the guarantee has to
live somewhere that a future edit cannot quietly step around.

### D-072 · Staleness is measured from the release, not from the ingest
**2026-09-10** — Measured from `computed_at`, a nightly job pointed at an old
file would report perfectly fresh comparables for ever. Re-processing an old
release does not make it new, and the clock that matters belongs to the newest
contract in it.

Staleness is also asked **before** thinness. Telling a caller "not enough
contracts in your area" when the real problem is that our whole release is six
months old is both wrong and unactionable — there is nothing they can do about
it, and it points them at the wrong thing.

**This has a live consequence.** The 2026-02-26 release has a horizon of
2026-03-01, which is 193 days old today, against a `market_snapshot_max_age_days`
of 120. Every lookup therefore returns `stale`, and every rent-increase answer
that would have relied on it returns HUMAN_REVIEW_REQUIRED. **That is the system
working, and it is also a blocker for the demo.** The 120 has no recorded
rationale — it was declared in T0.9 and never justified — so this is not a case
of data failing a considered threshold. See the open question in plan.md T2.3.

### D-073 · A missing derived input is our refusal, not the caller's mistake
**2026-09-10** — `_coerce_inputs` raised `MissingInputError` for any absent
required input, derived ones included. But a derived input is one *we* supply, so
our failing to supply it is exactly the G5 refusal — and raising there would send
"we have too little market data" back as a 422 blaming the caller for our gap.

A required input that is not derived is still the caller's to provide and still
raises. A derived one may be absent, and grading turns that into
HUMAN_REVIEW_REQUIRED. A second check closes behind it: if grading says the rule
is answerable, every declared input must be present before the rule runs, so a
grading bug cannot reach the rule logic with a hole in its inputs.

### D-074 · Market data is optional at boot and named in the health check
**2026-09-10** — The rules engine, the notice rule and a caller-supplied figure
all work without comparables. A service that refuses to start because one dataset
is missing takes down three things that were fine.

So a missing database logs a warning and `/healthz` reports
`market_data_loaded: false`, degrading `status`. `GET /comparables` answers 503
with the command that builds it. What is not acceptable is looking healthy while
a dataset the product advertises is absent.

`market_data_fresh` is a **separate** check, because a loaded snapshot older than
we will quote answers every lookup with `stale` — which reads as a broken service
unless the health check says why.

This retires the last `not_yet_checked` entry. `market_snapshot` had been
deferred there since T1.7.

### D-075 · The application is built once, not once per attribute lookup
**2026-09-10** — `__getattr__` returned `create_app()` without caching, and
uvicorn accesses `bayyina.api.app:app` more than once. Every boot therefore built
**two complete applications**: corpus verified twice, comparables database read
twice, static directory mounted twice.

The part that matters is not the wasted second. Two `AuditLog` objects existed,
each holding its own `threading.Lock` over the same file. Only one was ever
served, so the hash chain was never actually at risk — but a second lock over the
same log is exactly the shape of the concurrency bug D-035 exists to prevent, and
it should not be one refactor away from being live.

Fixed by writing the built app into the module namespace, so later lookups find
it there and never reach `__getattr__` again (PEP 562). Both halves of the
contract are now asserted: built exactly once however often it is looked up, and
still not built at import, so a broken corpus fails the process that asked for an
app rather than every test collection that imported `create_app`.

**Found by counting boot lines in a running container**, not by any test. T2.3
made it visible: two cheap corpus loads look like a log formatting quirk, two
database reads do not.

### D-076 · Freshness has two thresholds, and ageing data is disclosed not refused
**2026-09-10** — A single `market_snapshot_max_age_days` made staleness a cliff:
either the figure was quoted with nothing said, or nothing was quoted at all.
With a 193-day-old release and a 120-day limit, that meant **every rent question
returned HUMAN_REVIEW_REQUIRED**. The tempting fix was to raise 120 until our
file passed, which is the one change that makes a guardrail decorative.

Measured instead. Drift in the median cell, on pairs from 2024-09 onward:

| apart | median | p90 |
|---|---|---|
| 3 months | 3.4% | 10.7% |
| 6 months | 4.3% | 12.6% |
| 12 months | 6.1% | 15.4% |

**The rent-cap bands are five percentage points wide.** Past a year the median
cell has moved more than a whole band, so a stale figure can flip a verdict. Under
four months it has moved under ~3.5% and cannot.

So: `market_snapshot_fresh_days` (120) is where we start *saying* the figure is
ageing, and `market_snapshot_max_age_days` (365) is where we stop quoting it.
Between them the answer is given and carries `MARKET_DATA_AGEING` naming the date
it rests on. The old 120 survives as the disclosure point because the measurement
supports it — it previously had **no recorded rationale anywhere**.

This is the same shape as the comparable-count bands: `THIN_COMPARABLE_DATA`
discloses depth, `MARKET_DATA_AGEING` discloses recency. They **accumulate rather
than rank** — a thin *and* ageing comparable owes the listener both facts, and
reporting only the worse one would let someone act believing they had heard
everything wrong with the figure.

`age_days` is `None` for a caller-supplied figure. We cannot vouch for the
recency of a number we did not derive, and implying we checked is worse than
saying nothing.

**A design mistake caught while wiring it:** `market_data_fresh` was first added
to `/healthz` as a pass/fail check, which would have reported `degraded` for
eight months of every publication cycle — and a service that is always degraded
is one nobody reads the health of. It is now `market_data_usable` (can we answer
at all), with the age reported as a plain fact beside it.

### D-077 · The freshest data available is not on Dubai Pulse
**2026-09-10** — `www.dubaipulse.gov.ae` refuses connections outright, from two
independent networks. It is not a client problem and not a temporary blip we can
wait out.

Two other official hosts are live: `api.dubaipulse.gov.ae` (OAuth, needs a key)
and `dubailand.gov.ae`, whose Real Estate Data portal exports the same registry
as CSV. A Transactions export pulled from it on 2026-09-10 ran **to that same
day** and returned 154,262 rows uncapped — so the portal has current data and
will bulk-export it.

It is not a drop-in replacement. The portal's Rents tab returns `Annual Amount`,
`No of Units`, `Number of Rooms` — and **no contract identifier at all**, which
is what de-duplicates multi-property contracts. It also serves only the current
year ("For previous year data kindly visit Dubai Pulse"), so it supplements the
Pulse history rather than replacing it.

Third-party mirrors exist and are rejected: using one would break the claim that
**no government permission is required for any part of the product to work**,
which is a load-bearing part of the pitch, not a convenience.

`scripts/inspect_release.py` exists because of this. It reports what a file has,
which columns need mapping, whether a paginated export truncated, and the
horizon — so the next person to download one does not need to ask.

### D-078 · Recency is the cell's, never the release's
**2026-09-10** — D-076 built two freshness thresholds on `age_days`, and
`age_days` was the age of the *snapshot*. It should have been the age of the
figure being quoted, and for a tenth of the table those are not the same number.

Measured on the real release: of 841 quotable cells, **98 trail the horizon by
more than a month**, 10 by more than three, and one — `al rowaiyah first / flat /
studio`, 72 contracts — has a newest contract of 2025-07-19. That cell is **418
days old**, past the 365-day refusal threshold, and it was being quoted with a
"193 days" label attached.

So the aggregate stores `newest_contract` per cell and the lookup computes age
from it. `Al Rowaiyah First` now returns `stale` with no figure, which is what it
always should have done.

`ComparableStore.age_days()` survives as the release's own age, because that is
the right question for a health check — is this deployment's data worth anything
at all — and the wrong one for a lookup. The two are documented against each
other so the next reader does not reach for the convenient one.

The aggregation also now reports `oldest_quotable_contract`, so a build says at
build time whether it has produced figures already too old to quote. Learning
that once is cheaper than learning it one request at a time.

### D-079 · An `unknown_area` that offers nothing next is a dead end
**2026-09-10** — `/comparables` answers `unknown_area` when it cannot resolve a
place. The agent has then told someone we do not know where they live and has
nothing to say next, which on a phone call is where people hang up.

`GET /areas` returns all 184, by **display name** rather than by `area_key` —
`area_key` is our normalisation and nobody says "al barshaa south third" out
loud. Small enough to return whole, and small enough for an agent to match a
spoken place against. A test asserts every listed name actually resolves, because
a list containing something `/comparables` then rejects would send the agent
round a loop.

Alongside it, a boundary correction. `"   "` and `"!!!"` both passed
`min_length=1`, normalised to the empty key and came back as `unknown_area` —
technically true and useless. "We don't know that area" implies we looked.
Something that is not a place name is now a 422 that says so and points at
`/areas`, on both routes, because an agent that learns one of them lies stops
trusting either.

The distinction is deliberate: **"Narnia" is an outcome** — a real place name we
cannot resolve — **and punctuation is a malformed request**.

### D-080 · The palette is measured, and two colours failed
**2026-09-10** — T2.0 asks for "colour with **WCAG AA contrast verified**". It was
not verified; it was asserted in a comment. Measured:

* **`ink-300` at 2.46:1** — well under AA. Defined, used by nothing. Deleted
  rather than corrected: a token that exists will eventually be reached for, and
  the palette does not need a fourth ink.
* **`rule` at 1.26:1 — on the border of the rent input.** The one field a person
  has to find and type into had a boundary they could not see.

That second one is a design error, not a rounding error, and it produced the
split the system now has. **`rule`** separates rows of text and carries no
meaning if unseen. **`edge`** (#8a8370, 3.6:1) is any boundary a person must be
able to *find*. WCAG 1.4.11 asks 3:1 for the latter and nothing for the former,
and collapsing them meant every boundary took the weaker number.

`src/test/contrast.test.ts` computes every ratio from `index.css` itself, so the
claim is recomputed on every run rather than being true on the day it was typed.

**Two of the four tests in it proved nothing when first written**, and were only
found by breaking the code they guard:

* the focus-ring test matched `outline:` — which `outline: none` also matches, so
  deleting the ring left it green
* the interactive-border test scanned line by line, and a `className` five lines
  below its `<input` matched nothing. Then `[^>]*` was tried, which stops at the
  first `>` — and `onChange={(e) => ...}` has one. It now tracks brace depth,
  strips comments from the tag (the version before flagged its own explanation),
  and carries a guard asserting it finds elements at all, because a scan that
  matches nothing reports success either way.

### D-081 · Three scripts are bundled, not fetched
**2026-09-10** — Noto, because it is the only family covering Latin, Arabic and
Malayalam with one design, so two of the three languages are not visibly bolted
on. Six files, 175 KB, self-hosted.

Not Google Fonts. A page about someone's tenancy dispute should not announce
itself to a third party on load; the strict CSP forbids it anyway; and the PDF
pipeline (T2.5) needs the same faces on disk, so a CDN would mean the artifact a
resident carries into a hearing renders differently from the page that produced
it.

Only 400 and 600. A type system with seven weights is one nobody keeps
consistent.

### D-082 · The specimen is built from the product's own stylesheet
**2026-09-10** — `specimen.html` is a second Vite entry that imports
`src/index.css`, and its swatch grid reads computed values off
`document.documentElement` rather than repeating hexes. A specimen maintained
separately is wrong within a month, and a wrong specimen is worse than none.

**Its Arabic pane is genuinely `dir="rtl"`**, so what it shows is the mirroring
rather than a picture of it.

T2.0's DoD asks for "one page rendered in all three languages". That is **not
what this is**, and saying so matters: Arabic and Malayalam are not translated
(D-065), so the panes carry *typographic* text that states it is not product
copy. What the page demonstrates is that the three script stacks render at the
same sizes with the same rhythm, and that RTL mirrors. The translated product
page is T2.7 plus a translator.

### D-083 · A test fixture was adding a rule to the production stylesheet
**2026-09-10** — Tailwind v4 scans every file in the project for class names.
`styling-safety.test.ts` documents the banned v3 syntax `bg-[--color-ink-900]`,
so Tailwind found that string and **emitted the utility into the shipped CSS** —
`background-color:--color-ink-900`, with no `var()`, an invalid declaration that
does nothing. The test that exists to ban the syntax was the reason it shipped.

`@source not "./**/*.test.ts"` excludes tests from the scan, and a new test
asserts no such utility reaches the build. When that test was first written its
own explanatory comment leaked a second one, which is how it was confirmed to
work.

### D-084 · The evidence pack refuses a language rather than falling back
**2026-09-10** — The plan's own test asks that a pack render in all three
languages. It cannot: Arabic and Malayalam are untranslated (D-065), and the
straightforward way to make that test pass is an English fallback.

**The plan also says an English PDF for a Malayalam caller is a failed
delivery.** A fallback is exactly how that happens without anyone noticing — the
call completes, the pack sends, and the person cannot read the document they were
told to take to the Rental Dispute Centre. So `build_pack` raises
`UnsupportedLanguageError`, naming what is available.

`supported_languages()` is **derived from the template directories**, not listed,
so a language becomes supported the moment someone drops a translated
`pack.txt.j2` in — no code change, no second place to remember. Same shape as the
interface's switcher.

Each unsupported language carries a `_TRANSLATION_NEEDED.md` saying what is
needed and why it is blocked, and a test asserts the note exists and points at
the glossary. A gap nobody can find is a gap nobody closes. The Arabic note
states the real blocker — the official Arabic of Decree 43/2013 exists and must
be sourced rather than back-translated — and the Malayalam note states the
opposite, that no official register exists, because a translator told to source
something that does not exist will simply stop.

### D-085 · Vocabulary lives in one module, never in a template
**2026-09-10** — The first pack printed `Gap pct: 0.058824` and
`Current annual rent: 80000`. Both are wrong twice over: GLOSSARY section 1 gives
every internal name a different user-facing word on purpose — "the most they can
charge", never "legal rent", because the latter sounds like a fixed official
figure — and section 4 requires **AED 80,000**, never a bare number.

`wording.py` holds the mapping and the shape of every field. Templates carry no
vocabulary at all, so a translator working on the Arabic pack does not also have
to know that `gap_pct` is called "how far below the average", and there is no
second place for the glossary to drift.

**A field with no wording raises.** It does not fall back to its own name, so
adding a computed field forces a decision about how to say it out loud — which is
where that decision belongs, rather than in a template a fortnight later.

### D-086 · `pip install .` would have shipped no templates
**2026-09-10** — setuptools copies `.py` and nothing else unless told. The
evidence templates are `.j2`, and there was no `package-data` declaration — so
the container would have built, booted, verified its corpus, served `/healthz`,
and then failed on the **first evidence pack** with "template not found". The
worst moment and the least obvious cause.

Declared explicitly rather than through `include-package-data`, which depends on
what the VCS happens to be tracking. Guarded by a test that sweeps every
non-Python file under `src/bayyina` and asserts a pattern covers it, so the next
one added is caught the same way — verified against a real `pip install`, and CI
now renders a pack inside the built image, which is the only place that proves
the templates made the journey.

### D-087 · Three green suites, three red CI jobs
**2026-09-10** — Every job failed on a commit whose tests passed locally. Three
unrelated causes, one shared property: **none of them could fail on a developer's
machine.**

*Backend.* Dependencies are open `>=`, so CI installs the newest of everything.
It resolved Starlette 1.6, which stopped flattening included routers onto the
application — `isinstance(route, APIRoute)` matched nothing. The application was
fine; the *test* was reading a framework's private route table. It now reads
`app.openapi()["paths"]`, the published contract. Worth recording that the test
only failed at all because of its own guard, `assert served, "no API routes
found"` — without that line an empty set would have satisfied every later
assertion and reported success.

*Frontend.* Six styling tests each ran `vite build` if `dist/` was missing, under
Vitest's default 5 s timeout. Measured: **1 s here, 7 s on a single core**, which
is what a CI runner is. The build is now one cached hook with a timeout matched
to what it costs, and CI builds before it tests rather than twice.

*Image.* `COPY backend/data/ ./data/` cannot resolve a directory that is not
there, and every file in `backend/data/` is ignored — so the developer machine
has 359 MB in it and a fresh checkout has no such directory. Copying a directory
tolerates an *empty* one, not an *absent* one. A committed `.gitkeep` plus a
`.dockerignore` re-include, guarded by a test broken three ways to prove it.

**The unfixed part:** unpinned dependencies mean a release can still turn CI red
with no change to our source. Making the test robust was the right fix for the
test; it is not a fix for reproducibility.

### D-088 · The provenance page is generated from the table that runs
**2026-09-10** — A lawyer must be able to check our encoding against the decree
in under a minute. The obvious way to build that page is to write the encoding
out in prose beside the clause — and that prose is a second copy of the law which
drifts the first time someone edits one and not the other. Silently, because
nothing executes prose.

So `registry/explain.py` generates every sentence from `rule.bands`. Five bands
in the decree, five steps on the page, and changing the table changes the page.

The sentences are built from `gap_to` and never `gap_from`, because `gap_to` is
the bound the evaluator actually matches on. The schema already refuses a file
where the two disagree, so they cannot drift — but a page describing a boundary
nothing enforces would be worse than no page at all.

**The signature is recomputed on every request, never echoed from the file.** A
tampered rule carries a tampered signature block quite happily. And the review
notes are published rather than hidden: they record where the decree is ambiguous
and we had to choose, which is the difference between provenance and marketing.

### D-089 · `/evidence-pack` takes inputs, never a record
**2026-09-10** — `build_pack` refuses anything that is not an `EvaluationRecord`,
and a test walks the import graph to prove no language model can reach the
document path. None of that survives an HTTP endpoint that accepts a record: one
posted over the wire arrives already looking like a verdict we computed, carrying
our citation, our signature and our name.

The endpoint therefore takes the same body as `/evaluate` and recomputes. There
is no request shape that lets a caller choose what the document says. The shared
path also carries the audit append, so a third endpoint cannot produce an
evaluation the log never saw.

**A HUMAN_REVIEW_REQUIRED outcome still produces a pack.** It is not a
consolation prize: it is the document naming which facts were missing and which
rule would have applied, and it is the one a person takes to the Rental Dispute
Centre when we could not answer. Withholding it would leave them with nothing at
exactly the moment they need something.

Plain text, not PDF. T2.5 is deferred and the Malayalam glyph work it needs is
real; the text pack is complete, correct and printable today.

### D-090 · Deriving is offered only when it can actually happen
**2026-09-10** — The checker now asks for an area, a property type and a number
of bedrooms and derives the market average itself. The comparables database is
optional at boot (D-074) and is absent from the published image, so `/areas`
answering 503 is a supported state rather than a fault.

When it does, the choice disappears, the manual path stays, and the page says we
cannot work out an average right now. The alternative — showing the control and
failing on submit — offers a person a button that cannot work, which is the same
mistake as the language switcher in D-065.

### D-091 · `executescript` silently ended the transaction it was inside
**2026-09-10** — The migration runner opened a transaction, called
`executescript`, and rolled back on failure. `executescript` **issues a COMMIT
before it runs**, so the transaction was already gone: a migration failing
half-way would leave the schema partly changed, and the `rollback` in the
handler raised "cannot rollback - no transaction is active", losing the name of
the migration that actually failed.

Found by the test written for it — `test_a_failed_migration_is_not_recorded_as_applied`
— rather than by reading the code, which looked correct.

Statements are now executed one at a time inside the transaction, split with
`sqlite3.complete_statement` rather than on `;`: the parser SQLite ships knows a
semicolon inside a string or a trigger body does not end a statement, and a hand
split would work on today's migrations and break on the first one containing
either.

### D-092 · Consent is a log, not a boolean
**2026-09-10** — G8 says an opt-out cannot be undone. The obvious implementation
is a `granted` column, and the obvious bug is that anything holding a connection
can set it back to true — a retry, a replayed webhook, a "re-confirm consent"
step added in good faith next year.

So there is no boolean. `consent` is append-only and `opt_out` is **absorbing**:
`has()` answers false whenever one exists, whatever was written afterwards.
Irreversibility is a property of the shape of the data rather than the care of
every future caller. Proven by breaking it — replacing the check with a
latest-event read turns three tests red.

`opt_out` also cancels armed deadlines in the same transaction, because
honouring an opt-out from tomorrow is not honouring it.

**One test needed renaming.** `test_opting_out_cancels_anything_already_scheduled`
stayed green when the cancellation was removed, because `due()` independently
excludes opted-out calls. Defence in depth working — but the name claimed the
test pinned the write path, and it did not. It is now named for the outcome, and
says which tests pin each half.

### D-093 · A retry replays the document rather than producing another
**2026-09-10** — A voice agent retries: the network stalls, the tool call times
out, the platform sends it again. The caller must experience one action because
there was one action.

`Idempotency-Key` on `/evidence-pack` returns **the stored bytes**, not a fresh
render that happens to match — a pack quoted in a hearing must be the pack we
produced, and a re-render after a rule is re-signed would differ under the same
reference.

**The same key with a different body is a 409.** This is the half that is easy
to leave out and it is the one that matters: without it, a client reusing a key
by mistake — a constant, a badly seeded generator, a copied line — receives
somebody else's document. The stored request fingerprint turns a data leak into
a loud error.

Also fixed here: `TOOL_TIMEOUT_SECONDS` was declared in settings and applied to
nothing. There are no outbound calls yet, so `bayyina/outbound.py` exists now
with a test asserting nothing else in the package constructs an httpx client —
because a timeout added after the first outbound call is written is a timeout
added after it has already shipped without one.

### D-094 · A documented example that no longer works is worse than none
**2026-09-10** — A reader copies it, gets a 422, and concludes the API is broken.
So the OpenAPI examples are executed by a test rather than trusted.

That test proved nothing on its first attempt. The `/evaluate` dwelling example
**503s on the absent comparables database before the evaluator ever inspects the
inputs**, and 503 was in the accepted set — so renaming a field in the example
left the test green. Confirmed by breaking it.

The check that works reads each documented example against the signed rule it
names: every input must be one the rule declares, and every required
non-derived input must be present. No database, no network, and it fails on
exactly the mistake the round-trip misses.

### D-095 · One SQLite connection per thread, never one shared
**2026-09-10** — The case store opened one connection at boot and let every
handler use it. FastAPI runs sync handlers on a threadpool, and that design fails
twice over. Both were measured, not reasoned about.

**Writes trampled each other.** Four threads each opening a transaction on one
connection lost **72 of 100 rows** and raised `cannot start a transaction within
a transaction`. A transaction is state on the *connection*, not on the statement.
SQLite's own locking prevents file corruption and does nothing about this.

**Then reads went stale.** A lock around writes fixed the first bug and revealed
the second: a handler that wrote a row and read it back got nothing, because once
another thread opened a transaction on that connection, *every* read on it ran
inside that thread's older snapshot. The symptom was `no case 'case_844e1d0dedf2'`
for a case committed microseconds earlier — a caller told their case was open when
it was not.

A connection per thread fixes both by construction. WAL lets readers run through
a write, SQLite serialises the writers, and `busy_timeout` makes the loser wait.
`Store` also closes every connection it handed out, because a WAL left open
outlives the process and the next reader finds a database needing recovery.

The regression tests run four threads against the real store. Reverting to a
shared connection turns two of them red.

### D-096 · The failure taxonomy is the behaviour, not a document beside it
**2026-09-10** — `errors.py` declared a status for every failure and the agent
scripts are generated from it — and **nothing in `src/` imported it.** Every route
hardcoded its own number. The two agreed by coincidence, and would have drifted
the first time anyone changed one.

That drift is not cosmetic: the scripts tell the agent that market data absent is
a 503 it should talk through. A route returning something else mid-call produces
an unhandled failure while a caller is listening.

The four routes now read `behaviour(Failure.X).status`, and a test asserts both
that the codes match and that those files still import the taxonomy — because
wiring is undone by anyone typing a number back in.

### D-097 · "This needs a person" now reaches a person
**2026-09-10** — `HUMAN_REVIEW_REQUIRED` produced an honest document and reached
nobody. The service said a person should look at this, and no person was ever
told. Producing careful wording and dropping it on the floor is not honesty; it
is the same silence better phrased.

A pack for that outcome now opens a case, `awaiting_review` — `Cases.create` has
no parameter that could make it anything else (G4). An answered question opens
nothing, because a queue full of answered questions is a queue nobody reads.

The rendered pack is stored alongside it. A pack somebody was handed is a record
of what they were told, and re-rendering it later would produce a different
document under the same reference the first time a rule is re-signed.

**Failing to record does not fail the response.** The caller has a correct
document in their hands; losing our copy is ours to find in the logs.

### D-098 · Floors say what we need, constraints say what installs
**2026-09-10** — D-087 fixed the test that Starlette 1.6 broke and left the cause
alone: unpinned dependencies mean every install resolves whatever was published
that morning, so a green build can turn red with nobody touching it.

`constraints.txt` pins the resolution; `pyproject.toml` keeps the floors, because
those state what the code actually requires. CI, the Dockerfile and the developer
all install with `-c constraints.txt`, so the image ships what the suite ran
against.

Refreshing is a deliberate act: `scripts/refresh_constraints.py` re-resolves
inside `python:3.11-slim` — the runtime, not the developer's machine, which on
this project is Windows and Python 3.13. `--check` is cheap and asks only whether
every declared dependency is pinned. Whether newer versions exist is not a
question CI should ask; the answer changes whenever a stranger publishes a
release, which is the whole reason the file exists.

### D-099 · The translation gate, and why the drafts were backed out
**2026-09-10** — Arabic and Malayalam block T2.7 and T2.8, and T2.8 is a deadlock:
the comprehension gate cannot run without a document to put in front of a reader.
So the drafts were written — pack templates, 106 interface keys, labels, month
names — gated behind a marker so nothing could be delivered.

**Then a test said no.** `locales.test.ts` requires each marker to state that
*machine translation is not acceptable*, and the drafts were exactly that. That
rule is right and it is not ours to relax: this document tells someone what their
landlord may lawfully charge, and a plausible-sounding mistranslation is worse
than no document, because the reader has no way to tell. Every machine-authored
string was removed.

What stays is the machinery, which is what was actually missing:

* `_TRANSLATION_STATUS` gates delivery — a template appearing on disk no longer
  makes a language servable, and removing the marker is the act of approval;
* `build_pack(..., allow_draft=True)` renders an unreviewed template so the
  comprehension gate can be run before approval, and nothing serving a caller
  passes it;
* `label()`, `condition()` and `written_date()` take a language and **raise**
  rather than falling back, so a translator's first missing string fails loudly
  instead of producing Arabic prose with English scattered through it;
* the markers say what to check and in what order.

The gate is tested with a temporary language rather than a real draft, because it
has to work *before* a translator arrives — the failure it prevents is an
unreviewed template becoming deliverable the moment someone drops in a file.

**T2.7's language switcher and T2.8 remain blocked on a person, by this project's
own rule.** That is the honest state, and it is now a short piece of work for
whoever that person is rather than an open-ended one.

### D-100 · English at Stage 1, the other two languages with the voice work
**2026-09-10** — D-099 left Arabic and Malayalam blocked on a native speaker and
T2.8 unable to run. Rather than hold Phase 2 open on someone we have not yet
contacted, the interface and the pack ship in English.

This is not a retreat from the three-language promise; it is D-065 applied
honestly. A switcher offering a language that renders half in English is a broken
control however carefully it is captioned, and a machine translation of what a
landlord may lawfully charge is worse than an English document the reader can at
least recognise as not theirs.

The switcher already hides itself while one language is available and appears on
its own the moment a locale is filled in. Nothing needs rewriting when the
translations arrive — they land in `LABELS`, `MONTHS`, `pack.txt.j2` and the
locale files, and the marker comes off.

**T2.8 moves with them.** Running a comprehension gate on a machine draft would
produce false confidence: it tests wording nobody will ship. The gate belongs
beside T3.6, where the voice side needs the same translations.

What survives into Phase 3 unchanged is the reason the gate exists — that a
correct answer nobody understands is a failed answer. That is worth running in
English against two readers who are not us, and it costs an afternoon.
