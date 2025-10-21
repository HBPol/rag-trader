"""Forthcoming sentiment classifier guardrails (pre-implementation by design).

This module is written ahead of the concrete classifier to preserve our
TDD contract: the sentiment component must satisfy these behaviours once it
lands.  Until then the import below will fail, signalling the missing
implementation.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest

from ragtrader_pipelines.sentiment import (
    SentimentAspect,
    SentimentClassifier,
    SentimentLabel,
    SentimentResult,
    UnsupportedLanguageError,
)


@pytest.fixture(scope="module")
def classifier() -> SentimentClassifier:
    """Instantiate the future classifier once per test session."""

    return SentimentClassifier()


@pytest.fixture(
    params=[
        pytest.param(
            {
                "snippet": (
                    "Ethereum finalizes the Pectra upgrade, with analysts "
                    "calling for a sustained breakout as staking inflows surge."
                ),
                "metadata": {
                    "coins": ["eth", "arb", "ETH"],
                    "hype_signals": ["to the moon", "breakout"],
                    "regulatory_cues": [],
                    "security_incidents": [],
                },
                "expected_label": SentimentLabel.BULLISH,
                "expected_aspects": {SentimentAspect.HYPE},
                "confidence_range": (0.65, 1.0),
                "expected_coins": ("ARB", "ETH"),
            },
            id="bullish-hype-breakout",
        ),
        pytest.param(
            {
                "snippet": (
                    "SEC issues Wells notice to Solana Foundation; investigators "
                    "cite unresolved disclosures and the SOL token slumps on the news."
                ),
                "metadata": {
                    "coins": ["sol", "Sol"],
                    "hype_signals": [],
                    "regulatory_cues": ["SEC", "investigation"],
                    "security_incidents": ["disclosure"],
                },
                "expected_label": SentimentLabel.BEARISH,
                "expected_aspects": {
                    SentimentAspect.REGULATORY,
                    SentimentAspect.SECURITY,
                },
                "confidence_range": (0.6, 0.95),
                "expected_coins": ("SOL",),
            },
            id="bearish-regulatory-crackdown",
        ),
        pytest.param(
            {
                "snippet": (
                    "Bitcoin trades sideways near $30k with derivatives positioning "
                    "showing little directional conviction among market makers."
                ),
                "metadata": {
                    "coins": ["btc"],
                    "hype_signals": [],
                    "regulatory_cues": [],
                    "security_incidents": [],
                },
                "expected_label": SentimentLabel.NEUTRAL,
                "expected_aspects": set(),
                "confidence_range": (0.35, 0.6),
                "expected_coins": ("BTC",),
            },
            id="neutral-rangebound",
        ),
    ]
)
def canonical_sentiment_case(request: pytest.FixtureRequest) -> dict[str, object]:
    """Representative fixtures the classifier must handle correctly."""

    return request.param


def _assert_aspect_match(
    observed: Iterable[SentimentAspect],
    expected: set[SentimentAspect],
) -> None:
    """Helper to normalise the aspect container before assertion."""

    assert set(observed) == expected


def _assert_coin_alignment(observed: Iterable[str], expected: Iterable[str]) -> None:
    """Ensure coin tickers come back sorted, upper-cased, and unique."""

    assert tuple(observed) == tuple(expected)


def test_classifier_emits_expected_sentiment_profile(
    classifier: SentimentClassifier,
    canonical_sentiment_case: dict[str, object],
) -> None:
    """Classifier must respect polarity, aspects, coins, and confidence bounds."""

    result = classifier.classify(
        text=canonical_sentiment_case["snippet"],
        metadata=canonical_sentiment_case["metadata"],
    )
    assert isinstance(result, SentimentResult)
    assert result.label is canonical_sentiment_case["expected_label"]
    _assert_aspect_match(result.aspects, canonical_sentiment_case["expected_aspects"])
    lower, upper = canonical_sentiment_case["confidence_range"]
    assert lower <= result.confidence <= upper
    _assert_coin_alignment(result.coins, canonical_sentiment_case["expected_coins"])


def test_classifier_rejects_mixed_language_payload(
    classifier: SentimentClassifier,
) -> None:
    """Mixed-language inputs should surface as unsupported content."""

    with pytest.raises(UnsupportedLanguageError):
        classifier.classify(
            text="Bitcoin sube fuerte pero regulators warn of volatility",
            metadata={"language": "es-en", "coins": ["btc"]},
        )


def test_classifier_returns_sentinel_for_empty_text(
    classifier: SentimentClassifier,
) -> None:
    """Empty snippets should yield an explicit UNKNOWN result with zero confidence."""

    result = classifier.classify(
        text="   ",
        metadata={"coins": ["eth", "BTC"]},
    )
    assert isinstance(result, SentimentResult)
    assert result.label is SentimentLabel.UNKNOWN
    _assert_aspect_match(result.aspects, set())
    assert result.confidence == pytest.approx(0.0)
    _assert_coin_alignment(result.coins, ())


def test_classifier_handles_multi_coin_metadata(
    classifier: SentimentClassifier,
) -> None:
    """Downstream consumers expect stable ordering and deduplication of coins."""

    result = classifier.classify(
        text=(
            "Layer-2 usage climbs as Arbitrum and Optimism both see record "
            "transactions following the ETF greenlight."
        ),
        metadata={"coins": ["op", "arb", "ARB", "OP"], "hype_signals": ["record"]},
    )
    assert result.label in {SentimentLabel.BULLISH, SentimentLabel.NEUTRAL}
    _assert_coin_alignment(result.coins, ("ARB", "OP"))
