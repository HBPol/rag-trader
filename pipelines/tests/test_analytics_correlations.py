"""Tests for rolling correlation analytics helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_series_equal
from pipelines.tests import get_analytics_fixture_path

from ragtrader_pipelines.analytics.correlations import rolling_pearson, rolling_spearman


@pytest.fixture()
def btc_eth_fixture() -> pd.DataFrame:
    """Load the deterministic BTC/ETH analytics fixture."""

    path = get_analytics_fixture_path("csv")
    frame = pd.read_csv(path, parse_dates=["timestamp"])
    return frame.set_index("timestamp")


def test_rolling_pearson_matches_expected_values(
    btc_eth_fixture: pd.DataFrame,
) -> None:
    """Verify rolling Pearson correlations against a synthetic control series."""

    closes = btc_eth_fixture["btc_close"].astype(float)
    control = closes + pd.Series([0.0, 1.0, 2.0, 3.0], index=closes.index)

    result = rolling_pearson(closes, control, window=3)
    expected = pd.Series(
        [np.nan, np.nan, 0.9999996072156032, 0.9998063577003271],
        index=closes.index,
        name="pearson",
    )

    assert_series_equal(
        result,
        expected,
        check_names=True,
        check_exact=False,
        atol=1e-9,
    )


def test_rolling_spearman_matches_expected_values(
    btc_eth_fixture: pd.DataFrame,
) -> None:
    """Spearman helper should match hand-verified rolling values."""

    btc = btc_eth_fixture["btc_close"].astype(float)
    eth = btc_eth_fixture["eth_close"].astype(float)

    result = rolling_spearman(btc, eth, window=3)
    expected = pd.Series([np.nan, np.nan, 1.0, 0.5], index=btc.index, name="spearman")

    assert_series_equal(
        result,
        expected,
        check_names=True,
        check_exact=False,
        atol=1e-9,
    )


def test_rolling_helpers_respect_min_periods_with_missing_values(
    btc_eth_fixture: pd.DataFrame,
) -> None:
    """Rolling helpers should honour min_periods and NaN-handling semantics."""

    closes = btc_eth_fixture["btc_close"].astype(float)
    control = closes + pd.Series([0.0, 1.0, 2.0, 3.0], index=closes.index)
    control.iloc[2] = np.nan

    strict = rolling_pearson(closes, control, window=3)
    assert strict.isna().all()

    relaxed = rolling_pearson(closes, control, window=3, min_periods=2)
    expected_relaxed = pd.Series(
        [np.nan, 1.0, 1.0, 1.0], index=closes.index, name="pearson"
    )
    assert_series_equal(
        relaxed,
        expected_relaxed,
        check_names=True,
        check_exact=False,
        atol=1e-9,
    )

    spearman_relaxed = rolling_spearman(closes, control, window=3, min_periods=2)
    expected_spearman = pd.Series(
        [np.nan, 1.0, 1.0, 1.0], index=closes.index, name="spearman"
    )
    assert_series_equal(
        spearman_relaxed,
        expected_spearman,
        check_names=True,
        check_exact=False,
        atol=1e-9,
    )
