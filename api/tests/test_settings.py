"""Unit tests for API settings scaffolding."""

from ragtrader_api.settings import ApiSettings


def test_settings_require_dsn_for_configuration() -> None:
    settings = ApiSettings(postgres_dsn=None, qdrant_url="https://qdrant")
    assert not settings.is_configured()


def test_settings_validate_qdrant_url_scheme() -> None:
    settings = ApiSettings(postgres_dsn="postgresql://user:pass@localhost/db", qdrant_url="https://qdrant")
    assert settings.is_configured()
