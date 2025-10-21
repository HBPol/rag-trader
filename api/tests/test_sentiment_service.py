"""Unit tests for the sentiment service module."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from ragtrader_api.sentiment import (
    SentimentObservation,
    SentimentService,
    SqlAlchemySentimentRepository,
    _coerce_window,
    _normalize_symbol,
    create_sentiment_service,
)
from ragtrader_api.settings import ApiSettings, SettingsValidationError


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("btc-usd", "BTC"),
        (" ETH  ", "ETH"),
        ("sol-usd", "SOL"),
    ],
)
def test_normalize_symbol_strips_and_uppercases(raw: str, expected: str) -> None:
    assert _normalize_symbol(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   "],
)
def test_normalize_symbol_rejects_empty_values(raw: str) -> None:
    with pytest.raises(ValueError):
        _normalize_symbol(raw)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("15m", 15),
        ("90M", 90),
        ("2h", 120),
        ("1day", 24 * 60),
    ],
)
def test_coerce_window_supports_multiple_units(raw: str, expected: int) -> None:
    assert _coerce_window(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "abc", "15w"],
)
def test_coerce_window_rejects_invalid_inputs(raw: str) -> None:
    with pytest.raises(ValueError):
        _coerce_window(raw)


class RecordingRepository:
    """Fake repository capturing calls and returning canned observations."""

    def __init__(
        self,
        *,
        observations: Iterable[SentimentObservation],
        last_updated: datetime | None,
    ) -> None:
        self._observations = list(observations)
        self._last_updated = last_updated
        self.calls: list[dict[str, Any]] = []

    def fetch_series(self, *, coin: str, window_minutes: int):
        self.calls.append({"coin": coin, "window_minutes": window_minutes})
        return list(self._observations), self._last_updated


def test_sentiment_service_fetch_series_serializes_repository_results() -> None:
    request_symbol = "BTC-USD"
    window = "15m"

    polarity = Decimal("0.25")
    confidence = Decimal("0.8")
    zscore = Decimal("1.5")
    timestamp = datetime(2024, 1, 1, 12, 30, tzinfo=UTC)

    observations = [
        SentimentObservation(
            ts=timestamp,
            polarity=float(polarity),
            confidence=float(confidence),
            zscore=float(zscore),
            aspects=("macro", "momentum"),
        )
    ]

    repo = RecordingRepository(observations=observations, last_updated=timestamp)
    service = SentimentService(repository=repo)

    payload = service.fetch_series(request_symbol, window)

    assert repo.calls == [{"coin": "BTC", "window_minutes": 15}]
    assert payload["symbol"] == request_symbol
    assert payload["window"] == window

    series = payload["series"]
    assert isinstance(series, list)
    assert len(series) == 1

    entry = series[0]
    assert entry["ts"] is timestamp
    assert entry["polarity"] == float(polarity)
    assert isinstance(entry["polarity"], float)
    assert entry["confidence"] == float(confidence)
    assert isinstance(entry["confidence"], float)
    assert entry["zscore"] == float(zscore)
    assert isinstance(entry["zscore"], float)
    assert entry["aspects"] == ["macro", "momentum"]

    assert payload["last_updated"] == timestamp


def test_sentiment_service_fetch_series_uses_current_time_when_missing_last_updated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observations = [
        SentimentObservation(
            ts=datetime(2024, 1, 2, 9, 0, tzinfo=UTC),
            polarity=0.1,
            confidence=0.9,
            zscore=0.5,
            aspects=("news",),
        )
    ]
    repo = RecordingRepository(observations=observations, last_updated=None)
    service = SentimentService(repository=repo)

    expected_now = datetime(2024, 1, 2, 10, 0, tzinfo=UTC)

    class _Now:
        @staticmethod
        def now(tz: Any = None) -> datetime:
            assert tz is UTC
            return expected_now

    monkeypatch.setattr("ragtrader_api.sentiment.datetime", _Now)

    payload = service.fetch_series("btc-usd", "30m")

    assert repo.calls == [{"coin": "BTC", "window_minutes": 30}]
    assert payload["last_updated"] is expected_now


class _SessionContext:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.received_stmt = None

    def __enter__(self) -> _SessionContext:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, stmt: Any):
        self.received_stmt = stmt
        yield from self._rows


class StubSessionFactory:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.instances: list[_SessionContext] = []

    def __call__(self) -> _SessionContext:
        context = _SessionContext(list(self._rows))
        self.instances.append(context)
        return context


def test_sqlalchemy_repository_fetch_series_normalizes_rows() -> None:
    aware_ts = datetime(2024, 2, 1, 8, 0, tzinfo=UTC)
    naive_ts = datetime(2024, 2, 1, 9, 0)

    rows = [
        SimpleNamespace(
            ts=aware_ts,
            polarity=Decimal("0.1"),
            confidence=Decimal("0.2"),
            zscore=Decimal("0.3"),
            aspects=["macro"],
            published_ts=aware_ts - timedelta(minutes=30),
        ),
        SimpleNamespace(
            ts=None,
            polarity=None,
            confidence=Decimal("0.5"),
            zscore=None,
            aspects=None,
            published_ts=naive_ts,
        ),
    ]

    session_factory = StubSessionFactory(rows)
    repository = SqlAlchemySentimentRepository(session_factory=session_factory)

    observations, last_updated = repository.fetch_series(coin="BTC", window_minutes=15)

    assert len(observations) == 2

    first, second = observations

    assert first.ts == aware_ts
    assert first.polarity == pytest.approx(0.1)
    assert first.confidence == pytest.approx(0.2)
    assert first.zscore == pytest.approx(0.3)
    assert first.aspects == ("macro",)

    assert second.ts == naive_ts.replace(tzinfo=UTC)
    assert second.polarity is None
    assert second.confidence == pytest.approx(0.5)
    assert second.zscore is None
    assert second.aspects == ()

    assert last_updated == second.ts


def test_create_sentiment_service_requires_postgres_dsn() -> None:
    settings = ApiSettings(
        env="dev",
        require_database=False,
        require_vector_store=False,
        postgres_dsn=None,
    )

    with pytest.raises(SettingsValidationError):
        create_sentiment_service(settings)


def test_create_sentiment_service_constructs_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = ApiSettings(
        env="dev",
        require_database=False,
        require_vector_store=False,
        postgres_dsn="postgresql+psycopg://user:pass@host/db",
    )

    engine = object()
    session_factory = object()

    def fake_create_engine(received_settings: ApiSettings) -> object:
        assert received_settings is settings
        return engine

    def fake_session_factory(received_engine: object) -> object:
        assert received_engine is engine
        return session_factory

    monkeypatch.setattr(
        "ragtrader_api.sentiment.database.create_engine", fake_create_engine
    )
    monkeypatch.setattr(
        "ragtrader_api.sentiment.database.session_factory", fake_session_factory
    )

    service = create_sentiment_service(settings)

    assert isinstance(service, SentimentService)
    repository = service._repository
    assert isinstance(repository, SqlAlchemySentimentRepository)
    assert repository._session_factory is session_factory
