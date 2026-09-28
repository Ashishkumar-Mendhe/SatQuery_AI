import pytest

from satquery.core.config import SettingsError, load_settings


def test_invalid_configuration_is_clear_and_redacts_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "do-not-print-this-secret"
    monkeypatch.setenv("DATABASE_URL", f"postgresql+psycopg://user:{secret}@")

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    message = str(captured.value)
    assert "Invalid backend configuration" in message
    assert "DATABASE_URL" in message
    assert secret not in message


def test_missing_database_configuration_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    assert "DATABASE_URL" in str(captured.value)


def test_production_rejects_loopback_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SATQUERY_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@database/satquery")
    monkeypatch.setenv("FRONTEND_CORS_ORIGINS", '["http://localhost:3000"]')

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    assert "production CORS origins" in str(captured.value)
    assert "password" not in str(captured.value)


def test_production_rejects_debug_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SATQUERY_ENV", "production")
    monkeypatch.setenv("SATQUERY_DEBUG", "true")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@database/satquery")
    monkeypatch.setenv("FRONTEND_CORS_ORIGINS", '["https://satquery.example.com"]')

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    assert "Production mode cannot enable debug" in str(captured.value)


def test_cors_entries_must_be_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@127.0.0.1/satquery_test")
    monkeypatch.setenv("FRONTEND_CORS_ORIGINS", '["http://localhost:3000/not-an-origin"]')

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    assert "origins without credentials or paths" in str(captured.value)


def test_api_prefix_cannot_drift_from_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@127.0.0.1/satquery_test")
    monkeypatch.setenv("SATQUERY_API_PREFIX", "/api/v2")

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    assert "SATQUERY_API_PREFIX" in str(captured.value)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.test/v1/",
        "https://earth-search.aws.element84.com:444/v1/",
        "http://earth-search.aws.element84.com/v1/",
    ],
)
def test_catalogue_provider_endpoint_cannot_be_redirected(
    monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@database/satquery")
    monkeypatch.setenv("EARTH_SEARCH_BASE_URL", endpoint)

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    assert "EARTH_SEARCH_BASE_URL" in str(captured.value)
    assert "Earth Search HTTPS v1 endpoint" in str(captured.value)


def test_settings_safe_summary_redacts_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:super_secret_db_pass@127.0.0.1/satquery_test"
    )
    monkeypatch.setenv("SATQUERY_AI_API_KEY", "super-secret-gemini-key")
    monkeypatch.setenv("SATQUERY_SATELLITE_CLIENT_SECRET", "super-secret-eo-secret")

    settings = load_settings(env_file=None)
    summary = settings.get_safe_summary()

    summary_str = str(summary)
    assert "super_secret_db_pass" not in summary_str
    assert "super-secret-gemini-key" not in summary_str
    assert "super-secret-eo-secret" not in summary_str
    assert summary["ai_has_api_key"] is True
    assert summary["satellite_has_credentials"] is True
    assert summary["contract_version"] == "1.0"
