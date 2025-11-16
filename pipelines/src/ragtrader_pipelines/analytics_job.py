"""End-to-end analytics job that persists correlation, lead/lag, and Granger metrics."""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from itertools import combinations, permutations
from typing import cast

import numpy as np
import pandas as pd
from sqlalchemy import Select, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ragtrader_api.db.models import Ohlcv, Sentiment
from ragtrader_api.db.repositories.analytics import (
    FeatureRecord,
    GrangerTestRecord,
    LeadLagRecord,
    SqlAlchemyAnalyticsRepository,
)

from .analytics import (
    GrangerCausalityError,
    SeriesLike,
    best_cross_correlation,
    rolling_pearson,
    rolling_spearman,
    run_granger_causality,
)
from .registry import PipelineRegistry

SessionFactory = sessionmaker[Session]

_DECIMAL_QUANT = Decimal("0.000000000001")
_DEFAULT_PRICE_INTERVAL = "1h"
_DEFAULT_SENTIMENT_WINDOW = 6


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized = symbol.strip().upper()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_window(window: str) -> pd.Timedelta:
    try:
        parsed = pd.to_timedelta(window)
    except ValueError as exc:  # pragma: no cover - defensive guard
        msg = f"Unsupported window value '{window}'"
        raise ValueError(msg) from exc
    if parsed <= pd.Timedelta(0):
        raise ValueError("Window durations must be positive")
    return parsed


def _quantize(value: float | None) -> Decimal:
    if value is None:
        raise ValueError("Cannot quantize a null value")
    if not np.isfinite(value):
        raise ValueError("Cannot quantize non-finite values")
    return Decimal(str(value)).quantize(_DECIMAL_QUANT, rounding=ROUND_HALF_EVEN)


def _to_series_like(series: pd.Series, name: str) -> SeriesLike:
    """Rename the pandas ``Series`` and treat it as a ``SeriesLike``."""

    renamed = series.rename(name)
    return cast(SeriesLike, renamed)


def _infer_interval(series: pd.Series) -> pd.Timedelta:
    default_interval = pd.Timedelta(minutes=1)
    if series.empty or len(series) < 2:
        return default_interval

    index = series.index
    if not isinstance(index, pd.DatetimeIndex):
        return default_interval

    datetime_index = pd.DatetimeIndex(index)
    deltas = pd.Series(datetime_index.asi8).diff().dropna()
    if deltas.empty:
        return default_interval

    median_ns = deltas.median()
    if pd.isna(median_ns) or not np.isfinite(median_ns) or median_ns <= 0:
        return default_interval

    return pd.to_timedelta(median_ns, unit="ns")


def _resample_returns(series: pd.Series, window: pd.Timedelta) -> pd.Series:
    resampled = series.resample(window, label="right", closed="right").last().dropna()
    if resampled.empty:
        return pd.Series(dtype=float, name=series.name or "returns")
    float_values = resampled.astype(float)
    log_prices = pd.Series(np.log(float_values.to_numpy()), index=float_values.index)
    returns = log_prices.diff().dropna()
    returns.name = series.name or "returns"
    return returns


def _resample_sentiment(series: pd.Series, window: pd.Timedelta) -> pd.Series:
    aggregated = series.resample(window, label="right", closed="right").mean().dropna()
    return aggregated.rename(series.name or "sentiment")


def _rolling_window_periods(window: pd.Timedelta, base_interval: pd.Timedelta) -> int:
    if base_interval <= pd.Timedelta(0):
        return 3
    ratio = int(round(window / base_interval))
    return max(3, ratio)


@dataclass(slots=True)
class SqlAlchemyOhlcvRepository:
    """Read-only repository for OHLCV closes backed by SQLAlchemy."""

    session_factory: SessionFactory

    def load_closes(
        self,
        *,
        symbols: Sequence[str],
        interval: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, pd.Series]:
        if not symbols:
            return {}

        stmt: Select[tuple[str, datetime, Decimal]] = (
            select(Ohlcv.symbol, Ohlcv.ts, Ohlcv.close)
            .where(Ohlcv.symbol.in_(symbols))
            .where(Ohlcv.interval == interval)
            .where(Ohlcv.ts >= start)
            .where(Ohlcv.ts <= end)
            .order_by(Ohlcv.ts.asc())
        )

        grouped: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        with self.session_factory() as session:
            rows = session.execute(stmt).all()
        for symbol, ts, close in rows:
            grouped[symbol].append((ts, float(close)))

        series: dict[str, pd.Series] = {}
        for symbol, entries in grouped.items():
            if not entries:
                continue
            timestamps = pd.to_datetime([ts for ts, _ in entries])
            values = pd.Series([value for _, value in entries], index=timestamps)
            values = values.sort_index()
            values.name = symbol
            series[symbol] = values
        return series


