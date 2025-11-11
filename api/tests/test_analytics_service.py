"""Tests for the analytics API handlers and service orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from ragtrader_api.analytics import AnalyticsService
from ragtrader_api.app import Response, create_app
from ragtrader_api.db.repositories.analytics import (
    FeatureRecord,
    GrangerTestRecord,
    LeadLagRecord,
)
from ragtrader_api.settings import ApiSettings, SettingsValidationError


class FakeAnalyticsRepository:
    """In-memory analytics repository used for handler tests."""

    def __init__(
        self,
        *,
        features: dict[tuple[str, str], list[FeatureRecord]] | None = None,
        lead_lag: list[LeadLagRecord] | None = None,
        granger: list[GrangerTestRecord] | None = None,
    ) -> None:
        self._features = features or {}
        self._lead_lag = lead_lag or []
        self._granger = granger or []

        self.feature_calls: list[tuple[str, str, int | None]] = []
        self.lead_lag_calls: list[dict[str, Any]] = []
        self.granger_calls: list[dict[str, Any]] = []

    def list_features(
        self,
        *,
        symbol: str,
        feature_name: str,
        limit: int | None = None,
    ) -> list[FeatureRecord]:
        self.feature_calls.append((symbol, feature_name, limit))
        key = (symbol, feature_name)
        return list(self._features.get(key, []))

    def list_lead_lag(
        self,
        *,
        leader: str | None = None,
        follower: str | None = None,
        window: str | None = None,
        limit: int | None = None,
    ) -> list[LeadLagRecord]:
        self.lead_lag_calls.append(
            {"leader": leader, "follower": follower, "window": window, "limit": limit}
        )
        return list(self._lead_lag)

    def list_granger_tests(
        self,
        *,
        x_symbol: str | None = None,
        y_symbol: str | None = None,
        window: str | None = None,
        direction: str | None = None,
        limit: int | None = None,
    ) -> list[GrangerTestRecord]:
        self.granger_calls.append(
            {
                "x_symbol": x_symbol,
                "y_symbol": y_symbol,
                "window": window,
                "direction": direction,
                "limit": limit,
            }
        )
        return list(self._granger)


@pytest.fixture()
def fixed_now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def api_settings() -> ApiSettings:
    return ApiSettings(
        env="dev",
        require_database=False,
        require_vector_store=False,
        analytics_pairs=("BTC-ETH", "ETH-SOL"),
        analytics_windows=("1h",),
        analytics_correlation_metric="pearson",
        analytics_max_age_minutes=60,
        analytics_fallback_minutes=180,
        analytics_granger_significance=0.05,
    )


def _build_service(
    settings: ApiSettings,
    repository: FakeAnalyticsRepository,
    *,
    now: datetime,
) -> AnalyticsService:
    return AnalyticsService(settings=settings, repository=repository, clock=lambda: now)


def test_lead_lag_handler_serializes_payload(
    monkeypatch, api_settings, fixed_now
) -> None:
    base_ts = fixed_now - timedelta(minutes=45)
    recent_ts = fixed_now - timedelta(minutes=15)

    repository = FakeAnalyticsRepository(
        lead_lag=[
            LeadLagRecord(
                leader="BTC",
                follower="ETH",
                window="1h",
                best_lag_min=10,
                strength=Decimal("0.8125"),
                computed_ts=base_ts,
            ),
            LeadLagRecord(
                leader="ETH",
                follower="SOL",
                window="1h",
                best_lag_min=5,
                strength=Decimal("0.5321"),
                computed_ts=recent_ts,
            ),
        ]
    )

    service = _build_service(api_settings, repository, now=fixed_now)
    monkeypatch.setattr(
        "ragtrader_api.app.create_analytics_service",
        lambda settings: service,
    )

    app = create_app(settings=api_settings)
    response = app.dispatch("GET", "/analytics/leadlag")

    assert isinstance(response, Response)
    assert response.status_code == 200

    payload = response.json
    assert payload["status"] == "ok"
    assert payload["last_updated"] == recent_ts.isoformat()
    assert payload["freshness"]["age_minutes"] == pytest.approx(15.0, rel=1e-6)

    strengths = {item["leader"]: item["strength"] for item in payload["data"]}
    assert strengths["BTC"] == pytest.approx(0.8125)
    assert strengths["ETH"] == pytest.approx(0.5321)

    computed_ts = {item["leader"]: item["computed_ts"] for item in payload["data"]}
    assert computed_ts["BTC"] == base_ts.isoformat()
    assert computed_ts["ETH"] == recent_ts.isoformat()


def test_correlation_handler_formats_values(
    monkeypatch, api_settings, fixed_now
) -> None:
    feature_ts = fixed_now - timedelta(minutes=5)
    repository = FakeAnalyticsRepository(
        features={
            (
                "BTC-ETH",
                "correlation:pearson:1h",
            ): [
                FeatureRecord(
                    symbol="BTC-ETH",
                    feature_name="correlation:pearson:1h",
                    ts=feature_ts,
                    value=Decimal("0.812500"),
                )
            ],
            (
                "ETH-SOL",
                "correlation:pearson:1h",
            ): [
                FeatureRecord(
                    symbol="ETH-SOL",
                    feature_name="correlation:pearson:1h",
                    ts=feature_ts,
                    value=Decimal("-0.412345"),
                )
            ],
        }
    )

    service = _build_service(api_settings, repository, now=fixed_now)
    monkeypatch.setattr(
        "ragtrader_api.app.create_analytics_service",
        lambda settings: service,
    )

    app = create_app(settings=api_settings)
    response = app.dispatch("GET", "/analytics/correlation")

    assert response.status_code == 200
    payload = response.json

    assert payload["status"] == "ok"
    assert payload["last_updated"] == feature_ts.isoformat()
    assert payload["freshness"]["age_minutes"] == pytest.approx(5.0, rel=1e-6)

    pairs = {tuple(item["pair"]): item for item in payload["data"]}
    assert pairs[("BTC", "ETH")]["value"] == pytest.approx(0.8125)
    assert pairs[("ETH", "SOL")]["value"] == pytest.approx(-0.412345)
    assert repository.feature_calls == [
        ("BTC-ETH", "correlation:pearson:1h", None),
        ("ETH-SOL", "correlation:pearson:1h", None),
    ]


def test_granger_handler_errors_when_results_expire(
    monkeypatch, api_settings, fixed_now
) -> None:
    expired_ts = fixed_now - timedelta(minutes=480)
    repository = FakeAnalyticsRepository(
        granger=[
            GrangerTestRecord(
                x_symbol="BTC",
                y_symbol="ETH",
                window="1h",
                p_value=Decimal("0.150"),
                direction="x->y",
                computed_ts=expired_ts,
            )
        ]
    )

    service = _build_service(api_settings, repository, now=fixed_now)
    monkeypatch.setattr(
        "ragtrader_api.app.create_analytics_service",
        lambda settings: service,
    )

    app = create_app(settings=api_settings)
    response = app.dispatch("GET", "/analytics/granger")

    assert response.status_code == 503
    payload = response.json

    assert payload["status"] == "error"
    message = payload.get("message", "").lower()
    assert "fallback" in message
    assert "cannot be served" in message
    assert payload["freshness"]["age_minutes"] == pytest.approx(480.0, rel=1e-6)


def test_influence_graph_handler_marks_stale_and_builds_edges(
    monkeypatch, api_settings, fixed_now
) -> None:
    stale_ts = fixed_now - timedelta(minutes=120)
    repository = FakeAnalyticsRepository(
        lead_lag=[
            LeadLagRecord(
                leader="BTC",
                follower="ETH",
                window="1h",
                best_lag_min=20,
                strength=Decimal("0.7500"),
                computed_ts=stale_ts,
            )
        ],
        features={
            (
                "BTC-ETH",
                "correlation:pearson:1h",
            ): [
                FeatureRecord(
                    symbol="BTC-ETH",
                    feature_name="correlation:pearson:1h",
                    ts=stale_ts,
                    value=Decimal("0.8000"),
                )
            ]
        },
        granger=[
            GrangerTestRecord(
                x_symbol="BTC",
                y_symbol="ETH",
                window="1h",
                p_value=Decimal("0.020"),
                direction="x->y",
                computed_ts=stale_ts,
            )
        ],
    )

    service = _build_service(api_settings, repository, now=fixed_now)
    monkeypatch.setattr(
        "ragtrader_api.app.create_analytics_service",
        lambda settings: service,
    )

    app = create_app(settings=api_settings)
    response = app.dispatch("GET", "/analytics/influence-graph")

    assert response.status_code == 200
    payload = response.json

    assert payload["status"] == "stale"
    assert "stale" in payload.get("message", "").lower()
    assert payload["last_updated"] == stale_ts.isoformat()
    assert payload["freshness"]["age_minutes"] == pytest.approx(120.0, rel=1e-6)

    graph = payload.get("graph", {})
    assert graph.get("nodes") == ["BTC", "ETH"]
    assert len(graph.get("edges", [])) == 1

    edge = graph["edges"][0]
    assert edge["correlation"] == pytest.approx(0.8)
    assert edge["cross_correlation"] == pytest.approx(0.75)
    assert edge["granger_p_value"] == pytest.approx(0.02)
    assert edge["granger_reject_null"] is True
    assert edge["weight"] == pytest.approx((0.8 + 0.75 + 0.98) / 3, rel=1e-6)


@pytest.mark.parametrize(
    "path",
    (
        "/analytics/leadlag",
        "/analytics/correlation",
        "/analytics/granger",
        "/analytics/influence-graph",
    ),
)
def test_analytics_handlers_surface_settings_errors(
    monkeypatch, api_settings, path
) -> None:
    message = "Postgres DSN is required to serve analytics endpoints."

    api_settings.require_database = True
    api_settings.postgres_dsn = None

    def _raise(_: ApiSettings) -> AnalyticsService:  # pragma: no cover - never returns
        raise SettingsValidationError(message)

    monkeypatch.setattr("ragtrader_api.app.create_analytics_service", _raise)

    app = create_app(settings=api_settings)
    response = app.dispatch("GET", path)

    assert isinstance(response, Response)
    assert response.status_code == 500

    payload = response.json
    assert payload["status"] == "error"
    assert payload["message"] == message


@pytest.mark.parametrize(
    "path",
    (
        "/analytics/leadlag",
        "/analytics/correlation",
        "/analytics/granger",
        "/analytics/influence-graph",
    ),
)
def test_analytics_handlers_return_error_when_no_data(
    monkeypatch: pytest.MonkeyPatch,
    api_settings: ApiSettings,
    fixed_now: datetime,
    path: str,
) -> None:
    repository = FakeAnalyticsRepository()
    service = _build_service(api_settings, repository, now=fixed_now)

    monkeypatch.setattr(
        "ragtrader_api.app.create_analytics_service",
        lambda settings: service,
    )

    app = create_app(settings=api_settings)
    response = app.dispatch("GET", path)

    assert response.status_code == 503
    payload = response.json
    assert payload["status"] == "error"
    assert payload.get("freshness", {}).get("age_minutes") is None
    assert "unavailable" in payload.get("message", "").lower()
