"""Integration tests for the forthcoming content repository."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ragtrader_api.db.migrations import apply_migrations
from ragtrader_pipelines.content import (
    NormalizedArticleRecord,
    SentimentRecord,
    SqlAlchemyContentRepository,
)

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


def test_upsert_article_deduplicates_article_and_appends_sentiments(
    migrated_engine: Engine,
) -> None:
    """Upserting the same article should be idempotent while appending sentiments."""

    repository = SqlAlchemyContentRepository(migrated_engine)

    article = NormalizedArticleRecord(
        source="coindesk",
        url="https://www.coindesk.com/markets/bitcoin-rally/",
        title="Bitcoin Rally Charges Ahead",
        excerpt="Bitcoin pushes above $60K again.",
        coins=["BTC", "ETH"],
        published_ts=dt.datetime(2024, 5, 1, 16, 34, 56, tzinfo=dt.UTC),
    )

    initial_sentiments = [
        SentimentRecord(
            coin="BTC",
            polarity=Decimal("0.42000"),
            aspects=["price", "momentum"],
            confidence=Decimal("0.91000"),
            ts=dt.datetime(2024, 5, 1, 16, 40, tzinfo=dt.UTC),
            zscore_window=24,
            zscore=Decimal("1.23000"),
        ),
        SentimentRecord(
            coin="ETH",
            polarity=Decimal("0.31000"),
            aspects=["network", "defi"],
            confidence=Decimal("0.86000"),
            ts=dt.datetime(2024, 5, 1, 16, 50, tzinfo=dt.UTC),
            zscore_window=24,
            zscore=Decimal("0.98000"),
        ),
    ]

    repository.upsert_article_with_sentiments(
        article=article,
        sentiments=initial_sentiments,
    )

    with migrated_engine.connect() as conn:
        article_rows = (
            conn.execute(
                text(
                    "SELECT id, source, url, title, body_excerpt, coins, published_ts "
                    "FROM articles"
                )
            )
            .mappings()
            .all()
        )
        sentiment_rows = (
            conn.execute(
                text(
                    "SELECT article_id, coin, polarity, aspects, confidence, ts, "
                    "zscore_window, zscore FROM sentiments"
                )
            )
            .mappings()
            .all()
        )

    assert len(article_rows) == 1
    stored_article = article_rows[0]
    assert stored_article["source"] == article.source
    assert stored_article["url"] == article.url
    assert stored_article["title"] == article.title
    assert stored_article["body_excerpt"] == article.excerpt
    assert stored_article["coins"] == article.coins
    assert stored_article["published_ts"] == article.published_ts

    assert len(sentiment_rows) == 2
    assert {row["coin"] for row in sentiment_rows} == {"BTC", "ETH"}
    assert all(row["article_id"] == stored_article["id"] for row in sentiment_rows)

    follow_up_sentiments = [
        SentimentRecord(
            coin="BTC",
            polarity=Decimal("0.35000"),
            aspects=["derivatives"],
            confidence=Decimal("0.87000"),
            ts=dt.datetime(2024, 5, 1, 18, 0, tzinfo=dt.UTC),
            zscore_window=6,
            zscore=Decimal("0.75000"),
        ),
        SentimentRecord(
            coin="SOL",
            polarity=Decimal("0.28000"),
            aspects=["nft", "ecosystem"],
            confidence=Decimal("0.83000"),
            ts=dt.datetime(2024, 5, 1, 18, 5, tzinfo=dt.UTC),
            zscore_window=24,
            zscore=Decimal("1.05000"),
        ),
    ]

    repository.upsert_article_with_sentiments(
        article=article,
        sentiments=follow_up_sentiments,
    )

    with migrated_engine.connect() as conn:
        deduped_articles = (
            conn.execute(
                text(
                    "SELECT id, source, url, title, body_excerpt, coins, published_ts "
                    "FROM articles"
                )
            )
            .mappings()
            .all()
        )
        all_sentiments = (
            conn.execute(
                text(
                    "SELECT article_id, coin, polarity, aspects, confidence, ts, "
                    "zscore_window, zscore FROM sentiments ORDER BY coin, zscore_window"
                )
            )
            .mappings()
            .all()
        )

    assert len(deduped_articles) == 1
    assert deduped_articles[0]["id"] == stored_article["id"]

    combos = {(row["coin"], row["zscore_window"]) for row in all_sentiments}
    assert combos == {("BTC", 24), ("ETH", 24), ("BTC", 6), ("SOL", 24)}
    assert all(row["article_id"] == stored_article["id"] for row in all_sentiments)
