"""Coinbase OHLCV ingestion job."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import IntEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # pragma: no cover - import for type checkers only
    from sqlalchemy.engine import Engine

try:  # pragma: no cover - optional dependency during tests
    import httpx
except ModuleNotFoundError:  # pragma: no cover - deferred runtime failure
    httpx = None  # type: ignore[assignment]

DEFAULT_BASE_URL = "https://api.exchange.coinbase.com"


class Granularity(IntEnum):
    """Supported Coinbase candle granularities."""

    MIN_1 = 60
    MIN_5 = 300
    MIN_15 = 900
    MIN_60 = 3_600
    HOUR_6 = 21_600
    DAY_1 = 86_400

    @property
    def label(self) -> str:
        mapping = {
            Granularity.MIN_1: "1m",
            Granularity.MIN_5: "5m",
            Granularity.MIN_15: "15m",
            Granularity.MIN_60: "1h",
            Granularity.HOUR_6: "6h",
            Granularity.DAY_1: "1d",
        }
        return mapping[self]


@dataclass(frozen=True)
class OhlcvRecord:
    """Persistable OHLCV candle aligned with the database schema."""

    symbol: str
    interval: str
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class CandleRepository(Protocol):
    """Repository interface for persisting OHLCV candles."""

    def upsert_many(self, records: Sequence[OhlcvRecord]) -> None:
        """Persist the provided candles."""


class CoinbaseClient:
    """Thin wrapper around the Coinbase candles endpoint."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if httpx is None:  # pragma: no cover - runtime dependency guard
            msg = "httpx must be installed to use CoinbaseClient"
            raise RuntimeError(msg)
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
        )

    def fetch_candles(
        self,
        symbol: str,
        granularity: int,
        start: datetime,
        end: datetime,
    ) -> list[list[float]]:
        params = {
            "granularity": granularity,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        response = self._client.get(f"/products/{symbol}/candles", params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):  # pragma: no cover - defensive branch
            msg = "Unexpected response payload"
            raise ValueError(msg)
        return payload

    def close(self) -> None:
        self._client.close()


class CoinbaseOhlcvIngestion:
    """Fetch OHLCV candles from Coinbase and persist them."""

    def __init__(
        self,
        *,
        client: CoinbaseClient,
        repository: CandleRepository,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))

    def run(
        self,
        *,
        symbols: Iterable[str],
        granularity: Granularity,
        lookback: timedelta,
    ) -> None:
        if lookback <= timedelta(0):  # pragma: no cover - sanity check
            msg = "Lookback must be greater than zero"
            raise ValueError(msg)
        end = _ensure_aware(self._clock())
        start = end - lookback

        for symbol in symbols:
            raw = self._client.fetch_candles(symbol, granularity.value, start, end)
            records = self._transform(symbol, granularity, raw)
            if records:
                self._repository.upsert_many(records)

    def _transform(
        self,
        symbol: str,
        granularity: Granularity,
        raw_candles: Sequence[Sequence[float]],
    ) -> list[OhlcvRecord]:
        deduped: dict[datetime, OhlcvRecord] = {}
        for candle in raw_candles:
            if len(candle) < 6:  # pragma: no cover - defensive branch
                continue
            ts_seconds, low, high, open_, close, volume = candle[:6]
            ts = datetime.fromtimestamp(int(ts_seconds), tz=UTC)
            record = OhlcvRecord(
                symbol=symbol,
                interval=granularity.label,
                ts=ts,
                open=_to_decimal(open_),
                high=_to_decimal(high),
                low=_to_decimal(low),
                close=_to_decimal(close),
                volume=_to_decimal(volume),
            )
            deduped[ts] = record
        return [deduped[ts] for ts in sorted(deduped)]


class SqlAlchemyCandleRepository:
    """SQLAlchemy-backed repository for OHLCV candles."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @classmethod
    def from_dsn(cls, dsn: str) -> SqlAlchemyCandleRepository:
        try:  # pragma: no cover - runtime dependency guard
            from sqlalchemy import create_engine
        except ModuleNotFoundError as exc:  # pragma: no cover
            msg = "sqlalchemy must be installed to use SqlAlchemyCandleRepository"
            raise RuntimeError(msg) from exc
        engine = create_engine(dsn, future=True)
        return cls(engine)

    def upsert_many(self, records: Sequence[OhlcvRecord]) -> None:  # pragma: no cover
        """Persist the provided candles to the backing database."""

        from ragtrader_api.db.models import Ohlcv
        from sqlalchemy.dialects.postgresql import insert  # type: ignore
        from sqlalchemy.orm import Session

        with Session(self._engine) as session:
            stmt = insert(Ohlcv).values(
                [
                    {
                        "symbol": record.symbol,
                        "interval": record.interval,
                        "ts": record.ts,
                        "open": record.open,
                        "high": record.high,
                        "low": record.low,
                        "close": record.close,
                        "volume": record.volume,
                    }
                    for record in records
                ]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[Ohlcv.symbol, Ohlcv.interval, Ohlcv.ts],
                set_={
                    "open": stmt.excluded.open,
                    "high": stmt.excluded.high,
                    "low": stmt.excluded.low,
                    "close": stmt.excluded.close,
                    "volume": stmt.excluded.volume,
                },
            )
            session.execute(stmt)
            session.commit()


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(value))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Coinbase OHLCV ingestion job")
    parser.add_argument(
        "--symbols",
        default="BTC-USD,ETH-USD",
        help="Comma-separated list of product symbols",
    )
    parser.add_argument(
        "--granularity",
        default=Granularity.MIN_60.name,
        choices=[granularity.name for granularity in Granularity],
        help="Coinbase candle granularity",
    )
    parser.add_argument(
        "--lookback-minutes",
        type=int,
        default=360,
        help="Number of minutes to look back when fetching candles",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Database DSN for writing OHLCV data",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - CLI wiring
    args = build_arg_parser().parse_args(argv)
    symbols = [symbol.strip() for symbol in args.symbols.split(",") if symbol.strip()]
    if not symbols:
        msg = "At least one symbol must be provided"
        raise SystemExit(msg)

    granularity = Granularity[args.granularity]
    lookback = timedelta(minutes=args.lookback_minutes)

    repository: CandleRepository
    if args.database_url:
        repository = SqlAlchemyCandleRepository.from_dsn(args.database_url)
    else:
        msg = "DATABASE_URL must be set to persist data"
        raise SystemExit(msg)

    client = CoinbaseClient()
    job = CoinbaseOhlcvIngestion(client=client, repository=repository)
    try:
        job.run(symbols=symbols, granularity=granularity, lookback=lookback)
    finally:
        client.close()
    return 0


__all__ = [
    "CoinbaseClient",
    "CoinbaseOhlcvIngestion",
    "Granularity",
    "OhlcvRecord",
    "SqlAlchemyCandleRepository",
    "build_arg_parser",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - module CLI entrypoint
    raise SystemExit(main())
