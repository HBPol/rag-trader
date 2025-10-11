"""Tests for upcoming content parsing adapters.

These tests assert parsing and normalization behavior for the
CoinDesk, CoinTelegraph, and Reddit adapters. They intentionally
import not-yet-implemented adapters/classes to drive the TDD workflow.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ragtrader_pipelines.content import (
    ArticleCandidate,
    CoinDeskAdapter,
    CoinTelegraphAdapter,
    RedditAdapter,
)


@pytest.fixture
def coindesk_payload() -> dict:
    return {
        "guid": "coindesk-abc123",
        "title": "Bitcoin Rally Charges Ahead",
        "link": "HTTPS://CoinDesk.com/Markets/Bitcoin-Rally/?utm_source=rss&utm_medium=feed#section",
        "summary": "<p>  Bitcoin pushes <strong>above</strong> $60K again. </p>",
        "published": "2024-05-01T12:34:56-04:00",
        "source": "CoinDesk",
        "language": "En-US",
        "tickers": ["btc", "Eth"],
    }


@pytest.fixture
def cointelegraph_payload() -> dict:
    return {
        "id": "cointelegraph-987",
        "headline": "Solana NFTs Gain Momentum",
        "url": "https://cointelegraph.com/news/solana-nfts-gain-momentum?ref=rss",
        "description": "<div>Solana-based collections attract new buyers.</div>",
        "published_at": "2024-05-02 18:05:00+03:00",
        "source": "COINTELEGRAPH",
        "language_hint": "EN",
        "tags": ["SOL", "nft"],
    }


@pytest.fixture
def reddit_payload() -> dict:
    return {
        "id": "t3_xyz321",
        "title": "ETH whales scoop up more coins",
        "url": "https://www.reddit.com/r/ethfinance/comments/xyz321/eth_whales_scoop_up_more_coins/?utm_medium=web2x",
        "selftext": "<div>Traders discuss ETH and BTC accumulation.</div>",
        "created_utc": 1_714_459_545,
        "language": "en",
        "tickers": ["eth", "btc"],
    }


@pytest.mark.parametrize(
    "adapter_cls,payload_fixture,expected",
    [
        (
            CoinDeskAdapter,
            "coindesk_payload",
            {
                "source": "coindesk",
                "url": "https://www.coindesk.com/markets/bitcoin-rally/",
                "title": "Bitcoin Rally Charges Ahead",
                "excerpt": "Bitcoin pushes above $60K again.",
                "coins": ["BTC", "ETH"],
                "published_ts": dt.datetime(2024, 5, 1, 16, 34, 56, tzinfo=dt.UTC),
            },
        ),
        (
            CoinTelegraphAdapter,
            "cointelegraph_payload",
            {
                "source": "cointelegraph",
                "url": "https://cointelegraph.com/news/solana-nfts-gain-momentum",
                "title": "Solana NFTs Gain Momentum",
                "excerpt": "Solana-based collections attract new buyers.",
                "coins": ["SOL"],
                "published_ts": dt.datetime(2024, 5, 2, 15, 5, tzinfo=dt.UTC),
            },
        ),
        (
            RedditAdapter,
            "reddit_payload",
            {
                "source": "reddit",
                "url": "https://www.reddit.com/r/ethfinance/comments/xyz321/eth_whales_scoop_up_more_coins/",
                "title": "ETH whales scoop up more coins",
                "excerpt": "Traders discuss ETH and BTC accumulation.",
                "coins": ["BTC", "ETH"],
                "published_ts": dt.datetime(2024, 4, 30, 6, 45, 45, tzinfo=dt.UTC),
            },
        ),
    ],
    ids=["coindesk", "cointelegraph", "reddit"],
)
def test_adapter_normalization(adapter_cls, payload_fixture, expected, request):
    adapter = adapter_cls()
    payload = request.getfixturevalue(payload_fixture)

    article = adapter.parse(payload)

    assert isinstance(article, ArticleCandidate)
    assert article.source == expected["source"]
    assert article.url == expected["url"]
    assert article.title == expected["title"]
    assert article.excerpt == expected["excerpt"]
    assert article.coins == expected["coins"]
    assert article.published_ts == expected["published_ts"]
    assert article.published_ts.tzinfo is not None
    assert article.published_ts.utcoffset() == dt.timedelta(0)


@pytest.mark.parametrize(
    "adapter_cls,payload_fixture",
    [
        (CoinDeskAdapter, "coindesk_payload"),
        (CoinTelegraphAdapter, "cointelegraph_payload"),
        (RedditAdapter, "reddit_payload"),
    ],
    ids=["coindesk", "cointelegraph", "reddit"],
)
def test_adapter_language_filter(adapter_cls, payload_fixture, request):
    adapter = adapter_cls()
    payload = dict(request.getfixturevalue(payload_fixture))

    # Use an obviously non-English signal to trigger language filtering.
    payload.update({"language": "de", "language_hint": "DE"})

    try:
        result = adapter.parse(payload)
    except Exception as exc:  # noqa: BLE001
        # Sentinel exceptions are implementation-defined. The adapter is allowed
        # to raise a sentinel error type instead of returning None.
        assert exc.__class__.__name__.lower().startswith("unsupported")
    else:
        assert result is None
