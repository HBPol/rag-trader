"""Cross-correlation helpers for identifying leading/lagging relationships."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from .correlations import JoinStrategy

FloatArray = NDArray[np.floating[Any]]


def normalize_aligned_series(
    leader: pd.Series,
    follower: pd.Series,
    *,
    join: JoinStrategy = "inner",
) -> tuple[pd.Series, pd.Series]:
    """Align two series on a common index and apply z-score normalization."""

    aligned_leader, aligned_follower = leader.align(follower, join=join)
    combined = pd.concat(
        [aligned_leader.rename("leader"), aligned_follower.rename("follower")],
        axis=1,
    ).dropna()
    if combined.empty:
        empty_index = combined.index
        return (
            pd.Series(dtype=float, index=empty_index, name="leader"),
            pd.Series(dtype=float, index=empty_index, name="follower"),
        )

    normalized_columns: list[pd.Series] = []
    for column in ("leader", "follower"):
        values = combined[column].astype(float)
        mean = float(values.mean())
        std = float(values.std(ddof=0))
        if std == 0.0 or not np.isfinite(std):
            normalized = pd.Series(
                np.zeros(len(values), dtype=float), index=combined.index, name=column
            )
        else:
            normalized = (values - mean) / std
            normalized.name = column
        normalized_columns.append(normalized)

    normalized_leader, normalized_follower = normalized_columns
    return normalized_leader, normalized_follower


def _pearson_correlation(lhs: FloatArray, rhs: FloatArray) -> float | None:
    """Return the Pearson correlation for two equal-length arrays."""

    if lhs.size == 0 or rhs.size == 0:
        return None
    if lhs.shape != rhs.shape:
        raise ValueError("Correlation arrays must be the same length")

    lhs_centered = lhs - lhs.mean()
    rhs_centered = rhs - rhs.mean()
    denominator = np.sqrt(np.sum(lhs_centered**2) * np.sum(rhs_centered**2))
    if denominator == 0.0:
        return None
    return float(np.sum(lhs_centered * rhs_centered) / denominator)


def cross_correlation_scores(
    leader: pd.Series,
    follower: pd.Series,
    *,
    max_lag: int,
    join: JoinStrategy = "inner",
    min_overlap: int = 3,
) -> dict[int, float]:
    """Compute cross-correlation scores for lags in ``[-max_lag, max_lag]``."""

    if max_lag < 0:
        raise ValueError("max_lag must be non-negative")
    if min_overlap < 1:
        raise ValueError("min_overlap must be positive")

    normalized_leader, normalized_follower = normalize_aligned_series(
        leader, follower, join=join
    )
    if normalized_leader.empty or normalized_follower.empty:
        return {}

    leader_values = normalized_leader.to_numpy(dtype=float)
    follower_values = normalized_follower.to_numpy(dtype=float)
    length = leader_values.size
    if length != follower_values.size:
        raise ValueError("Aligned arrays must have the same length")

    scores: dict[int, float] = {}

    for lag in range(-max_lag, max_lag + 1):
        if lag > 0:
            if lag >= length:
                continue
            lhs_slice = leader_values[:-lag]
            rhs_slice = follower_values[lag:]
        elif lag < 0:
            offset = -lag
            if offset >= length:
                continue
            lhs_slice = leader_values[offset:]
            rhs_slice = follower_values[:-offset]
        else:
            lhs_slice = leader_values
            rhs_slice = follower_values

        if lhs_slice.size < min_overlap or rhs_slice.size < min_overlap:
            continue

        score = _pearson_correlation(lhs_slice, rhs_slice)
        if score is None:
            continue
        scores[lag] = score

    return scores


def best_cross_correlation(
    leader: pd.Series,
    follower: pd.Series,
    *,
    max_lag: int,
    join: JoinStrategy = "inner",
    min_overlap: int = 3,
) -> tuple[int, float] | None:
    """Return the ``(lag, score)`` pair with the strongest absolute correlation."""

    scores = cross_correlation_scores(
        leader,
        follower,
        max_lag=max_lag,
        join=join,
        min_overlap=min_overlap,
    )
    if not scores:
        return None

    lag, score = max(scores.items(), key=lambda item: abs(item[1]))
    return lag, score


__all__ = [
    "best_cross_correlation",
    "cross_correlation_scores",
    "normalize_aligned_series",
]
