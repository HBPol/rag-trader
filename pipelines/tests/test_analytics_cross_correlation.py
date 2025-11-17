"""Tests for cross-correlation analytics helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ragtrader_pipelines.analytics.cross_correlation import (
    best_cross_correlation,
    cross_correlation_scores,
    normalize_aligned_series,
)


@pytest.fixture()
def base_series() -> pd.Series:
    """Return a smooth deterministic series for correlation experiments."""

    index = pd.RangeIndex(0, 40)
    values = np.sin(np.linspace(0, 4 * np.pi, index.stop, endpoint=False))
    return pd.Series(values, index=index, dtype=float)


def test_normalize_aligned_series_standardizes_inputs(base_series: pd.Series) -> None:
    """Aligned series should be zero-mean and unit-variance after normalisation."""

    follower = base_series * 2 + 5
    normalized_leader, normalized_follower = normalize_aligned_series(
        base_series, follower
    )

    assert np.isclose(float(normalized_leader.mean()), 0.0)
    assert np.isclose(float(normalized_follower.mean()), 0.0)
    assert np.isclose(float(normalized_leader.std(ddof=0)), 1.0)
    assert np.isclose(float(normalized_follower.std(ddof=0)), 1.0)


def test_best_cross_correlation_identifies_positive_lag(base_series: pd.Series) -> None:
    """Follower lagging the leader should yield a positive best lag."""

    follower = base_series.shift(3)
    result = best_cross_correlation(base_series, follower, max_lag=5, min_overlap=10)

    assert result is not None
    lag, score = result
    assert lag == 3
    assert score == pytest.approx(1.0, abs=1e-9)


def test_best_cross_correlation_identifies_negative_lag(base_series: pd.Series) -> None:
    """When the follower leads, the best lag should be negative."""

    follower = base_series.shift(-4)
    result = best_cross_correlation(base_series, follower, max_lag=6, min_overlap=10)

    assert result is not None
    lag, score = result
    assert lag == -4
    assert score == pytest.approx(1.0, abs=1e-9)


def test_cross_correlation_scores_ignore_insufficient_overlap(
    base_series: pd.Series,
) -> None:
    """Scores should skip lags that do not have enough overlapping observations."""

    follower = base_series.shift(1)
    scores = cross_correlation_scores(base_series, follower, max_lag=3, min_overlap=50)

    assert scores == {}
    assert (
        best_cross_correlation(
            base_series,
            follower,
            max_lag=3,
            min_overlap=50,
        )
        is None
    )


def test_best_cross_correlation_handles_missing_values(base_series: pd.Series) -> None:
    """NaNs in either series should be dropped before evaluating correlations."""

    leader = base_series.copy()
    follower = base_series.shift(2)

    leader.iloc[5:7] = np.nan
    follower.iloc[15] = np.nan

    result = best_cross_correlation(leader, follower, max_lag=4, min_overlap=5)

    assert result is not None
    lag, score = result
    assert lag == 2
    assert score == pytest.approx(1.0, abs=2e-3)
