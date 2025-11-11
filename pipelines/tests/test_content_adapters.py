"""Focused tests for BaseContentAdapter helpers."""

from __future__ import annotations

from ragtrader_pipelines.content import BaseContentAdapter


def test_normalize_coins_filters_unknown_tokens() -> None:
    """Only supported tickers should survive normalization."""

    coins = BaseContentAdapter._normalize_coins(
        ["btc", "eth", "AI"],
        ["GOOGLE", "sol"],
        ["arb", "NFT"],
    )

    assert coins == ["ARB", "BTC", "ETH", "SOL"]
