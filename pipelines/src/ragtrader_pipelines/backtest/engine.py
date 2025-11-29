"""Vectorized backtester for parsed strategy DSL instructions."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ParsedStrategy:
    """Normalized representation of a parsed DSL strategy.

    Attributes:
        symbol: Ticker symbol for the OHLCV series.
        target_positions: Desired unit exposure for each bar.
    """

    symbol: str
    target_positions: pd.Series


@dataclass(frozen=True)
class BacktestResult:
    """Result container for vectorized backtests."""

    equity_curve: pd.Series
    metrics: Mapping[str, float]


class BacktestEngine:
    """Run simple vectorized backtests with slippage and transaction fees."""

    def __init__(self, *, initial_cash: float = 100_000) -> None:
        self.initial_cash = float(initial_cash)

    def run(
        self,
        strategy: ParsedStrategy,
        ohlcv: pd.DataFrame,
        *,
        slippage_bps: float = 0.0,
        fee_bps: float = 0.0,
        runtime_budget_secs: float | None = None,
        clock: Callable[[], float] | None = None,
    ) -> BacktestResult:
        """Simulate equity curve from parsed DSL instructions.

        Args:
            strategy: Parsed strategy containing target positions per bar.
            ohlcv: OHLCV dataframe indexed by datetime.
            slippage_bps: Per-trade slippage in basis points.
            fee_bps: Per-trade fee in basis points applied to notional.
            runtime_budget_secs: Optional wall-clock limit.
            clock: Optional clock provider used for budgeting and tests.

        Raises:
            TimeoutError: When runtime_budget_secs is exceeded.
        """

        timer = clock or time.perf_counter
        start = timer()

        def _check_budget() -> None:
            if runtime_budget_secs is None:
                return
            elapsed = timer() - start
            if elapsed > runtime_budget_secs:
                raise TimeoutError(
                    f"Backtest exceeded runtime budget of {runtime_budget_secs} seconds"
                )

        positions = strategy.target_positions.reindex(ohlcv.index)
        positions = positions.ffill().fillna(0.0)
        close = ohlcv["close"].reindex(positions.index)

        slippage = slippage_bps / 10_000
        fees = fee_bps / 10_000

        trade_units = positions.diff().fillna(positions.iloc[0])
        price_with_slippage = close * (1 + np.sign(trade_units) * slippage)
        trade_values = trade_units * price_with_slippage
        fee_paid = trade_units.abs() * close * fees

        cash_changes = -(trade_values + fee_paid)
        cash = self.initial_cash + cash_changes.cumsum()
        equity_curve = cash + positions * close

        _check_budget()

        metrics = self._compute_metrics(equity_curve, trade_units)
        return BacktestResult(equity_curve=equity_curve, metrics=metrics)

    def _compute_metrics(
        self, equity_curve: pd.Series, trade_units: pd.Series
    ) -> dict[str, float]:
        total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)

        running_peak = equity_curve.cummax()
        drawdown = (equity_curve / running_peak) - 1
        max_drawdown = float(drawdown.min())

        log_returns = np.log(equity_curve / equity_curve.shift()).dropna()
        if log_returns.std(ddof=1) == 0:  # pragma: no cover - defensive guard
            sharpe = 0.0
        else:
            sharpe = float(log_returns.mean() / log_returns.std(ddof=1) * np.sqrt(252))

        trades = int((trade_units != 0).sum())

        return {
            "total_return": total_return,
            "max_drawdown": max_drawdown,
            "sharpe": sharpe,
            "trades": trades,
        }
