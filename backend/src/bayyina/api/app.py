"""Application assembly.

`create_app()` loads and verifies the corpus **before it returns an app**. There
is no window in which the service is listening on a port with rules nobody
attested to: the process either starts with a verified corpus or does not start.
That is guardrail G7 at the process level, and it is the demo's wow moment - one
digit changed in a signed rule and this raises instead of serving.

The corpus, the evaluator and the audit log are built once here and shared. A
rule evaluation is a pure function over data already in memory, which is how the
latency budget is met without a cache.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from bayyina.audit import AuditLog
from bayyina.market.comparables import ComparableStore, MarketDataUnavailableError
from bayyina.observability import add_response_timing, configure_logging
from bayyina.registry.evaluator import EvaluationError, Evaluator, UnknownRuleError
from bayyina.registry.loader import load_rules
from bayyina.registry.schema import ApprovalStatus
from bayyina.rules_logic.errors import RuleInputError, RuleLogicError
from bayyina.settings import Settings, get_settings

from .rate_limit import add_rate_limiting
from .routes_evaluate import router as evaluate_router
from .security import add_security_headers

logger = logging.getLogger("bayyina")

DESCRIPTION = """
Bayyina converts published tenancy rules into a safe, conversational workflow
that determines what can be determined, produces the evidence a person needs to
act, and stops whenever the facts require human judgement.

**Not legal advice. Not an official determination.** Bayyina is not a government
entity and does not act for any authority.
"""


def _register_error_handlers(app: FastAPI) -> None:
    """Map failures onto status codes that mean what they say.

    The distinction is whose problem it is. A caller who sent an unusable value
    gets a 4xx and can fix it. A rule that cannot answer is a 5xx, because the
    corpus is wrong and no amount of retrying will help - and it must be loud
    rather than dressed up as a complaint about the request.
    """

    @app.exception_handler(UnknownRuleError)
    async def _unknown_rule(_: Request, exc: UnknownRuleError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(EvaluationError)
    async def _bad_evaluation_request(_: Request, exc: EvaluationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RuleInputError)
    async def _bad_input(_: Request, exc: RuleInputError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(RuleLogicError)
    async def _broken_rule(_: Request, exc: RuleLogicError) -> JSONResponse:
        # A signed rule passed load-time validation and still had no answer to
        # give. That is a defect in our encoding, or in the validator that was
        # meant to catch it, so it is logged at error level rather than absorbed.
        logger.error("rule logic failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "A rule could not be applied. This has been logged."},
        )


def create_app(
    *,
    rules_dir: Path | str | None = None,
    audit_path: Path | str | None = None,
    static_dir: Path | str | None = None,
    market_db: Path | str | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Build the application, or refuse to.

    Raises `CorpusError` - unsigned, tampered, malformed or empty - before any
    route exists. The caller is uvicorn, so the process exits.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # G7. Before anything else, and deliberately not inside a startup event:
    # a startup event that raises still leaves a constructed app object behind.
    rules = load_rules(rules_dir if rules_dir is not None else settings.rules_dir)

    app = FastAPI(
        title="Bayyina",
        description=DESCRIPTION,
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.rules = rules
    app.state.rule_count = len(rules)
    app.state.corpus_signed = all(
        rule.approval.status is not ApprovalStatus.UNSIGNED for rule in rules.values()
    )
    app.state.evaluator = Evaluator(rules, settings=settings)
    app.state.audit = AuditLog(
        audit_path if audit_path is not None else Path(settings.data_dir) / "audit.jsonl"
    )
    app.state.audit.path.parent.mkdir(parents=True, exist_ok=True)

    # Market data is optional at boot, and deliberately so. The rules engine, the
    # notice rule and a caller-supplied market figure all work without it, and a
    # service that refuses to start because one dataset is missing takes down
    # three things that were fine. Its absence is reported by /healthz rather
    # than hidden - a green check that lies is worse than none.
    # `comparables.duckdb`, not `market.duckdb`. The build database carries 5.3M
    # contract rows the request path never reads; the serving one is 1.3 MB.
    market_path = (
        market_db if market_db is not None else Path(settings.data_dir) / "comparables.duckdb"
    )
    try:
        app.state.comparables = ComparableStore(market_path, settings=settings)
        logger.info(
            "comparables loaded: snapshot %s, %s .. %s",
            app.state.comparables.snapshot_id,
            app.state.comparables.window_start,
            app.state.comparables.window_end,
        )
    except MarketDataUnavailableError as unavailable:
        app.state.comparables = None
        logger.warning("no market comparables: %s", unavailable)

    # Order matters. Middleware added later runs first, so timing wraps the
    # limiter: a 429 is still measured and still carries x-response-ms.
    add_rate_limiting(app, settings.public_rate_limit_per_minute)
    add_security_headers(app)
    add_response_timing(app)
    _register_error_handlers(app)
    app.include_router(evaluate_router)

    # Mounted last, so it can never shadow an API route: FastAPI matches in the
    # order routes are added, and a mount at "/" catches everything after it.
    # Missing in development, where Vite serves the frontend and proxies here -
    # so its absence is normal and logged rather than treated as a failure.
    static_root = static_dir if static_dir is not None else settings.frontend_dist
    if Path(static_root).is_dir():
        app.mount("/", StaticFiles(directory=static_root, html=True), name="frontend")
        logger.info("serving the built frontend from %s", Path(static_root).resolve())
    else:
        logger.info("no built frontend at %s; API only", Path(static_root).resolve())

    logger.info(
        "corpus loaded: %d rule(s) - %s",
        len(rules),
        ", ".join(
            f"{rule.id} v{rule.version} [{rule.approval.status.value}]" for rule in rules.values()
        ),
    )
    return app


def __getattr__(name: str) -> FastAPI:
    """Build the app on first access to `bayyina.api.app:app`.

    This keeps two things true at once. `uvicorn bayyina.api.app:app` works as
    documented, and refuses to start on a bad corpus - the tamper demo depends on
    that. And importing this module has no side effect, so a broken corpus fails
    the one process that asked for an app rather than every test collection that
    happened to import `create_app`.

    **Built once.** The result is written into the module namespace, so every
    later lookup finds it there and never reaches this function again (PEP 562).
    Without that, uvicorn's two accesses built two complete applications: the
    corpus was verified twice, the comparables database read twice, and **two
    `AuditLog` objects existed with a lock each**. Only one was ever served, so
    the chain was never actually at risk - but a second audit log holding a
    second lock over the same file is precisely the shape of the concurrency bug
    D-035 exists to prevent, and it should not be one refactor away.
    """
    if name == "app":
        built = create_app()
        globals()["app"] = built
        return built
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
