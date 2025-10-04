"""Unit tests for API settings scaffolding."""

from __future__ import annotations

import pytest

from ragtrader_api.settings import ApiSettings, SettingsValidationError, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure cached settings do not leak between tests."""

    get_settings.cache_clear()


def test_settings_require_postgres_dsn_when_database_required() -> None:
    with pytest.raises(SettingsValidationError):
        ApiSettings(qdrant_url="https://qdrant.cloud")


def test_settings_can_disable_database_requirement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGTRADER_API_REQUIRE_DATABASE", "false")
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "https://qdrant.cloud")
    settings = ApiSettings()

    assert settings.require_database is False
    assert settings.readiness_checks()["database"] is True


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGTRADER_API_ENV", "staging")
    monkeypatch.setenv(
        "RAGTRADER_API_POSTGRES_DSN",
        "postgresql+psycopg://user:pass@localhost:5432/app",
    )
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "https://example-qdrant")

    settings = ApiSettings()

    assert settings.env == "staging"
    assert isinstance(settings.postgres_dsn, str)
    assert settings.postgres_dsn.startswith("postgresql+psycopg")


def test_get_settings_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "RAGTRADER_API_POSTGRES_DSN",
        "postgresql+psycopg://user:pass@localhost:5432/app",
    )
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "https://example-qdrant")

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.readiness_checks()["vector_store"] is True
