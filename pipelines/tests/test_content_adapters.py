"""Focused tests for BaseContentAdapter helpers."""

from __future__ import annotations

from ragtrader_pipelines.content import BaseContentAdapter, CoinDeskAdapter


def _coindesk_payload(url: str) -> dict[str, object]:
    return {
        "url": url,
        "title": "Halving Preview",
        "excerpt": "Bitcoin prepares for halving.",
        "published_time": "2024-05-01T16:34:56+00:00",
    }


def test_normalize_coins_filters_unknown_tokens() -> None:
    """Only supported tickers should survive normalization."""

    coins = BaseContentAdapter._normalize_coins(
        ["btc", "eth", "AI"],
        ["GOOGLE", "sol"],
        ["arb", "NFT"],
    )

    assert coins == ["ARB", "BTC", "ETH", "SOL"]


def test_normalize_url_uses_canonical_host_for_coindesk_aliases() -> None:
    url = "HTTPS://coindesk.com/Markets/BTC-Surge?utm_source=rss#section"

    normalized = BaseContentAdapter._normalize_url(
        url, canonical_host="www.coindesk.com"
    )

    assert normalized == "https://www.coindesk.com/markets/btc-surge"


def test_normalize_url_preserves_third_party_host() -> None:
    url = "https://partner.example.com/Partner/Feed/Story?ref=cd"

    normalized = BaseContentAdapter._normalize_url(
        url, canonical_host="www.coindesk.com"
    )

    assert normalized == "https://partner.example.com/partner/feed/story"


def test_coindesk_adapter_normalizes_urls_for_first_party_articles() -> None:
    adapter = CoinDeskAdapter()

    article = adapter.parse(
        _coindesk_payload("HTTPS://coindesk.com/Markets/BTC-Surge/?utm_source=rss")
    )

    assert article is not None
    assert article.url == "https://www.coindesk.com/markets/btc-surge/"


def test_coindesk_adapter_preserves_partner_hosts() -> None:
    adapter = CoinDeskAdapter()

    article = adapter.parse(
        _coindesk_payload("https://partner.example.com/Feeds/Story/Item?utm_source=rss")
    )

    assert article is not None
    assert article.url == "https://partner.example.com/feeds/story/item"
