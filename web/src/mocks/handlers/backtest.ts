import { http, HttpResponse } from "msw";

export const dslResponse = {
  dsl: "MEAN_REVERSION_ENTRY:\n  WHEN close crosses below sma20\n  EXIT when close crosses above sma5",
  summary: "Mean reversion leg with volatility guard and simple exits.",
};

export const backtestResponse = {
  dsl: dslResponse.dsl,
  metrics: {
    total_return_pct: 5.1,
    sharpe: 1.62,
    max_drawdown_pct: -8.3,
    win_rate_pct: 58,
    avg_exposure: 0.63,
  },
  equity_curve: [
    { timestamp: "2024-01-01", equity: 100000 },
    { timestamp: "2024-01-02", equity: 102500 },
    { timestamp: "2024-01-03", equity: 103000 },
  ],
  drawdown_curve: [
    { timestamp: "2024-01-01", drawdown: 0 },
    { timestamp: "2024-01-02", drawdown: -0.01 },
    { timestamp: "2024-01-03", drawdown: -0.02 },
  ],
  exposure_curve: [
    { timestamp: "2024-01-01", gross: 0.5 },
    { timestamp: "2024-01-02", gross: 0.65 },
    { timestamp: "2024-01-03", gross: 0.6 },
  ],
};

export const backtestHandlers = [
  http.post("/studio/dsl", async () => {
    return HttpResponse.json(dslResponse);
  }),
  http.post("/studio/backtest", async () => {
    return HttpResponse.json(backtestResponse);
  }),
];
