import pandas as pd
import pytest

from ragtrader_pipelines.backtest import BacktestEngine, ParsedStrategy


def _build_prices(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"close": pd.Series([100.0] * len(index), index=index)})


def test_backtest_engine_runs_without_trades():
    index = pd.date_range("2024-01-01", periods=3, freq="D")
    strategy = ParsedStrategy(
        symbol="TEST", target_positions=pd.Series(0.0, index=index)
    )

    engine = BacktestEngine(initial_cash=1_000)
    result = engine.run(strategy, _build_prices(index))

    assert list(result.equity_curve) == [1_000, 1_000, 1_000]
    assert result.metrics == {
        "total_return": 0.0,
        "max_drawdown": 0.0,
        "sharpe": 0.0,
        "trades": 0,
    }


def test_backtest_engine_enforces_runtime_budget():
    index = pd.date_range("2024-01-01", periods=2, freq="D")
    strategy = ParsedStrategy(
        symbol="TEST", target_positions=pd.Series(1.0, index=index)
    )
    engine = BacktestEngine()

    clock_values = iter([0.0, 2.0])

    def fake_clock() -> float:
        return next(clock_values)

    with pytest.raises(TimeoutError):
        engine.run(
            strategy,
            _build_prices(index),
            runtime_budget_secs=1.0,
            clock=fake_clock,
        )
