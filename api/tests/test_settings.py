"""Unit tests for API settings scaffolding."""

from __future__ import annotations

from pathlib import Path

import pytest

import ragtrader_api.settings as settings_module
from ragtrader_api.settings import ApiSettings, SettingsValidationError, get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure cached settings do not leak between tests."""

    get_settings.cache_clear()


def test_settings_require_postgres_dsn_when_database_required(
    # intentionally wrapped to respect line length
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in [
        "RAGTRADER_API_POSTGRES_DSN",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    ]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SettingsValidationError):
        ApiSettings(qdrant_url="http://localhost:6333", require_vector_store=False)


def test_settings_can_disable_database_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAGTRADER_API_REQUIRE_DATABASE", "false")
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "https://qdrant.cloud")
    monkeypatch.setenv("RAGTRADER_API_QDRANT_API_KEY", "key")
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
    monkeypatch.setenv("RAGTRADER_API_QDRANT_API_KEY", "key")

    settings = ApiSettings()

    assert settings.env == "staging"
    assert isinstance(settings.postgres_dsn, str)
    assert settings.postgres_dsn.startswith("postgresql+psycopg")


def test_settings_infer_postgres_dsn_from_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAGTRADER_API_POSTGRES_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "app")
    monkeypatch.setenv("POSTGRES_USER", "user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "pass")
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "https://example-qdrant")
    monkeypatch.setenv("RAGTRADER_API_QDRANT_API_KEY", "key")

    settings = ApiSettings()

    assert settings.postgres_dsn == (
        "postgresql+psycopg://user:pass@localhost:5432/app"
    )


def test_settings_load_from_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in [
        "RAGTRADER_API_POSTGRES_DSN",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "RAGTRADER_API_QDRANT_URL",
        "RAGTRADER_API_USE_QDRANT_CLOUD",
    ]:
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / "api.env"
    env_file.write_text(
        "\n".join(
            [
                "POSTGRES_HOST=env-host",
                "POSTGRES_PORT=5433",
                "POSTGRES_DB=env-db",
                "POSTGRES_USER=env-user",
                "POSTGRES_PASSWORD=env-pass",
                "RAGTRADER_API_QDRANT_URL=http://qdrant-env:6333",
                "RAGTRADER_API_USE_QDRANT_CLOUD=false",
            ]
        )
    )

    monkeypatch.setenv("RAGTRADER_API_ENV_FILE", env_file.as_posix())
    monkeypatch.setattr(settings_module, "_ENV_FILE_LOADED", False)

    settings = ApiSettings()

    assert settings.postgres_dsn == (
        "postgresql+psycopg://env-user:env-pass@env-host:5433/env-db"
    )
    assert settings.qdrant_url == "http://qdrant-env:6333"


def test_env_file_expands_placeholders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RAGTRADER_API_ENV", raising=False)
    monkeypatch.setenv(
        "RAGTRADER_API_POSTGRES_DSN",
        "postgresql+psycopg://user:pass@localhost:5432/app",
    )
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("RAGTRADER_API_USE_QDRANT_CLOUD", "false")

    env_file = tmp_path / "api.env"
    env_file.write_text("ENV=dev\nRAGTRADER_API_ENV=${ENV}\n")

    monkeypatch.setenv("RAGTRADER_API_ENV_FILE", env_file.as_posix())
    monkeypatch.setattr(settings_module, "_ENV_FILE_LOADED", False)

    settings = ApiSettings()

    assert settings.env == "dev"


def test_get_settings_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "RAGTRADER_API_POSTGRES_DSN",
        "postgresql+psycopg://user:pass@localhost:5432/app",
    )
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "https://example-qdrant")
    monkeypatch.setenv("RAGTRADER_API_QDRANT_API_KEY", "key")

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.readiness_checks()["vector_store"] is True


def test_settings_require_api_key_for_cloud() -> None:
    with pytest.raises(SettingsValidationError):
        ApiSettings(
            postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
            qdrant_url="https://qdrant.cloud",
            require_database=False,
            use_qdrant_cloud=True,
            require_vector_store=True,
        )
