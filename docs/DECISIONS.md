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
