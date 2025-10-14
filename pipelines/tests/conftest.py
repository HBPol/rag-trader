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
