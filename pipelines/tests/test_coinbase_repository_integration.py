"""Integration test for the Coinbase candle repository."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ragtrader_api.db.migrations import apply_migrations
from ragtrader_pipelines.coinbase import OhlcvRecord, SqlAlchemyCandleRepository

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")
pytest.importorskip("alembic")
pytest.importorskip("testcontainers")


@pytest.fixture(scope="module")
def migrated_engine() -> Engine:
    """Provision a temporary Postgres database with migrations applied."""

    from api.tests.utils import PostgresTestContainer

    with PostgresTestContainer() as container:
        raw_url = container.get_connection_url()
        dsn = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
        engine = create_engine(dsn, future=True)
        apply_migrations(engine)
        try:
            yield engine
        finally:
            engine.dispose()


def test_upsert_many_seeds_instruments_and_candles(migrated_engine: Engine) -> None:
    """`upsert_many` should create instruments and insert OHLCV rows atomically."""

    repository = SqlAlchemyCandleRepository(migrated_engine)
    records = [
        OhlcvRecord(
            symbol="BTC",
            interval="1h",
            ts=datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
            open=Decimal("100.0"),
            high=Decimal("110.0"),
            low=Decimal("95.0"),
            close=Decimal("105.0"),
            volume=Decimal("12.34"),
        )
    ]

    repository.upsert_many(records)

    with migrated_engine.connect() as conn:
        instrument_rows = (
            conn.execute(
                text("SELECT symbol, name FROM instruments WHERE symbol = :symbol"),
                {"symbol": "BTC"},
            )
            .mappings()
            .all()
        )
        ohlcv_rows = (
            conn.execute(
                text(
                    "SELECT symbol, interval, ts, open, high, low, close, volume "
                    "FROM ohlcv WHERE symbol = :symbol"
                ),
                {"symbol": "BTC"},
            )
            .mappings()
            .all()
        )

    assert instrument_rows == [{"symbol": "BTC", "name": "BTC"}]
    assert len(ohlcv_rows) == 1
    candle = ohlcv_rows[0]
    assert candle["interval"] == "1h"
    assert candle["ts"] == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert candle["open"] == Decimal("100.0")
    assert candle["high"] == Decimal("110.0")
    assert candle["low"] == Decimal("95.0")
    assert candle["close"] == Decimal("105.0")
    assert candle["volume"] == Decimal("12.34")