@dataclass(slots=True)
class SqlAlchemySentimentRepository:
    """Read-only repository for sentiment z-scores."""

    session_factory: SessionFactory

    def load_zscores(
        self,
        *,
        symbols: Sequence[str],
        zscore_window: int,
        start: datetime,
        end: datetime,
    ) -> dict[str, pd.Series]:
        if not symbols:
            return {}

        stmt: Select[tuple[str, datetime, Decimal]] = (
            select(Sentiment.coin, Sentiment.ts, Sentiment.zscore)
            .where(Sentiment.coin.in_(symbols))
            .where(Sentiment.zscore_window == zscore_window)
            .where(Sentiment.ts.is_not(None))
            .where(Sentiment.zscore.is_not(None))
            .where(Sentiment.ts >= start)
            .where(Sentiment.ts <= end)
            .order_by(Sentiment.ts.asc())
        )

        grouped: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
        with self.session_factory() as session:
            rows = session.execute(stmt).all()
        for coin, ts, zscore in rows:
            grouped[coin].append((ts, float(zscore)))

        series: dict[str, pd.Series] = {}
        for coin, entries in grouped.items():
            if not entries:
                continue
            timestamps = pd.to_datetime([ts for ts, _ in entries])
            values = pd.Series([value for _, value in entries], index=timestamps)
            values = values.sort_index()
            values.name = coin
            series[coin] = values
        return series


