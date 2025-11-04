"""Helpers for building influence graphs from analytics metrics."""

from __future__ import annotations

from collections.abc import Mapping
from importlib import import_module
from typing import Any, TypedDict

from .granger import DirectionalGrangerResult, GrangerCausalitySummary

try:  # pragma: no cover - exercised when networkx is installed
    _networkx_module = import_module("networkx")
except ModuleNotFoundError:  # pragma: no cover - fallback for constrained environments
    _networkx_module = import_module("ragtrader_pipelines._compat.networkx")

nx: Any = _networkx_module

Pair = tuple[str, str]
LagResult = tuple[int, float]


class InfluenceEdge(TypedDict):
    """Serialized representation of a directed influence edge."""

    source: str
    target: str
    weight: float
    lag: int | None
    correlation: float | None
    cross_correlation: float | None
    granger_p_value: float | None
    granger_reject_null: bool | None


class InfluenceGraphPayload(TypedDict):
    """API-ready payload describing an influence graph."""

    nodes: list[str]
    edges: list[InfluenceEdge]


def build_influence_graph(
    correlations: Mapping[Pair, float] | None,
    cross_correlations: Mapping[Pair, LagResult] | None,
    granger_summaries: Mapping[Pair, GrangerCausalitySummary] | None,
    *,
    correlation_threshold: float = 0.5,
    cross_correlation_threshold: float = 0.5,
    granger_significance: float = 0.05,
    min_weight: float = 0.1,
) -> InfluenceGraphPayload:
    """Compose analytics metrics into a deterministic influence graph."""

    _validate_parameters(
        correlation_threshold,
        cross_correlation_threshold,
        granger_significance,
        min_weight,
    )

    correlation_map = dict(correlations or {})
    cross_map = dict(cross_correlations or {})
    granger_map = dict(granger_summaries or {})

    candidate_pairs: set[Pair] = set()
    for mapping in (correlation_map, cross_map, granger_map):
        for source, target in mapping:
            if source == target:
                continue
            candidate_pairs.add((source, target))
            candidate_pairs.add((target, source))

    nodes = sorted({asset for pair in candidate_pairs for asset in pair})
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)

    for source, target in sorted(candidate_pairs, key=lambda pair: (pair[0], pair[1])):
        if source == target:
            continue

        correlation = _lookup_symmetric_value(correlation_map, source, target)
        lag, cross_score = _resolve_cross_correlation(cross_map, source, target)
        granger_result, summary_significance = _resolve_granger(
            granger_map, source, target
        )

        if not _should_include_edge(
            correlation,
            cross_score,
            granger_result,
            correlation_threshold=correlation_threshold,
            cross_correlation_threshold=cross_correlation_threshold,
            granger_significance=granger_significance,
        ):
            continue

        significance_for_weight = _select_significance(
            granger_significance,
            summary_significance,
        )
        weight = _compute_weight(
            correlation,
            cross_score,
            granger_result,
            significance_for_weight,
        )
        if weight is None or weight < min_weight:
            continue

        graph.add_edge(
            source,
            target,
            weight=weight,
            lag=lag,
            correlation=correlation,
            cross_correlation=cross_score,
            granger_p_value=(
                granger_result.p_value if granger_result is not None else None
            ),
            granger_reject_null=(
                granger_result.reject_null if granger_result is not None else None
            ),
        )

    serialized_edges: list[InfluenceEdge] = []
    for source, target, data in sorted(
        graph.edges(data=True), key=lambda item: (item[0], item[1])
    ):
        edge: InfluenceEdge = {
            "source": source,
            "target": target,
            "weight": float(data["weight"]),
            "lag": data.get("lag"),
            "correlation": data.get("correlation"),
            "cross_correlation": data.get("cross_correlation"),
            "granger_p_value": data.get("granger_p_value"),
            "granger_reject_null": data.get("granger_reject_null"),
        }
        serialized_edges.append(edge)

    payload: InfluenceGraphPayload = {"nodes": nodes, "edges": serialized_edges}
    return payload


def _validate_parameters(
    correlation_threshold: float,
    cross_correlation_threshold: float,
    granger_significance: float,
    min_weight: float,
) -> None:
    if not 0.0 <= correlation_threshold <= 1.0:
        raise ValueError("correlation_threshold must be between 0 and 1")
    if not 0.0 <= cross_correlation_threshold <= 1.0:
        raise ValueError("cross_correlation_threshold must be between 0 and 1")
    if not 0.0 <= min_weight <= 1.0:
        raise ValueError("min_weight must be between 0 and 1")
    if not 0.0 < granger_significance < 1.0:
        raise ValueError("granger_significance must be between 0 and 1")


def _lookup_symmetric_value(
    mapping: Mapping[Pair, float],
    source: str,
    target: str,
) -> float | None:
    if (source, target) in mapping:
        return float(mapping[(source, target)])
    if (target, source) in mapping:
        return float(mapping[(target, source)])
    return None


def _resolve_cross_correlation(
    mapping: Mapping[Pair, LagResult],
    source: str,
    target: str,
) -> tuple[int | None, float | None]:
    if (source, target) not in mapping:
        return (None, None)

    lag_value, score = mapping[(source, target)]
    lag = int(lag_value)
    cross_score = float(score)
    if lag < 0:
        return (None, None)
    return (lag, cross_score)


def _resolve_granger(
    mapping: Mapping[Pair, GrangerCausalitySummary],
    source: str,
    target: str,
) -> tuple[DirectionalGrangerResult | None, float | None]:
    summary = mapping.get((source, target))
    if summary is not None:
        return summary.leader_to_follower, float(summary.significance)

    summary = mapping.get((target, source))
    if summary is not None:
        return summary.follower_to_leader, float(summary.significance)

    return None, None


def _should_include_edge(
    correlation: float | None,
    cross_score: float | None,
    granger_result: DirectionalGrangerResult | None,
    *,
    correlation_threshold: float,
    cross_correlation_threshold: float,
    granger_significance: float,
) -> bool:
    if cross_score is None and granger_result is None:
        return False
    if correlation is not None and abs(correlation) < correlation_threshold:
        return False
    if cross_score is not None and abs(cross_score) < cross_correlation_threshold:
        return False
    if granger_result is not None:
        if not granger_result.reject_null:
            return False
        if granger_result.p_value > granger_significance:
            return False
    return True


def _select_significance(
    configured_significance: float,
    summary_significance: float | None,
) -> float:
    if summary_significance is None:
        return configured_significance
    if summary_significance <= 0.0:
        return configured_significance
    return min(configured_significance, summary_significance)


def _compute_weight(
    correlation: float | None,
    cross_score: float | None,
    granger_result: DirectionalGrangerResult | None,
    significance: float,
) -> float | None:
    components: list[float] = []

    if correlation is not None:
        components.append(abs(float(correlation)))
    if cross_score is not None:
        components.append(abs(float(cross_score)))
    if granger_result is not None:
        if not granger_result.reject_null:
            return None
        normalized = 1.0 - min(granger_result.p_value / significance, 1.0)
        components.append(max(0.0, normalized))

    if not components:
        return None

    weight = sum(components) / len(components)
    return max(0.0, min(1.0, weight))


__all__ = [
    "InfluenceEdge",
    "InfluenceGraphPayload",
    "build_influence_graph",
]
