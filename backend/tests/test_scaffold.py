"""The package imports and settings load. The first thing that must be true."""


def test_package_imports():
    import bayyina

    assert bayyina.__version__


def test_settings_have_required_paths(tmp_path):
    from bayyina.settings import Settings

    settings = Settings(rules_dir=tmp_path, data_dir=tmp_path)
    assert settings.rules_dir == tmp_path
    assert settings.data_dir == tmp_path


def test_settings_carry_the_guardrail_thresholds():
    """G5 thresholds are configuration, not magic numbers scattered in code."""
    from bayyina.settings import Settings

    settings = Settings()
    assert settings.min_contracts_for_answer == 10
    assert settings.min_contracts_for_full_confidence == 30


def test_settings_do_not_carry_rule_parameters():
    """A law is not an environment variable.

    Rule parameters such as the 90-day notice period live in the signed rule
    file, covered by the signature and shown on the provenance page. If one ever
    appears here, an operator could change the law by editing config while the
    signature still verified.
    """
    from bayyina.settings import Settings

    forbidden = {"notice_required_days", "max_increase", "rent_increase_bands"}
    assert forbidden.isdisjoint(Settings.model_fields)


def test_production_refuses_a_non_https_base_url():
    """The base URL becomes the SMS link to someone's evidence pack.

    TLS is terminated at the platform edge, but the app must not mint http links
    while sitting behind an https edge - that looks correct in every log and is
    wrong in the only place it matters.
    """
    import pytest
    from pydantic import ValidationError

    from bayyina.settings import Settings

    with pytest.raises(ValidationError, match="https"):
        Settings(bayyina_env="production", bayyina_base_url="http://bayyina.example")

    ok = Settings(bayyina_env="production", bayyina_base_url="https://bayyina.example")
    assert ok.bayyina_base_url.startswith("https://")


def test_local_development_may_use_http():
    """Requiring TLS on localhost would just teach everyone to disable the check."""
    from bayyina.settings import Settings

    assert Settings(bayyina_env="local", bayyina_base_url="http://localhost:8000")


# Documented in .env.example for Phase 3, deliberately not modelled yet. Listed
# explicitly so that adding a variable to the template without either wiring it
# or acknowledging it here fails the build.
PHASE_3_ENV_VARS = {
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "TWILIO_WHATSAPP_FROM",
    "TWILIO_TIMEOUT_SECONDS",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_AGENT_ID",
    "ELEVENLABS_WEBHOOK_SECRET",
}


def _documented_env_vars() -> set[str]:
    import re
    from pathlib import Path

    template = Path(__file__).resolve().parents[1] / ".env.example"
    return {
        match.group(1)
        for line in template.read_text(encoding="utf-8").splitlines()
        if (match := re.match(r"^([A-Z][A-Z0-9_]*)=", line.strip()))
    }


def test_every_documented_variable_is_modelled_or_acknowledged():
    """`extra="ignore"` means an unmodelled variable is silently dropped.

    An operator who sets one and sees no effect has no way to tell whether it
    worked. This makes the gap explicit rather than silent.
    """
    from bayyina.settings import Settings

    modelled = {name.upper() for name in Settings.model_fields}
    unexplained = _documented_env_vars() - modelled - PHASE_3_ENV_VARS
    assert not unexplained, (
        f"documented in .env.example but neither modelled nor listed: {unexplained}"
    )


def test_every_setting_is_documented_in_the_template():
    """A setting nobody can discover is a setting nobody will set correctly."""
    from bayyina.settings import Settings

    modelled = {name.upper() for name in Settings.model_fields}
    undocumented = modelled - _documented_env_vars()
    assert not undocumented, f"in Settings but missing from .env.example: {undocumented}"