class AnalyticsJob:
    """Compose OHLCV + sentiment series to persist analytics metrics."""

    def __init__(
        self,
        *,
        price_repository: SqlAlchemyOhlcvRepository,
        sentiment_repository: SqlAlchemySentimentRepository,
        analytics_repository: SqlAlchemyAnalyticsRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._prices = price_repository
        self._sentiments = sentiment_repository
        self._analytics = analytics_repository
        self._clock = clock or _now

    def run(
        self,
        *,
        symbols: Sequence[str],
        start: datetime,
        end: datetime,
        windows: Sequence[str],
        price_interval: str = _DEFAULT_PRICE_INTERVAL,
        zscore_window: int = _DEFAULT_SENTIMENT_WINDOW,
        max_lag_minutes: int = 120,
    ) -> None:
        if start >= end:
            raise ValueError("Start timestamp must be earlier than the end timestamp")
        if max_lag_minutes < 0:
            raise ValueError("max_lag_minutes must be non-negative")
        normalized_symbols = _normalize_symbols(symbols)
        if not normalized_symbols:
            raise ValueError("At least one symbol must be provided")

        resolved_windows = list(
            dict.fromkeys(window.strip() for window in windows if window)
        )
        if not resolved_windows:
            raise ValueError("At least one sampling window must be provided")

        price_series = self._prices.load_closes(
            symbols=normalized_symbols,
            interval=price_interval,
            start=start,
            end=end,
        )
        sentiment_series = self._sentiments.load_zscores(
            symbols=normalized_symbols,
            zscore_window=zscore_window,
            start=start,
            end=end,
        )

        computed_ts = self._clock()
        feature_records: list[FeatureRecord] = []
        returns_by_window: dict[str, dict[str, pd.Series]] = defaultdict(dict)

        for symbol in normalized_symbols:
            prices = price_series.get(symbol)
            sentiments = sentiment_series.get(symbol)
            if prices is None or prices.empty or sentiments is None or sentiments.empty:
                continue
            base_interval = _infer_interval(prices)

            for window_label in resolved_windows:
                window = _parse_window(window_label)
                returns = _resample_returns(prices, window)
                raw_returns = returns.dropna()
                aggregated_sentiment = _resample_sentiment(sentiments, window)
                aggregated_sentiment = aggregated_sentiment.dropna()
                if raw_returns.empty or aggregated_sentiment.empty:
                    continue

                returns_by_window[window_label][symbol] = raw_returns.rename(symbol)

                aligned_returns, aligned_sentiment = raw_returns.align(
                    aggregated_sentiment, join="inner"
                )
                aligned_returns = aligned_returns.dropna()
                aligned_sentiment = aligned_sentiment.dropna()
                if aligned_returns.empty or aligned_sentiment.empty:
                    continue

                window_periods = _rolling_window_periods(window, base_interval)
                pearson = rolling_pearson(
                    aligned_returns,
                    aligned_sentiment,
                    window=window_periods,
                    min_periods=window_periods,
                )
                spearman = rolling_spearman(
                    aligned_returns,
                    aligned_sentiment,
                    window=window_periods,
                    min_periods=window_periods,
                )

                feature_records.extend(
                    self._build_feature_records(
                        symbol, window_label, pearson, metric="pearson"
                    )
                )
                feature_records.extend(
                    self._build_feature_records(
                        symbol, window_label, spearman, metric="spearman"
                    )
                )

        if feature_records:
            self._analytics.upsert_features(feature_records)

        lead_lag_records = self._compute_lead_lag(
            returns_by_window,
            normalized_symbols,
            max_lag_minutes,
            computed_ts,
        )
        if lead_lag_records:
            self._analytics.upsert_lead_lag(lead_lag_records)

        granger_records = self._compute_granger(
            returns_by_window,
            normalized_symbols,
            max_lag_minutes,
            computed_ts,
        )
        if granger_records:
            self._analytics.upsert_granger_tests(granger_records)

    def _build_feature_records(
        self,
        symbol: str,
        window: str,
        series: pd.Series,
        *,
        metric: str,
    ) -> list[FeatureRecord]:
        records: list[FeatureRecord] = []
        cleaned = series.dropna()
        if cleaned.empty:
            return records
        feature_name = f"correlation:return_vs_sentiment:{metric}:{window}"
        for timestamp, value in cleaned.items():
            if not isinstance(timestamp, pd.Timestamp):
                try:
                    timestamp = pd.Timestamp(timestamp)
                except (TypeError, ValueError):
                    continue
            try:
                decimal_value = _quantize(float(value))
            except ValueError:
                continue
            python_ts = timestamp.to_pydatetime()
            records.append(
                FeatureRecord(
                    symbol=symbol,
                    feature_name=feature_name,
                    ts=python_ts,
                    value=decimal_value,
                )
            )
        return records

    def _compute_lead_lag(
        self,
        returns_by_window: Mapping[str, Mapping[str, pd.Series]],
        symbols: Sequence[str],
        max_lag_minutes: int,
        computed_ts: datetime,
    ) -> list[LeadLagRecord]:
        records: list[LeadLagRecord] = []
        for window_label, per_symbol in returns_by_window.items():
            if len(per_symbol) < 2:
                continue
            window = _parse_window(window_label)
            window_minutes = max(1, int(window / pd.Timedelta(minutes=1)))
            max_lag_steps = max(0, max_lag_minutes // window_minutes)
            for leader, follower in permutations(symbols, 2):
                leader_series = per_symbol.get(leader)
                follower_series = per_symbol.get(follower)
                if (
                    leader_series is None
                    or follower_series is None
                    or leader_series.empty
                    or follower_series.empty
                ):
                    continue
                best = best_cross_correlation(
                    leader_series,
                    follower_series,
                    max_lag=max_lag_steps,
                )
                if best is None:
                    continue
                lag_steps, strength = best
                try:
                    strength_decimal = _quantize(float(strength))
                except ValueError:
                    continue
                records.append(
                    LeadLagRecord(
                        leader=leader,
                        follower=follower,
                        window=window_label,
                        best_lag_min=int(lag_steps * window_minutes),
                        strength=strength_decimal,
                        computed_ts=computed_ts,
                    )
                )
        return records

    def _compute_granger(
        self,
        returns_by_window: Mapping[str, Mapping[str, pd.Series]],
        symbols: Sequence[str],
        max_lag_minutes: int,
        computed_ts: datetime,
    ) -> list[GrangerTestRecord]:
        records: list[GrangerTestRecord] = []
        for window_label, per_symbol in returns_by_window.items():
            if len(per_symbol) < 2:
                continue
            window = _parse_window(window_label)
            window_minutes = max(1, int(window / pd.Timedelta(minutes=1)))
            max_lag_steps = max(1, max_lag_minutes // window_minutes)
            for leader, follower in combinations(symbols, 2):
                leader_series = per_symbol.get(leader)
                follower_series = per_symbol.get(follower)
                if (
                    leader_series is None
                    or follower_series is None
                    or leader_series.empty
                    or follower_series.empty
                ):
                    continue
                leader_series_like = _to_series_like(leader_series, leader)
                follower_series_like = _to_series_like(follower_series, follower)
                try:
                    summary = run_granger_causality(
                        leader_series_like,
                        follower_series_like,
                        max_lag=max_lag_steps,
                    )
                except GrangerCausalityError:
                    continue

                leader_record = GrangerTestRecord(
                    x_symbol=leader,
                    y_symbol=follower,
                    window=window_label,
                    p_value=_quantize(summary.leader_to_follower.p_value),
                    direction="x->y",
                    computed_ts=computed_ts,
                )
                follower_record = GrangerTestRecord(
                    x_symbol=follower,
                    y_symbol=leader,
                    window=window_label,
                    p_value=_quantize(summary.follower_to_leader.p_value),
                    direction="y->x",
                    computed_ts=computed_ts,
                )
                records.extend((leader_record, follower_record))
        return records


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the analytics ETL job")
    parser.add_argument(
        "--start",
        required=True,
        help="Start timestamp (ISO 8601)",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End timestamp (ISO 8601)",
    )
    parser.add_argument(
        "--symbols",
        default="BTC,ETH",
        help="Comma-separated list of instrument symbols to analyze",
    )
    parser.add_argument(
        "--windows",
        action="append",
        required=True,
        help="Comma-separated sampling windows (e.g. 1h,4h)",
    )
    parser.add_argument(
        "--price-interval",
        default=_DEFAULT_PRICE_INTERVAL,
        help="OHLCV interval label to query (default: 1h)",
    )
    parser.add_argument(
        "--sentiment-window",
        type=int,
        default=_DEFAULT_SENTIMENT_WINDOW,
        help="Rolling window used when persisting z-scores",
    )
    parser.add_argument(
        "--max-lag-minutes",
        type=int,
        default=120,
        help="Maximum lag (in minutes) for cross-correlation and Granger tests",
    )
    parser.add_argument(
        "--database-url",
        help="SQLAlchemy database URL (falls back to DATABASE_URL)",
    )
    return parser


def _parse_windows_argument(values: Sequence[str]) -> list[str]:
    parsed: list[str] = []
    for chunk in values:
        parts = [part.strip() for part in chunk.split(",")]
        parsed.extend(filter(None, parts))
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    start = _parse_datetime(args.start)
    end = _parse_datetime(args.end)
    symbols = _normalize_symbols(args.symbols.split(","))
    windows = _parse_windows_argument(args.windows)
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must be provided")

    engine = create_engine(database_url, future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    price_repo = SqlAlchemyOhlcvRepository(session_factory)
    sentiment_repo = SqlAlchemySentimentRepository(session_factory)
    analytics_repo = SqlAlchemyAnalyticsRepository(session_factory)

    job = AnalyticsJob(
        price_repository=price_repo,
        sentiment_repository=sentiment_repo,
        analytics_repository=analytics_repo,
    )
    job.run(
        symbols=symbols,
        start=start,
        end=end,
        windows=windows,
        price_interval=args.price_interval,
        zscore_window=int(args.sentiment_window),
        max_lag_minutes=int(args.max_lag_minutes),
    )
    engine.dispose()
    return 0


def register_analytics_job(
    registry: PipelineRegistry,
    *,
    database_url: str,
    symbols: Sequence[str],
    windows: Sequence[str],
    lookback: timedelta,
    price_interval: str = _DEFAULT_PRICE_INTERVAL,
    sentiment_window: int = _DEFAULT_SENTIMENT_WINDOW,
    max_lag_minutes: int = 120,
) -> None:
    engine = create_engine(database_url, future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    price_repo = SqlAlchemyOhlcvRepository(session_factory)
    sentiment_repo = SqlAlchemySentimentRepository(session_factory)
    analytics_repo = SqlAlchemyAnalyticsRepository(session_factory)
    job = AnalyticsJob(
        price_repository=price_repo,
        sentiment_repository=sentiment_repo,
        analytics_repository=analytics_repo,
        clock=_now,
    )

    def _pipeline() -> None:
        end = _now()
        start = end - lookback
        job.run(
            symbols=symbols,
            start=start,
            end=end,
            windows=windows,
            price_interval=price_interval,
            zscore_window=sentiment_window,
            max_lag_minutes=max_lag_minutes,
        )

    registry.register("analytics.job", _pipeline)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())


__all__ = [
    "AnalyticsJob",
    "SqlAlchemyOhlcvRepository",
    "SqlAlchemySentimentRepository",
    "build_arg_parser",
    "main",
    "register_analytics_job",
]
