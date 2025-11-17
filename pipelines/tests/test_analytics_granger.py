"""Unit tests for the Granger causality helpers (FR-8)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ragtrader_pipelines.analytics import (
    InsufficientSamplesError,
    NonStationarySeriesError,
    run_granger_causality,
)


def _generate_leader_follower(seed: int = 7) -> tuple[pd.Series, pd.Series]:
    """Create stationary leader/follower series with a clear causal signal."""

    rng = np.random.default_rng(seed)
    burn_in = 50
    total = burn_in + 240

    leader = rng.normal(loc=0.0, scale=1.0, size=total)
    follower = np.zeros(total, dtype=float)

    for idx in range(1, total):
        innovation = rng.normal(loc=0.0, scale=0.1)
        follower[idx] = 0.65 * leader[idx - 1] + 0.25 * follower[idx - 1] + innovation

    leader_series = pd.Series(leader[burn_in:], name="leader")
    follower_series = pd.Series(follower[burn_in:], name="follower")
    return leader_series, follower_series


def test_leader_causes_follower_detected() -> None:
    """The helper identifies the seeded leader→follower relationship."""

    leader, follower = _generate_leader_follower()

    result = run_granger_causality(leader, follower, max_lag=4, significance=0.01)

    assert result.max_lag == 4
    assert result.leader_stationarity.is_stationary
    assert result.follower_stationarity.is_stationary
    assert result.leader_to_follower.reject_null
    assert result.leader_to_follower.best_lag == 1
    assert result.leader_to_follower.p_value < 1e-4
    assert not result.follower_to_leader.reject_null
    assert result.follower_to_leader.p_value > 0.05
    assert result.inferred_direction() == "leader"


def test_requires_enough_history() -> None:
    """FR-8 mandates bounded-order tests, raising on insufficient samples."""

    leader = pd.Series([0.1, 0.2], name="leader")
    follower = pd.Series([0.3, 0.5], name="follower")

    with pytest.raises(
        InsufficientSamplesError, match="At least three aligned observations"
    ):
        run_granger_causality(leader, follower)


def test_rejects_non_stationary_inputs() -> None:
    """Non-stationary series should be rejected before running the tests."""

    trend = np.arange(100, dtype=float)
    leader = pd.Series(trend, name="leader")
    follower = pd.Series(trend + 0.5, name="follower")

    with pytest.raises(
        NonStationarySeriesError, match="Leader series is not stationary"
    ):
        run_granger_causality(leader, follower, max_lag=2)
