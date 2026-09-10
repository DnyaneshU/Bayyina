"""Configuration, read from the environment.

Guardrail thresholds live here rather than as literals scattered through the
code, so that a reviewer can see every value that changes agent behaviour in one
place. See `.env.example` for the documented variables.
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Environment ---------------------------------------------------------
    bayyina_env: str = "local"
    bayyina_base_url: str = "http://localhost:8000"
    log_level: str = "INFO"

    # --- Paths ---------------------------------------------------------------
    rules_dir: Path = Path("rules")
    data_dir: Path = Path("data")

    # The built frontend, served by this process in production so the whole
    # product stays one container. Absent in local development, where the Vite
    # dev server serves it and proxies the API here.
    frontend_dist: Path = Path("static")

    # --- Guardrail thresholds ------------------------------------------------
    # G5: below `min_contracts_for_answer` the engine returns HUMAN_REVIEW_REQUIRED
    # and no figure may be spoken or printed. Between that and
    # `min_contracts_for_full_confidence`, confidence is reduced.
    # Measured 2026-09-09: 99.1% of contracts sit in cells with >= 30 comparables.
    min_contracts_for_answer: int = 10
    min_contracts_for_full_confidence: int = 30

    # Freshness has two thresholds, not one, and both are measured from the
    # newest contract in the release - never from when we processed it. Re-running
    # an ingest over an old file does not make it new.
    #
    # **Measured on 5.3M contracts, pairs from 2024-09 onward:**
    #
    #   | apart    | median cell drift | p90   |
    #   |----------|-------------------|-------|
    #   | 3 months | 3.4%              | 10.7% |
    #   | 6 months | 4.3%              | 12.6% |
    #   | 12 months| 6.1%              | 15.4% |
    #
    # The rent-cap bands are five percentage points wide (0/5/10/15/20%), so
    # these are the numbers that decide whether staleness can flip a verdict.
    #
    # Under `fresh`, drift sits under ~3.5% and the figure is quoted plainly.
    # Between the two, it is quoted with the condition MARKET_DATA_AGEING naming
    # the date it came from - the same shape as THIN_COMPARABLE_DATA, which
    # discloses depth rather than recency. Past `max_age` the median cell has
    # moved more than a whole band and the figure no longer describes the market,
    # so there is nothing to quote.
    #
    # The previous single threshold of 120 had **no recorded rationale anywhere**.
    # It survives as the disclosure point because the measurement supports it.
    market_snapshot_fresh_days: int = 120
    market_snapshot_max_age_days: int = 365

    # NOTE: rule parameters do NOT belong here.
    #
    # The 90-day notice period is a property of Law 26/2007 Article 14 and lives
    # in the signed rule file, where it is covered by the signature and shown on
    # the provenance page beside the clause it came from. Putting it in settings
    # would make the rule file decorative: an operator could change the law by
    # editing an environment variable, and the signature would still verify.
    #
    # Thresholds above are different. They are *our* operational choices about
    # when we decline to answer, not statements about what the law says.

    # --- Limits --------------------------------------------------------------
    # Applied to every public route except /healthz, which platforms poll.
    public_rate_limit_per_minute: int = 30

    # NOT YET CONSUMED - T2.10, the outbound timeout on agent-facing webhooks.
    tool_timeout_seconds: int = 3

    @model_validator(mode="after")
    def _production_must_be_https(self) -> "Settings":
        """In production the base URL must be https.

        This is not decoration. `bayyina_base_url` is what goes into the SMS a
        resident receives - the link to their own evidence pack, containing the
        rent they stated and the case we built for them. Sent over http that is
        readable in transit, and the person receiving it has no way to tell.

        TLS itself is terminated by the platform edge, not by this process. What
        this check prevents is the app *minting* http links while sitting behind
        an https edge, which looks fine in every log and is wrong in the only
        place that matters.
        """
        if self.bayyina_env == "production" and not self.bayyina_base_url.startswith("https://"):
            raise ValueError(
                f"BAYYINA_ENV is 'production' but BAYYINA_BASE_URL is "
                f"'{self.bayyina_base_url}'. Evidence-pack links are sent to residents "
                f"by SMS; in production that URL must be https."
            )
        return self


def get_settings() -> Settings:
    """Load settings. Kept as a function so tests can construct their own."""
    return Settings()
