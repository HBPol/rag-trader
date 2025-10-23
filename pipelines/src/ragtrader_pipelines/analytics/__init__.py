"""Analytics helpers for RAGTrader pipelines."""

from .correlations import JoinStrategy, rolling_pearson, rolling_spearman
from .cross_correlation import (
    best_cross_correlation,
    cross_correlation_scores,
    normalize_aligned_series,
)

__all__ = [
    "JoinStrategy",
    "best_cross_correlation",
    "cross_correlation_scores",
    "normalize_aligned_series",
    "rolling_pearson",
    "rolling_spearman",
]
