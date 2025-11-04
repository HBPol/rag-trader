"""Analytics helpers for RAGTrader pipelines."""

from .correlations import JoinStrategy, rolling_pearson, rolling_spearman
from .cross_correlation import (
    best_cross_correlation,
    cross_correlation_scores,
    normalize_aligned_series,
)
from .granger import (
    Direction,
    DirectionalGrangerResult,
    GrangerCausalityError,
    GrangerCausalitySummary,
    InsufficientSamplesError,
    NonStationarySeriesError,
    StationarityTestResult,
    run_granger_causality,
    test_stationarity,
)
from .influence_graph import InfluenceEdge, InfluenceGraphPayload, build_influence_graph

__all__ = [
    "JoinStrategy",
    "best_cross_correlation",
    "cross_correlation_scores",
    "Direction",
    "DirectionalGrangerResult",
    "InfluenceEdge",
    "InfluenceGraphPayload",
    "GrangerCausalityError",
    "GrangerCausalitySummary",
    "InsufficientSamplesError",
    "NonStationarySeriesError",
    "build_influence_graph",
    "normalize_aligned_series",
    "rolling_pearson",
    "rolling_spearman",
    "StationarityTestResult",
    "run_granger_causality",
    "test_stationarity",
]
