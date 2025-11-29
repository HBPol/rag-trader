from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fastapi.testclient import TestClient

from ragtrader_api.routes.strategy import create_strategy_app
from ragtrader_api.strategy.schema import StrategySchema


@dataclass
class _FakeBacktestResult:
    equity_curve: list[tuple[str, float]]
    metrics: Mapping[str, float]


class _FakeBacktester:
    def __init__(self, result: _FakeBacktestResult) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def run_backtest(
        self,
        payload: StrategySchema,
        *,
        slippage_bps: float = 0.0,
        fee_bps: float = 0.0,
    ) -> _FakeBacktestResult:
        self.calls.append(
            {
                "strategy": payload,
                "slippage_bps": slippage_bps,
                "fee_bps": fee_bps,
            }
        )
        return self.result


class _FakeConverter:
    def __init__(self, strategy: StrategySchema) -> None:
        self.strategy = strategy
        self.calls: list[str] = []

    def convert(self, instructions: str) -> StrategySchema:
        self.calls.append(instructions)
        return self.strategy


def _strategy_payload() -> dict[str, object]:
    return {
        "instrument": "BTC-USD",
        "sentiment_zscore": 1.2,
        "lead_lag": 15,
        "action": "long",
        "atr_stop": 2.5,
        "size_fraction": 0.4,
        "exits": [
            {"kind": "take_profit", "value": 3.0},
            {"kind": "stop_loss", "value": 1.5},
        ],
    }


def test_nl_to_dsl_route_translates_and_validates() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    converter = _FakeConverter(strategy)
    app = create_strategy_app(
        converter_provider=lambda: converter,
        backtester_provider=lambda: _FakeBacktester(
            _FakeBacktestResult(equity_curve=[], metrics={})
        ),
    )

    client = TestClient(app)
    response = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "long btc on bullish sentiment"},
        auth=("admin", "changeme"),
    )

    assert response.status_code == 200
    assert response.json() == strategy.model_dump()
    assert converter.calls == ["long btc on bullish sentiment"]


def test_backtest_runs_and_results_are_cached() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    result = _FakeBacktestResult(
        equity_curve=[("2024-01-01T00:00:00", 100_000.0)],
        metrics={"total_return": 0.15, "sharpe": 1.2},
    )
    backtester = _FakeBacktester(result)
    converter = _FakeConverter(strategy)
    app = create_strategy_app(
        converter_provider=lambda: converter,
        backtester_provider=lambda: backtester,
    )
    client = TestClient(app)

    response = client.post(
        "/strategy/backtests",
        json={
            "strategy": _strategy_payload(),
            "slippage_bps": 15.0,
            "fee_bps": 5.0,
        },
        auth=("admin", "changeme"),
    )

    assert response.status_code == 200
    payload = response.json()
    backtest_id = payload["backtest_id"]
    assert payload["metrics"] == result.metrics
    assert payload["equity_curve"] == [{"ts": "2024-01-01T00:00:00", "value": 100000.0}]

    assert backtester.calls[-1] == {
        "strategy": strategy,
        "slippage_bps": 15.0,
        "fee_bps": 5.0,
    }

    metrics = client.get(
        f"/strategy/backtests/{backtest_id}/metrics", auth=("admin", "changeme")
    )
    equity = client.get(
        f"/strategy/backtests/{backtest_id}/equity", auth=("admin", "changeme")
    )

    assert metrics.status_code == 200
    assert metrics.json() == {"backtest_id": backtest_id, "metrics": result.metrics}
    assert equity.status_code == 200
    assert equity.json() == {
        "backtest_id": backtest_id,
        "equity_curve": payload["equity_curve"],
    }


def test_rate_limiting_and_auth_enforced() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    converter = _FakeConverter(strategy)
    app = create_strategy_app(
        converter_provider=lambda: converter,
        backtester_provider=lambda: _FakeBacktester(
            _FakeBacktestResult(equity_curve=[], metrics={})
        ),
        rate_limit=1,
        window_seconds=3600,
    )
    client = TestClient(app)

    first = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "do something"},
        auth=("admin", "changeme"),
    )
    second = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "again"},
        auth=("admin", "changeme"),
    )
    unauthorized = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "again"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert unauthorized.status_code == 401
