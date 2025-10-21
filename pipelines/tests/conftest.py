"""Shared pytest configuration for the pipelines test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PATHS = [ROOT, ROOT / "api" / "src", ROOT / "api" / "tests"]

for path in PATHS:
    candidate = str(path)
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


@pytest.fixture
def coindesk_documented_payload() -> dict[str, object]:
    """Return a payload shaped like CoinDesk's documented API response."""

    return {
        "GUID": "doc-asset-123",
        "TITLE": "Bitcoin, Ether, and Solana Rally Ahead of Halving",
        "URL": "HTTPS://www.coindesk.com/markets/halving-preview/?utm_source=rss#section",
        "BODY": (
            "<p>Bitcoin (BTC) and Ether (ETH) extend gains while SOL follows suit.</p>"
        ),
        "PUBLISHED_ON": "2024-05-20T10:45:00Z",
        "LANGUAGE": "EN",
        "KEYWORDS": ["BTC"],
        "CATEGORY_DATA": [
            {"primary_ticker": "ETH"},
            {"related_assets": [{"ticker": "SOL"}]},
        ],
    }


@pytest.fixture
def coindesk_headlines_payload() -> dict[str, object]:
    """Return a sample payload from CoinDesk's aggregated headlines API."""

    return {
        "TYPE": "121",
        "ID": 53448094,
        "GUID": "https://en.coinotag.com/screxs-scrx-token-presale-aims-to-address-defi-challenges-with-ai-integration/",
        "PUBLISHED_ON": 1_761_037_978,
        "IMAGE_URL": "https://resources.cryptocompare.com/news/77/53448094.jpeg",
        "TITLE": "Screx’s SCRX Token Presale Aims to Address DeFi Challenges with AI Integration",
        "AUTHORS": "Marisol Navaro",
        "URL": "https://en.coinotag.com/screxs-scrx-token-presale-aims-to-address-defi-challenges-with-ai-integration/",
        "BODY": (
            "Screx is an innovative DeFi platform powered by AI that addresses key challenges like"
            " liquidity fragmentation and complex interfaces. It integrates swaps, lending, staking,"
            " and more into a unified ecosystem."
        ),
        "KEYWORDS": "News|Aave|ARB|AVAX|BNB|COMP|Core|ETH|FTM|MATIC|UNI",
        "LANG": "EN",
        "SENTIMENT": "POSITIVE",
        "STATUS": "ACTIVE",
        "CATEGORY_DATA": [
            {"TYPE": "122", "ID": 8, "NAME": "AVAX", "CATEGORY": "AVAX"},
            {"TYPE": "122", "ID": 17, "NAME": "COMP", "CATEGORY": "COMP"},
            {"TYPE": "122", "ID": 71, "NAME": "ARB", "CATEGORY": "ARB"},
            {"TYPE": "122", "ID": 74, "NAME": "BNB", "CATEGORY": "BNB"},
            {
                "TYPE": "122",
                "ID": 211,
                "NAME": "CRYPTOCURRENCY",
                "CATEGORY": "CRYPTOCURRENCY",
            },
        ],
        "SOURCE_DATA": {
            "TYPE": "120",
            "ID": 77,
            "SOURCE_KEY": "coinotag",
            "NAME": "CoinOtag",
            "LANG": "EN",
            "SOURCE_TYPE": "RSS",
            "STATUS": "ACTIVE",
        },
    }
