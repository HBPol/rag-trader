"""Integration-style tests for API health endpoints."""

from __future__ import annotations

import pytest

from ragtrader_api.app import create_app
from ragtrader_api.settings import ApiSettings


def test_healthz_reports_service_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "RAGTRADER_API_POSTGRES_DSN",
        "postgresql+psycopg://user:pass@localhost:5432/app",
    )
    monkeypatch.setenv("RAGTRADER_API_QDRANT_URL", "https://example-qdrant")
    settings = ApiSettings()
    app = create_app(settings=settings)

    response = app.dispatch("GET", "/healthz")

    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.json["service"] == settings.app_name
    assert response.json["environment"] == settings.env


def test_readyz_indicates_dependency_failures() -> None:
    settings = ApiSettings(
        postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/app",
        qdrant_url="https://example-qdrant",
    )
    # Simulate a missing dependency in readiness checks.
    settings.postgres_dsn = None
    app = create_app(settings=settings)

    response = app.dispatch("GET", "/readyz")

    assert response.status_code == 503
    assert response.json["status"] == "error"
    assert response.json["checks"]["database"] is False