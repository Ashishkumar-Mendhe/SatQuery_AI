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


def test_runtime_ai_configuration_is_all_or_none_and_redacts_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "runtime-secret-must-not-leak"
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@database/satquery")
    monkeypatch.setenv("RUNTIME_AI_PROVIDER", "openai")
    monkeypatch.setenv("RUNTIME_AI_API_KEY", secret)
    monkeypatch.delenv("RUNTIME_AI_MODEL", raising=False)

    with pytest.raises(SettingsError) as captured:
        load_settings(env_file=None)

    assert "configured together" in str(captured.value)
    assert secret not in str(captured.value)


def test_pinned_runtime_ai_configuration_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@database/satquery")
    monkeypatch.setenv("RUNTIME_AI_PROVIDER", "openai")
    monkeypatch.setenv("RUNTIME_AI_API_KEY", "synthetic-key")
    monkeypatch.setenv("RUNTIME_AI_MODEL", "gpt-4.1-mini-2025-04-14")

    settings = load_settings(env_file=None)

    assert settings.runtime_ai_available is True
    assert settings.runtime_ai_api_key is not None
    assert "synthetic-key" not in repr(settings.runtime_ai_api_key)


def test_xai_key_is_server_only_and_model_must_match(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@database/satquery")
    monkeypatch.setenv("RUNTIME_AI_PROVIDER", "xai")
    monkeypatch.setenv("RUNTIME_AI_MODEL", "grok-4.3")
    monkeypatch.setenv("XAI_API_KEY", "synthetic-xai-key")

    settings = load_settings(env_file=None)
    assert settings.runtime_ai_available is True
    assert settings.xai_api_key is not None
    assert "synthetic-xai-key" not in repr(settings)

    monkeypatch.setenv("RUNTIME_AI_MODEL", "gpt-4.1-mini-2025-04-14")
    with pytest.raises(SettingsError, match="do not match"):
        load_settings(env_file=None)


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
