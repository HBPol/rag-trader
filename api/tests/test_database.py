"""Integration tests for database engine and migrations."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")
pytest.importorskip("alembic")

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ragtrader_api.db import database
from ragtrader_api.db.migrations import apply_migrations
from ragtrader_api.settings import ApiSettings
from tests.utils import PostgresTestContainer


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresTestContainer]:
    """Spin up a disposable Postgres instance for the test session."""

    with PostgresTestContainer() as container:
        yield container


@pytest.fixture()
def engine(postgres_container: PostgresTestContainer) -> Iterator[Engine]:
    """Create a SQLAlchemy engine bound to the disposable database."""

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


def test_engine_executes_simple_query(engine: Engine) -> None:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar_one()
    assert result == 1


def test_migrations_create_expected_tables(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    assert inspector.has_table("instruments")
    assert inspector.has_table("ohlcv")

    ohlcv_columns = {col["name"] for col in inspector.get_columns("ohlcv")}
    expected_columns = {
        "symbol",
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "interval",
        "created_at",
        "updated_at",
    }
    assert expected_columns.issubset(ohlcv_columns)
