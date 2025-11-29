import math

import pandas as pd
import pytest

from ragtrader_pipelines.backtest.engine import BacktestEngine, ParsedStrategy


@pytest.fixture
def synthetic_ohlcv() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    data = {
        "open": [100, 101, 102, 103, 104],
        "high": [101, 103, 103, 104, 105],
        "low": [99, 100, 101, 102, 103],
        "close": [100, 102, 101, 103, 104],
        "volume": [1_000, 1_200, 1_100, 1_300, 1_250],
    }
    return pd.DataFrame(data, index=index)


@pytest.fixture
def parsed_strategy() -> ParsedStrategy:
    index = pd.date_range("2024-01-01", periods=5, freq="D")
    target_positions = pd.Series([0, 1, 1, 2, 0], index=index, name="position")
    return ParsedStrategy(symbol="SYN", target_positions=target_positions)


def test_engine_computes_equity_and_metrics(
    synthetic_ohlcv: pd.DataFrame, parsed_strategy: ParsedStrategy
) -> None:
    engine = BacktestEngine(initial_cash=10_000)

    result = engine.run(
        parsed_strategy,
        synthetic_ohlcv,
        slippage_bps=10,
        fee_bps=5,
    )

    assert result.equity_curve.index.equals(synthetic_ohlcv.index)
    assert math.isclose(result.equity_curve.iloc[-1], 10_002.3805, rel_tol=1e-9)
    assert result.metrics["total_return"] == pytest.approx(0.00023805, rel=1e-6)
    assert result.metrics["max_drawdown"] == pytest.approx(-0.0001153, rel=1e-6)
    assert result.metrics["sharpe"] == pytest.approx(6.7578171, rel=1e-6)
    assert result.metrics["trades"] == 3


def test_engine_enforces_runtime_budget(
    synthetic_ohlcv: pd.DataFrame, parsed_strategy: ParsedStrategy
) -> None:
    times = iter([0.0, 1.2])

    def fake_clock() -> float:
        return next(times)

    engine = BacktestEngine(initial_cash=1_000)

    with pytest.raises(TimeoutError):
        engine.run(
            parsed_strategy,
            synthetic_ohlcv,
            runtime_budget_secs=1.0,
            clock=fake_clock,
        )
