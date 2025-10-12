"""Tests for the forthcoming z-score sentiment calculator."""

import math
from collections.abc import Iterable

import pytest

from ragtrader_pipelines.sentiment import (  # pragma: no cover -; intentional import failure until implemented
    SentimentSeriesPoint,
    SentimentZScore,
    ZScoreCalculator,
)


def _manual_zscores(window: int, scores: Iterable[float]) -> list[float]:
    """Compute population z-scores for the provided rolling window."""
    scores = list(scores)
    results: list[float] = []
    for idx in range(window - 1, len(scores)):
        window_scores = scores[idx - window + 1 : idx + 1]
        mean = sum(window_scores) / window
        variance = sum((value - mean) ** 2 for value in window_scores) / window
        stddev = math.sqrt(variance)
        if stddev == 0:
            results.append(0.0)
        else:
            results.append((scores[idx] - mean) / stddev)
    return results


@pytest.mark.parametrize(
    "window, scores",
    [
        (3, [10.0, 11.0, 12.0, 13.0, 14.0]),
        (4, [100.0, 101.0, 102.0, 104.0, 108.0, 110.0]),
    ],
)
def test_zscore_calculator_computes_expected_window_values(
    window: int, scores: list[float]
):
    """The calculator should emit rolling z-scores matching manual calculations."""
    coin = "BTC"
    interval_seconds = 60
    points = [
        SentimentSeriesPoint(coin=coin, timestamp=index * interval_seconds, score=score)
        for index, score in enumerate(scores)
    ]

    calculator = ZScoreCalculator(window=window)
    zscores: list[SentimentZScore] = list(calculator.calculate(points))

    # Only the last len(scores) - window + 1 z-scores are expected.
    expected_scores = _manual_zscores(window, scores)
    assert len(zscores) == len(expected_scores)

    # Skip the first window - 1 points;
    # each z-score should match manual calc and carry metadata.
    for offset, (point, expected) in enumerate(
        zip(zscores, expected_scores, strict=False)
    ):
        source_point = points[offset + window - 1]
        assert point.coin == coin
        assert point.window == window
        assert point.timestamp == source_point.timestamp
        assert point.z_score == pytest.approx(expected)


def test_zscore_calculator_isolates_coins():
    """Interleaved coin observations should be tracked independently."""
    window = 2
    points = [
        SentimentSeriesPoint(coin="BTC", timestamp=0, score=100.0),
        SentimentSeriesPoint(coin="ETH", timestamp=0, score=50.0),
        SentimentSeriesPoint(coin="BTC", timestamp=60, score=102.0),
        SentimentSeriesPoint(coin="ETH", timestamp=60, score=48.0),
        SentimentSeriesPoint(coin="BTC", timestamp=120, score=104.0),
        SentimentSeriesPoint(coin="ETH", timestamp=120, score=52.0),
    ]

    calculator = ZScoreCalculator(window=window)
    zscores: list[SentimentZScore] = list(calculator.calculate(points))

    # Separate results by coin while preserving chronological order.
    btc_scores = [value for value in zscores if value.coin == "BTC"]
    eth_scores = [value for value in zscores if value.coin == "ETH"]

    assert all(result.window == window for result in zscores)

    expected_btc = _manual_zscores(window, [100.0, 102.0, 104.0])
    expected_eth = _manual_zscores(window, [50.0, 48.0, 52.0])

    assert [result.timestamp for result in btc_scores] == [60, 120]
    assert [result.timestamp for result in eth_scores] == [60, 120]

    for result, expected in zip(btc_scores, expected_btc, strict=False):
        assert result.z_score == pytest.approx(expected)

    for result, expected in zip(eth_scores, expected_eth, strict=False):
        assert result.z_score == pytest.approx(expected)


def test_zscore_calculator_requires_enough_points():
    """If there are not enough points to fill the window,
    no z-score should be produced."""
    window = 5
    points = [
        SentimentSeriesPoint(coin="BTC", timestamp=0, score=10.0),
        SentimentSeriesPoint(coin="BTC", timestamp=60, score=11.0),
        SentimentSeriesPoint(coin="BTC", timestamp=120, score=12.0),
        SentimentSeriesPoint(coin="BTC", timestamp=180, score=13.0),
    ]

    calculator = ZScoreCalculator(window=window)
    zscores: list[SentimentZScore] = list(calculator.calculate(points))

    assert zscores == []
