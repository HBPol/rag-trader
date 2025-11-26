"""Unit tests for API settings scaffolding."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

import ragtrader_api.settings as settings_module
from ragtrader_api.settings import (
    ApiSettings,
    SchedulerSettings,
    SettingsValidationError,
    get_settings,
)
from ragtrader_pipelines.coinbase import Granularity


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
    monkeypatch.setenv(
        "RAGTRADER_API_CORS_ORIGINS",
        "https://frontend.example.com,https://alt-frontend.example.com",
    )

    settings = ApiSettings()

    assert settings.env == "staging"
    assert isinstance(settings.postgres_dsn, str)
    assert settings.postgres_dsn.startswith("postgresql+psycopg")
    assert settings.cors_origins == (
        "https://frontend.example.com",
        "https://alt-frontend.example.com",
    )


def test_settings_infer_analytics_symbols_from_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "http://localhost:6333")
    settings = ApiSettings(
        postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
        qdrant_url="http://localhost:6333",
        require_database=False,
        require_vector_store=False,
        analytics_pairs=("BTC-ETH", "ETH-SOL"),
    )

    assert settings.analytics_symbols == ("BTC", "ETH", "SOL")


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
    monkeypatch.delenv("ENV", raising=False)
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


def test_default_cors_origins_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAGTRADER_API_CORS_ORIGINS", raising=False)

    settings = ApiSettings(
        postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
        qdrant_url="http://localhost:6333",
        require_database=False,
        require_vector_store=False,
    )

    assert settings.cors_origins == ("http://localhost:5173",)


def test_cors_origins_required_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGTRADER_API_ENV", "prod")
    monkeypatch.setenv("RAGTRADER_API_CORS_ORIGINS", "")

    with pytest.raises(SettingsValidationError):
        ApiSettings(
            postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
            qdrant_url="http://localhost:6333",
            require_database=False,
            require_vector_store=False,
        )


def test_cors_origins_required_in_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGTRADER_API_ENV", "staging")
    monkeypatch.delenv("RAGTRADER_API_CORS_ORIGINS", raising=False)

    with pytest.raises(SettingsValidationError):
        ApiSettings(
            postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
            qdrant_url="http://localhost:6333",
            require_database=False,
            require_vector_store=False,
        )


def test_settings_require_api_key_for_cloud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAGTRADER_API_QDRANT_API_KEY", raising=False)
    monkeypatch.delenv("QDRANT_API_KEY", raising=False)
    with pytest.raises(SettingsValidationError):
        ApiSettings(
            postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
            qdrant_url="https://qdrant.cloud",
            require_database=False,
            use_qdrant_cloud=True,
            require_vector_store=True,
        )


def test_settings_fall_back_to_unprefixed_qdrant_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAGTRADER_API_QDRANT_API_KEY", raising=False)
    monkeypatch.setenv("QDRANT_API_KEY", "fallback-key")

    settings = ApiSettings(
        postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
        qdrant_url="https://qdrant.cloud",
        require_database=False,
        use_qdrant_cloud=True,
        require_vector_store=True,
    )

    assert settings.qdrant_api_key == "fallback-key"


def test_scheduler_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGTRADER_SCHEDULER_COINBASE_SYMBOLS", "btc-usd,eth-usd")
    monkeypatch.setenv("RAGTRADER_SCHEDULER_COINBASE_GRANULARITY", "MIN_15")
    monkeypatch.setenv("RAGTRADER_SCHEDULER_COINBASE_LOOKBACK_MINUTES", "45")
    monkeypatch.setenv(
        "RAGTRADER_SCHEDULER_DATABASE_DSN",
        "postgresql+psycopg://scheduler:pass@localhost:5432/app",
    )

    settings = ApiSettings(
        postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
        qdrant_url="http://localhost:6333",
        require_database=False,
        require_vector_store=False,
    )

    scheduler = settings.scheduler_options()

    assert isinstance(scheduler, SchedulerSettings)
    assert scheduler.symbols == ("BTC-USD", "ETH-USD")
    assert scheduler.granularity is Granularity.MIN_15
    assert scheduler.lookback == timedelta(minutes=45)
    assert scheduler.database_dsn.endswith("/app")


def test_scheduler_settings_fall_back_to_api_dsn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAGTRADER_SCHEDULER_DATABASE_DSN", raising=False)
    monkeypatch.delenv("RAGTRADER_SCHEDULER_DATABASE_SECRET_NAME", raising=False)

    settings = ApiSettings(
        postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
        qdrant_url="http://localhost:6333",
        require_database=False,
        require_vector_store=False,
    )

    scheduler = settings.scheduler_options()

    assert scheduler.database_dsn == "postgresql+psycopg://user:pass@localhost:5432/app"
    assert scheduler.granularity is Granularity.MIN_1
    assert scheduler.lookback == timedelta(minutes=15)
