from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fastapi.testclient import TestClient

from ragtrader_api.routes.strategy import create_strategy_app
from ragtrader_api.strategy.nl_to_dsl import (
    StrategyConversionError,
    UnsafeContentError,
)
from ragtrader_api.strategy.schema import StrategySchema

_USERNAME = "admin"
_PASSWORD = "changeme"


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
    def __init__(self, result: StrategySchema | Exception) -> None:
        self.result = result
        self.calls: list[str] = []

    def convert(self, instructions: str) -> StrategySchema:
        self.calls.append(instructions)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


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


def _client(
    *,
    converter_result: StrategySchema | Exception,
    backtest_result: _FakeBacktestResult | None = None,
    rate_limit: int = 30,
    window_seconds: int = 60,
) -> tuple[TestClient, _FakeConverter, _FakeBacktester]:
    StrategySchema.model_validate(_strategy_payload())
    converter = _FakeConverter(converter_result)
    backtester = _FakeBacktester(
        backtest_result or _FakeBacktestResult(equity_curve=[], metrics={})
    )
    app = create_strategy_app(
        username=_USERNAME,
        password=_PASSWORD,
        converter_provider=lambda: converter,
        backtester_provider=lambda: backtester,
        rate_limit=rate_limit,
        window_seconds=window_seconds,
    )
    return TestClient(app), converter, backtester


def test_nl_to_dsl_route_translates_and_validates() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    client, converter, _ = _client(converter_result=strategy)

    response = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "long btc on bullish sentiment"},
        auth=(_USERNAME, _PASSWORD),
    )

    assert response.status_code == 200
    assert response.json() == strategy.model_dump()
    assert converter.calls == ["long btc on bullish sentiment"]


def test_nl_to_dsl_reports_conversion_errors() -> None:
    error = StrategyConversionError("could not understand request")
    client, converter, _ = _client(converter_result=error)

    response = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "???"},
        auth=(_USERNAME, _PASSWORD),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == str(error)
    assert converter.calls == ["???"]


def test_nl_to_dsl_reports_unsafe_requests() -> None:
    error = UnsafeContentError("unsafe content detected")
    client, converter, _ = _client(converter_result=error)

    response = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "malicious"},
        auth=(_USERNAME, _PASSWORD),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == str(error)
    assert converter.calls == ["malicious"]


def test_backtest_runs_and_results_are_cached() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    result = _FakeBacktestResult(
        equity_curve=[("2024-01-01T00:00:00", 100_000.0)],
        metrics={"total_return": 0.15, "sharpe": 1.2},
    )
    client, converter, backtester = _client(
        converter_result=strategy, backtest_result=result
    )

    response = client.post(
        "/strategy/backtests",
        json={
            "strategy": _strategy_payload(),
            "slippage_bps": 15.0,
            "fee_bps": 5.0,
        },
        auth=(_USERNAME, _PASSWORD),
    )

    assert response.status_code == 200
    payload = response.json()
    backtest_id = payload["backtest_id"]
    assert payload["metrics"] == result.metrics
    assert payload["equity_curve"] == [{"ts": "2024-01-01T00:00:00", "value": 100000.0}]
    assert converter.calls == []
    assert backtester.calls[-1] == {
        "strategy": strategy,
        "slippage_bps": 15.0,
        "fee_bps": 5.0,
    }

    metrics = client.get(
        f"/strategy/backtests/{backtest_id}/metrics", auth=(_USERNAME, _PASSWORD)
    )
    equity = client.get(
        f"/strategy/backtests/{backtest_id}/equity", auth=(_USERNAME, _PASSWORD)
    )

    assert metrics.status_code == 200
    assert metrics.json() == {"backtest_id": backtest_id, "metrics": result.metrics}
    assert equity.status_code == 200
    assert equity.json() == {
        "backtest_id": backtest_id,
        "equity_curve": payload["equity_curve"],
    }


def test_backtest_fetch_routes_return_404_for_missing_entries() -> None:
    client, _, _ = _client(
        converter_result=StrategySchema.model_validate(_strategy_payload())
    )
    missing_id = "does-not-exist"

    metrics = client.get(
        f"/strategy/backtests/{missing_id}/metrics", auth=(_USERNAME, _PASSWORD)
    )
    equity = client.get(
        f"/strategy/backtests/{missing_id}/equity", auth=(_USERNAME, _PASSWORD)
    )

    assert metrics.status_code == 404
    assert equity.status_code == 404
    assert metrics.json() == {"detail": "Backtest not found"}
    assert equity.json() == {"detail": "Backtest not found"}


def test_basic_auth_is_enforced() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    client, _, _ = _client(converter_result=strategy)

    response = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "long btc"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
    assert response.headers.get("WWW-Authenticate") == "Basic"


def test_basic_auth_accepts_valid_credentials() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    client, _, _ = _client(converter_result=strategy)

    response = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "long btc"},
        auth=(_USERNAME, _PASSWORD),
    )

    assert response.status_code == 200
    assert response.json() == strategy.model_dump()


def test_basic_auth_rejects_invalid_credentials() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    client, _, _ = _client(converter_result=strategy)

    response = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "long btc"},
        auth=(_USERNAME, "wrong"),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"
    assert response.headers.get("WWW-Authenticate") == "Basic"


def test_rate_limiting_applies_across_requests() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    client, _, _ = _client(converter_result=strategy, rate_limit=1, window_seconds=1)

    first = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "do something"},
        auth=(_USERNAME, _PASSWORD),
    )
    second = client.post(
        "/strategy/nl-to-dsl",
        json={"instructions": "again"},
        auth=(_USERNAME, _PASSWORD),
    )

    assert first.status_code == 200
    assert second.status_code == 429


def test_backtest_serializes_mapping_equity_curves() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    result = _FakeBacktestResult(
        equity_curve={"2024-01-01": 100_000.0, "2024-01-02": 101_500.0},
        metrics={"total_return": 0.015},
    )
    client, _, _ = _client(converter_result=strategy, backtest_result=result)

    response = client.post(
        "/strategy/backtests",
        json={"strategy": _strategy_payload()},
        auth=(_USERNAME, _PASSWORD),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["equity_curve"] == [
        {"ts": "2024-01-01", "value": 100000.0},
        {"ts": "2024-01-02", "value": 101500.0},
    ]
    metrics_response = client.get(
        f"/strategy/backtests/{payload['backtest_id']}/metrics",
        auth=(_USERNAME, _PASSWORD),
    )
    equity_response = client.get(
        f"/strategy/backtests/{payload['backtest_id']}/equity",
        auth=(_USERNAME, _PASSWORD),
    )

    assert metrics_response.status_code == 200
    assert metrics_response.json()["metrics"] == result.metrics
    assert equity_response.status_code == 200
    assert equity_response.json()["equity_curve"] == payload["equity_curve"]


def test_backtest_serializes_sequence_equity_curves() -> None:
    strategy = StrategySchema.model_validate(_strategy_payload())
    result = _FakeBacktestResult(
        equity_curve=[
            {"ts": "2024-01-01", "value": 100_000.0},
            ["2024-01-02", 102_000],
        ],
        metrics={"total_return": 0.02},
    )
    client, _, _ = _client(converter_result=strategy, backtest_result=result)

    response = client.post(
        "/strategy/backtests",
        json={"strategy": _strategy_payload()},
        auth=(_USERNAME, _PASSWORD),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["equity_curve"] == [
        {"ts": "2024-01-01", "value": 100000.0},
        {"ts": "2024-01-02", "value": 102000.0},
    ]
