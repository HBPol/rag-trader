"""Rolling correlation helpers for analytics workflows."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, cast

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from numpy.typing import NDArray

JoinStrategy = Literal["inner", "outer", "left", "right"]

FloatArray = NDArray[np.floating[Any]]


def _align_series(
    lhs: pd.Series, rhs: pd.Series, join: JoinStrategy
) -> tuple[pd.Series, pd.Series]:
    """Align two series on a common index."""

    aligned_lhs, aligned_rhs = lhs.align(rhs, join=join)
    return aligned_lhs, aligned_rhs


def rolling_pearson(
    lhs: pd.Series,
    rhs: pd.Series,
    window: int | str | pd.Timedelta | pd.DateOffset,
    *,
    min_periods: int | None = None,
    join: JoinStrategy = "inner",
) -> pd.Series:
    """Compute the rolling Pearson correlation between two series."""

    aligned_lhs, aligned_rhs = _align_series(lhs, rhs, join)
    combined = pd.concat([aligned_lhs.rename("lhs"), aligned_rhs.rename("rhs")], axis=1)
    windowed = combined.rolling(window=window, min_periods=min_periods)
    correlations = windowed.corr().loc[(slice(None), "lhs"), "rhs"].droplevel(1)
    correlations.name = "pearson"
    return correlations


def _average_tied_ranks(values: FloatArray) -> FloatArray:
    """Return average ranks for a 1D array, handling ties via averaging."""

    sorter = np.argsort(values, kind="mergesort")
    sorted_values = values[sorter]
    ranks = np.empty_like(sorted_values, dtype=float)
    _, start_indices, counts = np.unique(
        sorted_values, return_index=True, return_counts=True
    )
    cumulative = np.cumsum(counts)
    for start, end in zip(start_indices, cumulative, strict=False):
        slice_ranks = np.arange(start + 1, end + 1, dtype=float)
        ranks[start:end] = slice_ranks.mean()
    result = np.empty_like(ranks, dtype=float)
    result[sorter] = ranks
    return cast(FloatArray, result)


def _pearsonr(x: FloatArray, y: FloatArray) -> float:
    """Compute the Pearson correlation for two equally-sized vectors."""

    if x.size == 0 or y.size == 0:
        return np.nan
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    denominator = np.sqrt(np.sum(x_centered**2) * np.sum(y_centered**2))
    if denominator == 0:
        return np.nan
    return float(np.sum(x_centered * y_centered) / denominator)


def _spearman_for_window(window_values: Sequence[Sequence[float]]) -> float:
    """Compute the Spearman correlation for a 2D window."""

    values = np.asarray(window_values, dtype=float)
    if values.size == 0:
        return np.nan
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("Spearman window expects a 2-column array")
    lhs_ranks = _average_tied_ranks(values[:, 0])
    rhs_ranks = _average_tied_ranks(values[:, 1])
    return _pearsonr(lhs_ranks, rhs_ranks)


def rolling_spearman(
    lhs: pd.Series,
    rhs: pd.Series,
    window: int,
    *,
    min_periods: int | None = None,
    join: JoinStrategy = "inner",
) -> pd.Series:
    """Compute the rolling Spearman correlation between two series."""

    if not isinstance(window, int):  # pragma: no cover - defensive guard
        raise TypeError("Spearman rolling correlations require an integer window")
    if min_periods is None:
        min_periods = window

    aligned_lhs, aligned_rhs = _align_series(lhs, rhs, join)
    combined = pd.concat([aligned_lhs.rename("lhs"), aligned_rhs.rename("rhs")], axis=1)
    values = combined.to_numpy(dtype=float)
    results = np.full(len(combined), np.nan, dtype=float)
    required = max(min_periods, 2)

    for idx in range(len(combined)):
        start = max(0, idx - window + 1)
        window_slice = values[start : idx + 1]
        valid = window_slice[~np.isnan(window_slice).any(axis=1)]
        if valid.shape[0] < required:
            continue
        results[idx] = _spearman_for_window(valid)

    return pd.Series(results, index=combined.index, name="spearman")


__all__ = [
    "JoinStrategy",
    "rolling_pearson",
    "rolling_spearman",
]
