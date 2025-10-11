"""Integration tests for database engine and migrations."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ragtrader_api.db import database
from ragtrader_api.db.migrations import apply_migrations
from ragtrader_api.settings import ApiSettings
from tests.utils import PostgresTestContainer

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")
pytest.importorskip("alembic")


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
    assert inspector.has_table("articles")
    assert inspector.has_table("sentiments")

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

    article_columns = {col["name"] for col in inspector.get_columns("articles")}
    expected_article_columns = {
        "id",
        "source",
        "url",
        "title",
        "published_ts",
        "fetched_ts",
        "body_excerpt",
        "coins",
    }
    assert expected_article_columns.issubset(article_columns)

    sentiment_columns = {col["name"] for col in inspector.get_columns("sentiments")}
    expected_sentiment_columns = {
        "article_id",
        "coin",
        "polarity",
        "aspects",
        "confidence",
        "ts",
        "zscore_window",
        "zscore",
    }
    assert expected_sentiment_columns.issubset(sentiment_columns)

    sentiment_fks = inspector.get_foreign_keys("sentiments")
    assert any(
        fk["referred_table"] == "articles"
        and fk.get("constrained_columns") == ["article_id"]
        and fk.get("referred_columns") == ["id"]
        for fk in sentiment_fks
    ), "sentiments.article_id should reference articles.id"

    article_indexes = inspector.get_indexes("articles")
    assert any(
        index.get("unique")
        and (
            "url" in (index.get("column_names") or [])
            or "url_hash" in (index.get("column_names") or [])
            or "url_title_hash" in (index.get("column_names") or [])
        )
        for index in article_indexes
    ), "Expected a unique index on articles URL information"

    sentiment_indexes = inspector.get_indexes("sentiments")
    assert any(
        (
            "coin" in (index.get("column_names") or [])
            and "zscore_window" in (index.get("column_names") or [])
        )
        and (
            "ts" in (index.get("column_names") or [])
            or index.get("column_names") == ["coin", "zscore_window"]
        )
        for index in sentiment_indexes
    ), "Expected an index to support sentiment window lookups"
