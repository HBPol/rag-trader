"""Tests for the upcoming content aggregation orchestrator."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

import pytest

from ragtrader_pipelines.content import ArticleCandidate, ContentAggregator


class FakeClock:
    """Deterministic stand-in for ``datetime.datetime.now``."""

    def __init__(self, start: dt.datetime) -> None:
        self._now = start

    def now(self) -> dt.datetime:
        return self._now

    def advance(self, delta: dt.timedelta) -> None:
        self._now += delta


def make_candidate(
    *,
    source: str,
    url: str,
    title: str,
    clock: FakeClock,
    excerpt: str = "",
    coins: Iterable[str] | None = None,
    published_offset: dt.timedelta = dt.timedelta(),
) -> ArticleCandidate:
    """Factory helper that builds ``ArticleCandidate`` test doubles."""

    published_ts = clock.now() - published_offset
    return ArticleCandidate(
        source=source,
        url=url,
        title=title,
        excerpt=excerpt,
        coins=list(coins or ()),
        published_ts=published_ts,
    )


def test_aggregator_collapses_duplicates_within_window() -> None:
    clock = FakeClock(dt.datetime(2024, 5, 1, 12, 0, tzinfo=dt.UTC))
    aggregator = ContentAggregator(
        freshness_window=dt.timedelta(minutes=30),
        clock=clock.now,
    )

    batch_one = [
        make_candidate(
            source="coindesk",
            url="HTTPS://www.CoinDesk.com/Markets/Bitcoin-Rally/?utm_source=rss",
            title="Bitcoin Rally Charges Ahead",
            clock=clock,
        ),
        make_candidate(
            source="coindesk",
            url="https://www.coindesk.com/markets/bitcoin-rally/?utm_medium=newsletter",
            title="bitcoin rally charges ahead ",
            clock=clock,
        ),
        make_candidate(
            source="coindesk",
            url="https://www.coindesk.com/markets/ethereum-rally/",
            title="Ethereum Rally Builds Momentum",
            clock=clock,
        ),
    ]

    emitted_one = list(aggregator.emit("coindesk", batch_one))

    assert emitted_one == [batch_one[0], batch_one[2]]

    batch_two = [
        make_candidate(
            source="coindesk",
            url="https://www.coindesk.com/markets/bitcoin-rally/#section",
            title="BITCOIN RALLY CHARGES AHEAD",
            clock=clock,
        ),
        make_candidate(
            source="coindesk",
            url="https://www.coindesk.com/markets/ethereum-rally/",
            title="Ethereum Rally Builds Momentum",
            clock=clock,
        ),
    ]

    emitted_two = list(aggregator.emit("coindesk", batch_two))

    assert emitted_two == []


def test_aggregator_allows_reemit_after_ttl() -> None:
    clock = FakeClock(dt.datetime(2024, 5, 1, 9, 0, tzinfo=dt.UTC))
    aggregator = ContentAggregator(
        freshness_window=dt.timedelta(minutes=45),
        clock=clock.now,
    )

    first_seen = make_candidate(
        source="coindesk",
        url="https://www.coindesk.com/news/solana-upgrade/?utm_campaign=rss",
        title="Solana Network Upgrade Scheduled",
        clock=clock,
    )

    assert list(aggregator.emit("coindesk", [first_seen])) == [first_seen]

    dupe = make_candidate(
        source="coindesk",
        url="HTTPS://www.Coindesk.com/News/Solana-Upgrade/",
        title="solana network upgrade scheduled",
        clock=clock,
    )

    assert list(aggregator.emit("coindesk", [dupe])) == []

    clock.advance(dt.timedelta(hours=1))

    reemit = make_candidate(
        source="coindesk",
        url="https://www.coindesk.com/news/solana-upgrade/",
        title="Solana Network Upgrade Scheduled",
        clock=clock,
    )

    assert list(aggregator.emit("coindesk", [reemit])) == [reemit]


@pytest.mark.parametrize(
    "first_source,second_source",
    [("coindesk", "reddit"), ("reddit", "coindesk")],
)
def test_aggregator_dedupes_cross_adapter_duplicates(
    first_source: str, second_source: str
) -> None:
    clock = FakeClock(dt.datetime(2024, 5, 2, 15, 0, tzinfo=dt.UTC))
    aggregator = ContentAggregator(
        freshness_window=dt.timedelta(minutes=20),
        clock=clock.now,
    )

    canonical_url = "https://www.coindesk.com/policy/sec-updates-guidance/"

    first_batch = [
        make_candidate(
            source=first_source,
            url=f"{canonical_url}?utm_source={first_source}",
            title="SEC Updates Guidance for Bitcoin ETFs",
            clock=clock,
        )
    ]
    second_batch = [
        make_candidate(
            source=second_source,
            url=f"{canonical_url}?utm_medium={second_source}",
            title="sec updates guidance for bitcoin etfs",
            clock=clock,
        )
    ]

    emitted_first = list(aggregator.emit(first_source, first_batch))
    emitted_second = list(aggregator.emit(second_source, second_batch))

    assert emitted_first == first_batch
    assert emitted_second == []
