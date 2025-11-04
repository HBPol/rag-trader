"""Tests for the influence graph analytics helper."""

from __future__ import annotations

import pytest

from ragtrader_pipelines.analytics import (
    DirectionalGrangerResult,
    GrangerCausalitySummary,
    StationarityTestResult,
    build_influence_graph,
)


def _stationarity(name: str) -> StationarityTestResult:
    """Create a deterministic stationarity result for tests."""

    return StationarityTestResult(
        name=name,
        statistic=-3.5,
        p_value=0.01,
        n_obs=128,
        is_stationary=True,
    )


def test_build_influence_graph_composes_metrics_into_edges() -> None:
    """Correlation, lag, and Granger metrics should yield weighted edges."""

    correlations = {
        ("BTC", "ETH"): 0.9,
        ("BTC", "SOL"): 0.65,
    }
    cross_correlations = {
        ("BTC", "ETH"): (2, 0.7),
        ("SOL", "BTC"): (1, 0.6),
    }

    btc_eth_summary = GrangerCausalitySummary(
        max_lag=4,
        significance=0.05,
        leader_stationarity=_stationarity("BTC"),
        follower_stationarity=_stationarity("ETH"),
        leader_to_follower=DirectionalGrangerResult(
            direction="leader_causes_follower",
            best_lag=2,
            p_value=0.01,
            reject_null=True,
        ),
        follower_to_leader=DirectionalGrangerResult(
            direction="follower_causes_leader",
            best_lag=1,
            p_value=0.12,
            reject_null=False,
        ),
    )

    btc_sol_summary = GrangerCausalitySummary(
        max_lag=4,
        significance=0.05,
        leader_stationarity=_stationarity("BTC"),
        follower_stationarity=_stationarity("SOL"),
        leader_to_follower=DirectionalGrangerResult(
            direction="leader_causes_follower",
            best_lag=1,
            p_value=0.09,
            reject_null=False,
        ),
        follower_to_leader=DirectionalGrangerResult(
            direction="follower_causes_leader",
            best_lag=1,
            p_value=0.02,
            reject_null=True,
        ),
    )

    graph = build_influence_graph(
        correlations=correlations,
        cross_correlations=cross_correlations,
        granger_summaries={
            ("BTC", "ETH"): btc_eth_summary,
            ("BTC", "SOL"): btc_sol_summary,
        },
        correlation_threshold=0.6,
        cross_correlation_threshold=0.5,
        granger_significance=0.05,
        min_weight=0.2,
    )

    assert graph["nodes"] == ["BTC", "ETH", "SOL"]
    assert len(graph["edges"]) == 2

    btc_eth_edge = graph["edges"][0]
    assert btc_eth_edge["source"] == "BTC"
    assert btc_eth_edge["target"] == "ETH"
    assert btc_eth_edge["lag"] == 2
    assert btc_eth_edge["correlation"] == pytest.approx(0.9)
    assert btc_eth_edge["cross_correlation"] == pytest.approx(0.7)
    assert btc_eth_edge["granger_p_value"] == pytest.approx(0.01)
    assert btc_eth_edge["granger_reject_null"] is True
    assert btc_eth_edge["weight"] == pytest.approx(0.8, abs=1e-9)

    sol_btc_edge = graph["edges"][1]
    assert sol_btc_edge["source"] == "SOL"
    assert sol_btc_edge["target"] == "BTC"
    assert sol_btc_edge["lag"] == 1
    assert sol_btc_edge["correlation"] == pytest.approx(0.65)
    assert sol_btc_edge["cross_correlation"] == pytest.approx(0.6)
    assert sol_btc_edge["granger_p_value"] == pytest.approx(0.02)
    assert sol_btc_edge["granger_reject_null"] is True
    assert sol_btc_edge["weight"] == pytest.approx((0.65 + 0.6 + 0.6) / 3, abs=1e-9)


def test_build_influence_graph_filters_edges_below_thresholds() -> None:
    """Edges should be dropped when metrics fail configured thresholds."""

    correlations = {("BTC", "ETH"): 0.4}
    cross_correlations = {("BTC", "ETH"): (1, 0.2)}
    granger_summary = GrangerCausalitySummary(
        max_lag=4,
        significance=0.05,
        leader_stationarity=_stationarity("BTC"),
        follower_stationarity=_stationarity("ETH"),
        leader_to_follower=DirectionalGrangerResult(
            direction="leader_causes_follower",
            best_lag=1,
            p_value=0.2,
            reject_null=False,
        ),
        follower_to_leader=DirectionalGrangerResult(
            direction="follower_causes_leader",
            best_lag=1,
            p_value=0.4,
            reject_null=False,
        ),
    )

    graph = build_influence_graph(
        correlations=correlations,
        cross_correlations=cross_correlations,
        granger_summaries={("BTC", "ETH"): granger_summary},
        correlation_threshold=0.6,
        cross_correlation_threshold=0.5,
        granger_significance=0.05,
        min_weight=0.2,
    )

    assert graph == {"nodes": ["BTC", "ETH"], "edges": []}


def test_build_influence_graph_supports_granger_only_edges() -> None:
    """Strong Granger results should produce edges even without lag metrics."""

    correlations = {("BTC", "ETH"): 0.7}
    cross_correlations: dict[tuple[str, str], tuple[int, float]] = {}
    granger_summary = GrangerCausalitySummary(
        max_lag=4,
        significance=0.05,
        leader_stationarity=_stationarity("BTC"),
        follower_stationarity=_stationarity("ETH"),
        leader_to_follower=DirectionalGrangerResult(
            direction="leader_causes_follower",
            best_lag=2,
            p_value=0.01,
            reject_null=True,
        ),
        follower_to_leader=DirectionalGrangerResult(
            direction="follower_causes_leader",
            best_lag=1,
            p_value=0.3,
            reject_null=False,
        ),
    )

    graph = build_influence_graph(
        correlations=correlations,
        cross_correlations=cross_correlations,
        granger_summaries={("BTC", "ETH"): granger_summary},
        correlation_threshold=0.5,
        cross_correlation_threshold=0.4,
        granger_significance=0.05,
        min_weight=0.2,
    )

    assert graph["nodes"] == ["BTC", "ETH"]
    assert graph["edges"] == [
        {
            "source": "BTC",
            "target": "ETH",
            "weight": pytest.approx((0.7 + 0.8) / 2, abs=1e-9),
            "lag": None,
            "correlation": pytest.approx(0.7),
            "cross_correlation": None,
            "granger_p_value": pytest.approx(0.01),
            "granger_reject_null": True,
        }
    ]
