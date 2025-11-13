"""End-to-end regression test for the demo analytics seed data."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")
pytest.importorskip("alembic")
pytest.importorskip("testcontainers")

from ragtrader_api.analytics import AnalyticsService
from ragtrader_api.db import database
from ragtrader_api.db.repositories.analytics import SqlAlchemyAnalyticsRepository
from ragtrader_api.db.seed_demo import load_demo_data
from ragtrader_api.settings import ApiSettings, get_settings
from tests.utils import PostgresTestContainer

_LATER_TS = datetime(2024, 1, 1, 1, tzinfo=UTC)
_BASE_TS = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresTestContainer]:
    with PostgresTestContainer() as container:
        yield container


@pytest.fixture()
def demo_service(
    postgres_container: PostgresTestContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[AnalyticsService]:
    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

    monkeypatch.setenv("RAGTRADER_API_POSTGRES_DSN", dsn)
    monkeypatch.setenv("RAGTRADER_API_REQUIRE_DATABASE", "1")
    monkeypatch.setenv("RAGTRADER_API_REQUIRE_VECTOR_STORE", "0")

    get_settings.cache_clear()
    try:
        load_demo_data()
    finally:
        get_settings.cache_clear()

    settings = ApiSettings(
        postgres_dsn=dsn,
        require_database=True,
        require_vector_store=False,
        analytics_pairs=("BTC-ETH", "ETH-SOL"),
        analytics_windows=("1h",),
        analytics_correlation_metric="pearson",
        analytics_max_age_minutes=120,
        analytics_fallback_minutes=240,
        analytics_granger_significance=0.05,
    )

    engine = database.create_engine(settings)
    session_factory = database.session_factory(engine)
    repository = SqlAlchemyAnalyticsRepository(session_factory)
    service = AnalyticsService(
        settings=settings,
        repository=repository,
        clock=lambda: _LATER_TS,
    )
    try:
        yield service
    finally:
        engine.dispose()


def test_demo_seed_regressions(demo_service: AnalyticsService) -> None:
    later_iso = _LATER_TS.isoformat()
    base_iso = _BASE_TS.isoformat()

    status, payload = demo_service.lead_lag()
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["last_updated"] == later_iso
    assert payload["freshness"] == {"age_minutes": pytest.approx(0.0)}

    lead_lag_data = sorted(
        payload["data"],
        key=lambda entry: (entry["leader"], entry["follower"], entry["window"]),
    )
    assert lead_lag_data == [
        {
            "leader": "BTC",
            "follower": "ETH",
            "window": "1h",
            "best_lag_minutes": 15,
            "strength": pytest.approx(0.8125),
            "computed_ts": later_iso,
        },
        {
            "leader": "BTC",
            "follower": "ETH",
            "window": "4h",
            "best_lag_minutes": 60,
            "strength": pytest.approx(0.7021),
            "computed_ts": base_iso,
        },
        {
            "leader": "ETH",
            "follower": "SOL",
            "window": "1h",
            "best_lag_minutes": 25,
            "strength": pytest.approx(0.6554),
            "computed_ts": later_iso,
        },
    ]

    status, payload = demo_service.correlation()
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["metric"] == "pearson"
    assert payload["last_updated"] == later_iso
    assert payload["freshness"] == {"age_minutes": pytest.approx(0.0)}

    correlation_data = sorted(
        payload["data"],
        key=lambda entry: (entry["pair"][0], entry["pair"][1], entry["window"]),
    )
    assert correlation_data == [
        {
            "pair": ["BTC", "ETH"],
            "window": "1h",
            "value": pytest.approx(0.8456),
            "computed_ts": later_iso,
        },
        {
            "pair": ["ETH", "SOL"],
            "window": "1h",
            "value": pytest.approx(-0.3789),
            "computed_ts": later_iso,
        },
    ]

    status, payload = demo_service.granger()
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["last_updated"] == later_iso
    assert payload["freshness"] == {"age_minutes": pytest.approx(0.0)}

    granger_data = sorted(
        payload["data"],
        key=lambda entry: (entry["source"], entry["target"], entry["window"]),
    )
    assert granger_data == [
        {
            "source": "BTC",
            "target": "ETH",
            "window": "1d",
            "direction": "y->x",
            "p_value": pytest.approx(0.2210),
            "reject_null": False,
            "computed_ts": base_iso,
        },
        {
            "source": "BTC",
            "target": "SOL",
            "window": "1d",
            "direction": "x->y",
            "p_value": pytest.approx(0.0125),
            "reject_null": True,
            "computed_ts": later_iso,
        },
        {
            "source": "ETH",
            "target": "SOL",
            "window": "1h",
            "direction": "x->y",
            "p_value": pytest.approx(0.0187),
            "reject_null": True,
            "computed_ts": later_iso,
        },
    ]

    status, payload = demo_service.influence_graph()
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["last_updated"] == later_iso
    assert payload["freshness"] == {"age_minutes": pytest.approx(0.0)}

    assert payload["graph"]["nodes"] == ["BTC", "ETH", "SOL"]
    assert payload["graph"]["edges"] == [
        {
            "source": "BTC",
            "target": "ETH",
            "window": "1h",
            "lag": 15,
            "correlation": pytest.approx(0.8456),
            "cross_correlation": pytest.approx(0.8125),
            "granger_p_value": None,
            "granger_reject_null": None,
            "weight": pytest.approx(0.82905),
            "computed_ts": later_iso,
        },
        {
            "source": "BTC",
            "target": "ETH",
            "window": "4h",
            "lag": 60,
            "correlation": None,
            "cross_correlation": pytest.approx(0.7021),
            "granger_p_value": None,
            "granger_reject_null": None,
            "weight": pytest.approx(0.7021),
            "computed_ts": base_iso,
        },
        {
            "source": "ETH",
            "target": "SOL",
            "window": "1h",
            "lag": 25,
            "correlation": pytest.approx(-0.3789),
            "cross_correlation": pytest.approx(0.6554),
            "granger_p_value": pytest.approx(0.0187),
            "granger_reject_null": True,
            "weight": pytest.approx(0.6718666667),
            "computed_ts": later_iso,
        },
    ]
