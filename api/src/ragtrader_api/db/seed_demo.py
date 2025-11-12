"""Utility for loading demo analytics data into the database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..settings import get_settings
from . import database
from .migrations import apply_migrations
from .repositories.analytics import (
    FeatureRecord,
    GrangerTestRecord,
    LeadLagRecord,
    SqlAlchemyAnalyticsRepository,
)


def _build_repository() -> tuple[SqlAlchemyAnalyticsRepository, Engine]:
    settings = get_settings()
    engine = database.create_engine(settings)
    apply_migrations(engine)
    session_factory = database.session_factory(engine)
    repository = SqlAlchemyAnalyticsRepository(session_factory)
    return repository, engine


def load_demo_data() -> None:
    """Populate deterministic demo analytics rows for local development."""

    repository, engine = _build_repository()
    try:
        with engine.begin() as conn:
            symbols = (
                ("BTC", "Bitcoin"),
                ("ETH", "Ethereum"),
                ("SOL", "Solana"),
                ("BTC-ETH", "BTC/ETH Pair"),
                ("ETH-SOL", "ETH/SOL Pair"),
            )
            for symbol, name in symbols:
                conn.execute(
                    text(
                        "INSERT INTO instruments (symbol, name) VALUES (:symbol, :name)"
                        " ON CONFLICT (symbol) DO NOTHING"
                    ),
                    {"symbol": symbol, "name": name},
                )

        base_ts = datetime(2024, 1, 1, tzinfo=UTC)
        later_ts = base_ts + timedelta(hours=1)

        repository.upsert_features(
            [
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
                FeatureRecord(
                    symbol="BTC-ETH",
                    feature_name="correlation:pearson:1h",
                    ts=later_ts,
                    value=Decimal("0.8456"),
                ),
                FeatureRecord(
                    symbol="ETH-SOL",
                    feature_name="correlation:pearson:1h",
                    ts=later_ts,
                    value=Decimal("-0.3789"),
                ),
            ]
        )

        repository.upsert_lead_lag(
            [
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
                    window="4h",
                    best_lag_min=60,
                    strength=Decimal("0.7021"),
                    computed_ts=base_ts,
                ),
                LeadLagRecord(
                    leader="ETH",
                    follower="SOL",
                    window="1h",
                    best_lag_min=25,
                    strength=Decimal("0.6554"),
                    computed_ts=later_ts,
                ),
            ]
        )

        repository.upsert_granger_tests(
            [
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
                GrangerTestRecord(
                    x_symbol="ETH",
                    y_symbol="SOL",
                    window="1h",
                    p_value=Decimal("0.018700"),
                    direction="x->y",
                    computed_ts=later_ts,
                ),
            ]
        )
    finally:
        engine.dispose()


def main() -> None:
    load_demo_data()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
