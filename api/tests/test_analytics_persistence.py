"""Integration tests covering analytics schema and repositories."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ragtrader_api.db import database
from ragtrader_api.db.migrations import apply_migrations
from ragtrader_api.db.models import Instrument
from ragtrader_api.db.repositories.analytics import (
    FeatureRecord,
    GrangerTestRecord,
    LeadLagRecord,
    SqlAlchemyAnalyticsRepository,
)
from ragtrader_api.settings import ApiSettings
from tests.utils import PostgresTestContainer

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")
pytest.importorskip("alembic")
pytest.importorskip("testcontainers")


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresTestContainer]:
    with PostgresTestContainer() as container:
        yield container


@pytest.fixture()
def engine(postgres_container: PostgresTestContainer) -> Iterator[Engine]:
    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    settings = ApiSettings(
        postgres_dsn=dsn,
        require_database=True,
        require_vector_store=False,
    )
    engine = database.create_engine(settings)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def migrated_engine(engine: Engine) -> Engine:
    apply_migrations(engine)
    return engine


@pytest.fixture()
def analytics_repository(migrated_engine: Engine) -> SqlAlchemyAnalyticsRepository:
    session_factory = database.session_factory(migrated_engine)
    return SqlAlchemyAnalyticsRepository(session_factory)


@pytest.fixture()
def seeded_instruments(migrated_engine: Engine) -> None:
    symbols = (
        ("BTC", "Bitcoin"),
        ("ETH", "Ethereum"),
        ("SOL", "Solana"),
    )
    with migrated_engine.begin() as conn:
        for symbol, name in symbols:
            conn.execute(
                text(
                    "INSERT INTO instruments (symbol, name) VALUES (:symbol, :name)"
                    " ON CONFLICT (symbol) DO NOTHING"
                ),
                {"symbol": symbol, "name": name},
            )


def test_migrations_create_analytics_tables(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)

    assert inspector.has_table("features")
    assert inspector.has_table("lead_lag")
    assert inspector.has_table("granger_tests")

    feature_columns = {column["name"] for column in inspector.get_columns("features")}
    assert feature_columns == {"symbol", "feature_name", "ts", "value"}

    feature_indexes = inspector.get_indexes("features")
    assert any(
        index.get("name") == "ix_features_symbol_feature_name_ts"
        for index in feature_indexes
    )

    lead_lag_columns = {column["name"] for column in inspector.get_columns("lead_lag")}
    assert lead_lag_columns == {
        "leader",
        "follower",
        "window",
        "computed_ts",
        "best_lag_min",
        "strength",
    }

    lead_lag_indexes = inspector.get_indexes("lead_lag")
    assert any(
        index.get("name") == "ix_lead_lag_pair_window_ts" for index in lead_lag_indexes
    )

    lead_lag_fks = inspector.get_foreign_keys("lead_lag")
    assert {tuple(fk.get("constrained_columns", ())) for fk in lead_lag_fks} == {
        ("leader",),
        ("follower",),
    }

    granger_columns = {
        column["name"] for column in inspector.get_columns("granger_tests")
    }
    assert granger_columns == {
        "x_symbol",
        "y_symbol",
        "window",
        "computed_ts",
        "p_value",
        "direction",
    }

    granger_indexes = inspector.get_indexes("granger_tests")
    assert any(
        index.get("name") == "ix_granger_tests_pair_window_ts"
        for index in granger_indexes
    )

    granger_fks = inspector.get_foreign_keys("granger_tests")
    assert {tuple(fk.get("constrained_columns", ())) for fk in granger_fks} == {
        ("x_symbol",),
        ("y_symbol",),
    }


def test_repository_round_trip(
    migrated_engine: Engine,
    analytics_repository: SqlAlchemyAnalyticsRepository,
    seeded_instruments: None,
) -> None:
    base_ts = datetime(2024, 1, 1, tzinfo=UTC)
    later_ts = base_ts + timedelta(hours=1)

    feature_records = [
        FeatureRecord(
            symbol="BTC",
            feature_name="rsi_14",
            ts=base_ts,
            value=Decimal("54.3210"),
        ),
        FeatureRecord(
            symbol="BTC",
            feature_name="rsi_14",
            ts=later_ts,
            value=Decimal("48.7654"),
        ),
    ]
    analytics_repository.upsert_features(feature_records)
    stored_features = analytics_repository.list_features(
        symbol="BTC", feature_name="rsi_14"
    )
    assert stored_features == feature_records
    assert (
        analytics_repository.list_features(symbol="BTC", feature_name="rsi_14", limit=1)
        == feature_records[:1]
    )

    lead_lag_records = [
        LeadLagRecord(
            leader="BTC",
            follower="ETH",
            window="1h",
            best_lag_min=15,
            strength=Decimal("0.8125"),
            computed_ts=later_ts,
        ),
        LeadLagRecord(
            leader="BTC",
            follower="ETH",
            window="1h",
            best_lag_min=5,
            strength=Decimal("0.6321"),
            computed_ts=base_ts,
        ),
    ]
    analytics_repository.upsert_lead_lag(lead_lag_records)
    stored_lead_lag = analytics_repository.list_lead_lag(
        leader="BTC", follower="ETH", window="1h"
    )
    assert [record.computed_ts for record in stored_lead_lag] == [later_ts, base_ts]
    assert stored_lead_lag[0].strength == Decimal("0.8125")

    granger_records = [
        GrangerTestRecord(
            x_symbol="BTC",
            y_symbol="SOL",
            window="1d",
            p_value=Decimal("0.012500"),
            direction="x->y",
            computed_ts=later_ts,
        ),
        GrangerTestRecord(
            x_symbol="ETH",
            y_symbol="BTC",
            window="1d",
            p_value=Decimal("0.221000"),
            direction="y->x",
            computed_ts=base_ts,
        ),
    ]
    analytics_repository.upsert_granger_tests(granger_records)
    stored_granger = analytics_repository.list_granger_tests(
        x_symbol="BTC", y_symbol="SOL"
    )
    assert stored_granger == granger_records[:1]

    directional = analytics_repository.list_granger_tests(direction="y->x")
    assert directional == [granger_records[1]]

    # ensure feature FK relationship allows ORM joins
    with database.session_factory(migrated_engine)() as session:
        instrument = session.get(Instrument, "BTC")
        assert instrument is not None
        assert {feature.ts for feature in instrument.features} == {base_ts, later_ts}
