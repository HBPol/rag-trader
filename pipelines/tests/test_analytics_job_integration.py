"""Integration test for the analytics job writing to Postgres."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest
from pipelines.tests import get_analytics_fixture_path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ragtrader_api.db.migrations import apply_migrations
from ragtrader_api.db.models import Article, Instrument, Ohlcv, Sentiment
from ragtrader_api.db.repositories.analytics import SqlAlchemyAnalyticsRepository
from ragtrader_pipelines.analytics import (
    best_cross_correlation,
    rolling_pearson,
    rolling_spearman,
    run_granger_causality,
)
from ragtrader_pipelines.analytics_job import (
    AnalyticsJob,
    SqlAlchemyOhlcvRepository,
    SqlAlchemySentimentRepository,
    register_analytics_job,
)
from ragtrader_pipelines.registry import PipelineRegistry

pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")
pytest.importorskip("alembic")
pytest.importorskip("testcontainers")
pytest.importorskip("statsmodels")


@pytest.fixture(scope="module")
def migrated_engine() -> Iterator[Engine]:
    """Provision Postgres via testcontainers and apply migrations."""

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


@pytest.fixture()
def session(migrated_engine: Engine) -> Iterator[Session]:
    maker = sessionmaker(bind=migrated_engine, expire_on_commit=False, future=True)
    with maker() as session:
        yield session


def _load_expanded_fixture() -> pd.DataFrame:
    base = pd.read_csv(get_analytics_fixture_path("csv"), parse_dates=["timestamp"])
    chunks: list[pd.DataFrame] = []
    hours = len(base)
    for multiplier in range(6):
        chunk = base.copy()
        offset = pd.Timedelta(hours=hours * multiplier)
        chunk["timestamp"] = chunk["timestamp"] + offset
        bump = float(multiplier * 10)
        for column in ("btc_open", "btc_high", "btc_low", "btc_close"):
            chunk[column] = chunk[column] + bump
        for column in ("eth_open", "eth_high", "eth_low", "eth_close"):
            chunk[column] = chunk[column] + bump / 2
        chunks.append(chunk)
    return pd.concat(chunks, ignore_index=True)


def _seed_database(session: Session, data: pd.DataFrame) -> None:
    session.add_all(
        [
            Instrument(symbol="BTC", name="Bitcoin"),
            Instrument(symbol="ETH", name="Ethereum"),
        ]
    )
    session.flush()

    article_counter = 0
    for row in data.itertuples(index=False):
        timestamp = row.timestamp
        btc_fields = {
            "open": row.btc_open,
            "high": row.btc_high,
            "low": row.btc_low,
            "close": row.btc_close,
            "volume": row.btc_volume,
        }
        eth_fields = {
            "open": row.eth_open,
            "high": row.eth_high,
            "low": row.eth_low,
            "close": row.eth_close,
            "volume": row.eth_volume,
        }
        session.add(
            Ohlcv(
                symbol="BTC",
                interval="1h",
                ts=timestamp.to_pydatetime(),
                **{key: Decimal(str(value)) for key, value in btc_fields.items()},
            )
        )
        session.add(
            Ohlcv(
                symbol="ETH",
                interval="1h",
                ts=timestamp.to_pydatetime(),
                **{key: Decimal(str(value)) for key, value in eth_fields.items()},
            )
        )

        article_counter += 1
        article = Article(
            source="fixture",
            url=f"https://example.com/{article_counter}",
            title=f"Fixture article {article_counter}",
            body_excerpt="seed",
            coins=["BTC", "ETH"],
            published_ts=timestamp.to_pydatetime(),
        )
        session.add(article)
        session.flush()
        for coin, zscore in (
            ("BTC", row.btc_sentiment_zscore),
            ("ETH", row.eth_sentiment_zscore),
        ):
            session.add(
                Sentiment(
                    article_id=article.id,
                    coin=coin,
                    polarity=Decimal("0"),
                    confidence=Decimal("1"),
                    aspects=[],
                    ts=timestamp.to_pydatetime(),
                    zscore_window=6,
                    zscore=Decimal(str(zscore)),
                )
            )
    session.commit()


def _compute_expected_correlations(data: pd.DataFrame) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    for coin in ("btc", "eth"):
        closes = pd.Series(
            data[f"{coin}_close"].astype(float).values, index=data["timestamp"]
        )
        sentiments = pd.Series(
            data[f"{coin}_sentiment_zscore"].astype(float).values,
            index=data["timestamp"],
        )
        returns = (
            np.log(closes.resample("1h", label="right", closed="right").last())
            .diff()
            .dropna()
        )
        aggregated_sentiment = (
            sentiments.resample("1h", label="right", closed="right").mean().dropna()
        )
        aligned_returns, aligned_sentiment = returns.align(
            aggregated_sentiment, join="inner"
        )
        pearson = rolling_pearson(
            aligned_returns, aligned_sentiment, window=3, min_periods=3
        )
        spearman = rolling_spearman(
            aligned_returns, aligned_sentiment, window=3, min_periods=3
        )
        results[coin.upper()] = {
            "pearson": float(pearson.dropna().iloc[-1]),
            "spearman": float(spearman.dropna().iloc[-1]),
        }
    return results


def _compute_expected_cross_metrics(
    data: pd.DataFrame,
) -> tuple[dict[tuple[str, str], tuple[int, float]], dict[tuple[str, str], float]]:
    btc = pd.Series(data["btc_close"].astype(float).values, index=data["timestamp"])
    eth = pd.Series(data["eth_close"].astype(float).values, index=data["timestamp"])
    btc_returns = (
        np.log(btc.resample("1h", label="right", closed="right").last()).diff().dropna()
    )
    eth_returns = (
        np.log(eth.resample("1h", label="right", closed="right").last()).diff().dropna()
    )
    lag_btc_eth = best_cross_correlation(btc_returns, eth_returns, max_lag=1)
    lag_eth_btc = best_cross_correlation(eth_returns, btc_returns, max_lag=1)
    summary = run_granger_causality(btc_returns, eth_returns, max_lag=1)
    if lag_btc_eth is None or lag_eth_btc is None:
        raise AssertionError("Expected cross-correlation results in both directions")
    lead_lag = {
        ("BTC", "ETH"): lag_btc_eth,
        ("ETH", "BTC"): lag_eth_btc,
    }
    granger = {
        ("BTC", "ETH"): summary.leader_to_follower.p_value,
        ("ETH", "BTC"): summary.follower_to_leader.p_value,
    }
    return lead_lag, granger


def test_analytics_job_populates_tables(
    session: Session, migrated_engine: Engine
) -> None:
    data = _load_expanded_fixture()
    _seed_database(session, data)

    session_factory = sessionmaker(
        bind=migrated_engine, expire_on_commit=False, future=True
    )
    price_repo = SqlAlchemyOhlcvRepository(session_factory)
    sentiment_repo = SqlAlchemySentimentRepository(session_factory)
    analytics_repo = SqlAlchemyAnalyticsRepository(session_factory)
    job = AnalyticsJob(
        price_repository=price_repo,
        sentiment_repository=sentiment_repo,
        analytics_repository=analytics_repo,
        clock=lambda: datetime(2024, 1, 2, tzinfo=UTC),
    )
    start = data["timestamp"].min().to_pydatetime()
    end = data["timestamp"].max().to_pydatetime()
    job.run(
        symbols=["BTC", "ETH"],
        start=start,
        end=end,
        windows=["1h"],
        price_interval="1h",
        zscore_window=6,
        max_lag_minutes=60,
    )

    expected_correlations = _compute_expected_correlations(data)
    repository = SqlAlchemyAnalyticsRepository(session_factory)
    btc_features = repository.list_features(
        symbol="BTC", feature_name="correlation:return_vs_sentiment:pearson:1h"
    )
    assert btc_features
    assert float(btc_features[-1].value) == pytest.approx(
        expected_correlations["BTC"]["pearson"], rel=1e-6
    )

    btc_spearman = repository.list_features(
        symbol="BTC", feature_name="correlation:return_vs_sentiment:spearman:1h"
    )
    assert btc_spearman
    assert float(btc_spearman[-1].value) == pytest.approx(
        expected_correlations["BTC"]["spearman"], rel=1e-6
    )

    eth_features = repository.list_features(
        symbol="ETH", feature_name="correlation:return_vs_sentiment:pearson:1h"
    )
    assert eth_features
    assert float(eth_features[-1].value) == pytest.approx(
        expected_correlations["ETH"]["pearson"], rel=1e-6
    )

    lead_lag = repository.list_lead_lag()
    assert len(lead_lag) >= 2
    expected_lead_lag, expected_granger = _compute_expected_cross_metrics(data)
    assert lead_lag[0].window == "1h"

    lead_lag_by_pair = {(item.leader, item.follower): item for item in lead_lag}
    assert set(lead_lag_by_pair) >= expected_lead_lag.keys()
    for direction, (lag_steps, strength) in expected_lead_lag.items():
        record = lead_lag_by_pair[direction]
        expected_minutes = lag_steps * 60  # 1h window
        assert record.best_lag_min == expected_minutes
        assert float(record.strength) == pytest.approx(strength, rel=1e-6)

    granger = repository.list_granger_tests()
    assert len(granger) >= 2
    p_values = {(item.x_symbol, item.y_symbol): float(item.p_value) for item in granger}
    assert set(p_values) >= expected_granger.keys()
    for direction, expected in expected_granger.items():
        assert p_values[direction] == pytest.approx(expected, rel=1e-6)

    registry = PipelineRegistry()
    register_analytics_job(
        registry,
        database_url=str(migrated_engine.url),
        symbols=["BTC", "ETH"],
        windows=["1h"],
        lookback=timedelta(hours=1),
        price_interval="1h",
        sentiment_window=6,
        max_lag_minutes=60,
    )
    assert "analytics.job" in registry
