"""Tests for the Coinbase OHLCV ingestion job."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

import pytest

from ragtrader_pipelines.coinbase import (
    CoinbaseOhlcvIngestion,
    Granularity,
    OhlcvRecord,
)


class StubClient:
    def __init__(self, payload: list[list[float]] | None = None) -> None:
        self.payload = payload or []
        self.calls: list[tuple[str, int, datetime, datetime]] = []

    def fetch_candles(
        self,
        symbol: str,
        granularity: int,
        start: datetime,
        end: datetime,
    ) -> list[list[float]]:
        self.calls.append((symbol, granularity, start, end))
        return self.payload


class StubRepository:
    def __init__(self) -> None:
        self.writes: list[Sequence[OhlcvRecord]] = []

    def upsert_many(self, records: Sequence[OhlcvRecord]) -> None:
        self.writes.append(records)


def test_job_requests_expected_time_window() -> None:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    lookback = timedelta(hours=4)
    client = StubClient()
    repo = StubRepository()
    job = CoinbaseOhlcvIngestion(client=client, repository=repo, clock=lambda: now)

    job.run(symbols=["BTC-USD"], granularity=Granularity.MIN_60, lookback=lookback)

    assert client.calls == [
        (
            "BTC-USD",
            Granularity.MIN_60.value,
            now - lookback,
            now,
        )
    ]


def test_job_deduplicates_records_before_writing() -> None:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    ts = int(datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc).timestamp())
    client = StubClient(
        payload=[
            [ts, 100.0, 110.0, 95.0, 105.0, 42.0],
            [ts, 100.0, 110.0, 95.0, 105.0, 42.0],
            [ts + 3600, 105.0, 115.0, 101.0, 109.0, 43.0],
        ]
    )
    repo = StubRepository()
    job = CoinbaseOhlcvIngestion(client=client, repository=repo, clock=lambda: now)

    job.run(symbols=["ETH-USD"], granularity=Granularity.MIN_60, lookback=timedelta(hours=4))

    assert len(repo.writes) == 1
    records = list(repo.writes[0])
    assert [record.ts for record in records] == [
        datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
    ]
    assert {record.volume for record in records} == {
        Decimal("42.0"),
        Decimal("43.0"),
    }


@pytest.mark.parametrize(
    "record",
    [
        OhlcvRecord(
            symbol="BTC-USD",
            interval="1h",
            ts=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("100"),
            high=Decimal("110"),
            low=Decimal("95"),
            close=Decimal("105"),
            volume=Decimal("42"),
        )
    ],
)
def test_record_schema_aligns_with_database_expectations(record: OhlcvRecord) -> None:
    assert record.__dict__.keys() == {
        "symbol",
        "interval",
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }
