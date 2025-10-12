"""Contract tests for the sentiment timeseries endpoint."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ragtrader_api.app import Response, create_app
from ragtrader_api.settings import ApiSettings


class FakeSentimentService:
    """Collect arguments passed to ``fetch_series`` and return canned data."""

    def __init__(self, *, last_updated: datetime) -> None:
        self.last_updated = last_updated
        self.fetch_series_calls: list[tuple[str, str]] = []
        self.returned_payloads: list[dict[str, Any]] = []

    def fetch_series(self, symbol: str, window: str) -> dict[str, Any]:
        self.fetch_series_calls.append((symbol, window))

        series = [
            {
                "ts": (self.last_updated - timedelta(minutes=30)).isoformat(),
                "polarity": 0.25,
                "confidence": 0.82,
                "zscore": 1.1,
                "aspects": ["macro", "momentum"],
            },
            {
                "ts": (self.last_updated - timedelta(minutes=15)).isoformat(),
                "polarity": -0.1,
                "confidence": 0.76,
                "zscore": -0.5,
                "aspects": ["regulation"],
            },
            {
                "ts": self.last_updated.isoformat(),
                "polarity": 0.4,
                "confidence": 0.91,
                "zscore": 1.8,
                "aspects": ["market", "derivatives"],
            },
        ]

        payload = {
            "symbol": symbol,
            "window": window,
            "series": series,
            "last_updated": self.last_updated,
        }
        self.returned_payloads.append(payload)
        return payload


@pytest.fixture()
def _settings() -> ApiSettings:
    return ApiSettings(env="dev", require_database=False, require_vector_store=False)


def test_get_sentiment_returns_series_with_freshness_guard(
    monkeypatch: pytest.MonkeyPatch, _settings: ApiSettings
) -> None:
    last_updated = datetime.now(UTC) - timedelta(minutes=5)
    fake_service = FakeSentimentService(last_updated=last_updated)

    def factory(*_: Any, **__: Any) -> FakeSentimentService:
        return fake_service

    monkeypatch.setattr(
        "ragtrader_api.app.create_sentiment_service",
        factory,
        raising=False,
    )

    app = create_app(settings=_settings)

    response = app.dispatch("GET", "/sentiment?symbol=BTC-USD&window=1h")

    assert isinstance(response, Response)
    assert fake_service.fetch_series_calls == [("BTC-USD", "1h")]
    assert response.status_code == 200

    data = response.json
    expected = fake_service.returned_payloads[-1]
    assert data["symbol"] == expected["symbol"]
    assert data["window"] == expected["window"]
    assert data["series"] == expected["series"]
    assert data["last_updated"] == expected["last_updated"].isoformat()

    freshness = data.get("freshness", {})
    assert isinstance(freshness, dict)
    assert freshness.get("age_minutes", float("inf")) < 10


def test_get_sentiment_rejects_stale_series(
    monkeypatch: pytest.MonkeyPatch, _settings: ApiSettings
) -> None:
    last_updated = datetime.now(UTC) - timedelta(minutes=45)
    fake_service = FakeSentimentService(last_updated=last_updated)

    def factory(*_: Any, **__: Any) -> FakeSentimentService:
        return fake_service

    monkeypatch.setattr(
        "ragtrader_api.app.create_sentiment_service",
        factory,
        raising=False,
    )

    app = create_app(settings=_settings)

    response = app.dispatch("GET", "/sentiment?symbol=BTC-USD&window=1h")

    assert fake_service.fetch_series_calls == [("BTC-USD", "1h")]
    assert response.status_code == 503
    payload = response.json
    assert "stale" in str(payload).lower()


@pytest.mark.parametrize(
    "path",
    [
        "/sentiment",
        "/sentiment?symbol=BTC-USD",
        "/sentiment?window=1h",
    ],
)
def test_get_sentiment_validates_required_query_params(
    path: str, monkeypatch: pytest.MonkeyPatch, _settings: ApiSettings
) -> None:
    created_services: list[FakeSentimentService] = []

    def factory(*_: Any, **__: Any) -> FakeSentimentService:
        service = FakeSentimentService(last_updated=datetime.now(UTC))
        created_services.append(service)
        return service

    monkeypatch.setattr(
        "ragtrader_api.app.create_sentiment_service",
        factory,
        raising=False,
    )

    app = create_app(settings=_settings)

    response = app.dispatch("GET", path)

    assert response.status_code == 400
    for service in created_services:
        assert service.fetch_series_calls == []
