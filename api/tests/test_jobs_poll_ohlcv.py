"""Tests for the Coinbase OHLCV polling endpoint."""

from __future__ import annotations

from datetime import timedelta

from ragtrader_api.app import create_app
from ragtrader_api.settings import ApiSettings, SchedulerSettings
from ragtrader_pipelines.coinbase import Granularity


def test_poll_ohlcv_invokes_job(monkeypatch):
    monkeypatch.setenv("RAGTRADER_SCHEDULER_COINBASE_SYMBOLS", "BTC-USD,ETH-USD")
    monkeypatch.setenv("RAGTRADER_SCHEDULER_COINBASE_GRANULARITY", "5m")
    monkeypatch.setenv("RAGTRADER_SCHEDULER_COINBASE_LOOKBACK_MINUTES", "30")
    monkeypatch.setenv(
        "RAGTRADER_SCHEDULER_DATABASE_DSN",
        "postgresql+psycopg://scheduler:pass@localhost:5432/app",
    )

    executed: dict[str, object] = {}

    class FakeJob:
        def run(self, *, symbols, granularity, lookback):  # type: ignore[override]
            executed["symbols"] = symbols
            executed["granularity"] = granularity
            executed["lookback"] = lookback

    def fake_factory(settings: ApiSettings, options: SchedulerSettings):
        executed["options"] = options
        assert isinstance(options, SchedulerSettings)
        return FakeJob()

    settings = ApiSettings(
        postgres_dsn="postgresql+psycopg://user:pass@localhost:5432/api",
        qdrant_url="http://localhost:6333",
        require_vector_store=False,
    )
    app = create_app(settings=settings, job_factory=fake_factory)

    response = app.dispatch("POST", "/jobs/poll_ohlcv")

    assert response.status_code == 202
    assert response.json["status"] == "accepted"
    assert response.json["symbols"] == ["BTC-USD", "ETH-USD"]
    assert response.json["granularity"] == Granularity.MIN_5.label
    assert response.json["lookback_minutes"] == 30

    assert executed["symbols"] == ("BTC-USD", "ETH-USD")
    assert executed["granularity"] == Granularity.MIN_5
    assert executed["lookback"] == timedelta(minutes=30)
