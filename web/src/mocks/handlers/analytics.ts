import { http, HttpResponse } from "msw";

export const correlationResponse = {
  status: "ok",
  metric: "pearson",
  data: [
    {
      asset: "AAPL",
      window: "1d",
      metrics: {
        close: {
          value: 0.82,
          computed_ts: "2024-01-01T00:00:00Z",
        },
      },
      value: 0.82,
      computed_ts: "2024-01-01T00:00:00Z",
    },
    {
      asset: "MSFT",
      window: "1w",
      metrics: {
        close: {
          value: 0.64,
          computed_ts: "2024-01-02T00:00:00Z",
        },
      },
      value: 0.64,
      computed_ts: "2024-01-02T00:00:00Z",
    },
  ],
  last_updated: "2024-01-03T00:00:00Z",
  freshness: { age_minutes: 12 },
};

export const leadLagResponse = {
  status: "ok",
  data: [
    {
      leader: "BTC",
      follower: "ETH",
      window: "1h",
      best_lag_minutes: 15,
      strength: 0.82,
      sample_size: 240,
      computed_ts: "2024-01-05T00:00:00Z",
      correlogram: {
        best_lag_minutes: 15,
        buckets: [
          { lag_minutes: -30, correlation: -0.12, label: "-30m" },
          { lag_minutes: -15, correlation: 0.24, label: "-15m" },
          { lag_minutes: 0, correlation: 0.48, label: "0m" },
          { lag_minutes: 15, correlation: 0.82, label: "+15m" },
          { lag_minutes: 30, correlation: 0.63, label: "+30m" },
        ],
      },
    },
    {
      leader: "ETH",
      follower: "BTC",
      window: "1h",
      best_lag_minutes: 10,
      strength: 0.41,
      sample_size: 240,
      computed_ts: "2024-01-05T00:00:00Z",
      correlogram: {
        best_lag_minutes: 10,
        buckets: [
          { lag_minutes: -30, correlation: 0.16, label: "-30m" },
          { lag_minutes: -15, correlation: 0.22, label: "-15m" },
          { lag_minutes: 0, correlation: 0.38, label: "0m" },
          { lag_minutes: 10, correlation: 0.41, label: "+10m" },
          { lag_minutes: 20, correlation: 0.27, label: "+20m" },
        ],
      },
    },
    {
      leader: "BTC",
      follower: "SOL",
      window: "1h",
      best_lag_minutes: 25,
      strength: 0.67,
      sample_size: 180,
      computed_ts: "2024-01-05T00:00:00Z",
    },
    {
      leader: "SOL",
      follower: "BTC",
      window: "1h",
      best_lag_minutes: 20,
      strength: 0.36,
      sample_size: 180,
      computed_ts: "2024-01-05T00:00:00Z",
    },
    {
      leader: "ETH",
      follower: "SOL",
      window: "1h",
      best_lag_minutes: 30,
      strength: 0.28,
      sample_size: 120,
      computed_ts: "2024-01-05T00:00:00Z",
    },
    {
      leader: "SOL",
      follower: "ETH",
      window: "1h",
      best_lag_minutes: null,
      strength: null,
      sample_size: 60,
      computed_ts: "2024-01-05T00:00:00Z",
    },
    {
      leader: "BTC",
      follower: "ETH",
      window: "4h",
      best_lag_minutes: 45,
      strength: 0.63,
      sample_size: 96,
      computed_ts: "2024-01-06T04:00:00Z",
      correlogram: {
        best_lag_minutes: 45,
        buckets: [
          { lag_minutes: -60, correlation: -0.22, label: "-60m" },
          { lag_minutes: -30, correlation: 0.18, label: "-30m" },
          { lag_minutes: 0, correlation: 0.39, label: "0m" },
          { lag_minutes: 30, correlation: 0.55, label: "+30m" },
          { lag_minutes: 45, correlation: 0.63, label: "+45m" },
        ],
      },
    },
    {
      leader: "ETH",
      follower: "BTC",
      window: "4h",
      best_lag_minutes: 35,
      strength: -0.22,
      sample_size: 96,
      computed_ts: "2024-01-06T04:00:00Z",
    },
    {
      leader: "BTC",
      follower: "DOGE",
      window: "4h",
      best_lag_minutes: 50,
      strength: 0.18,
      sample_size: 64,
      computed_ts: "2024-01-06T04:00:00Z",
    },
    {
      leader: "DOGE",
      follower: "BTC",
      window: "4h",
      best_lag_minutes: null,
      strength: 0.12,
      sample_size: 64,
      computed_ts: "2024-01-06T04:00:00Z",
    },
    {
      leader: "SOL",
      follower: "DOGE",
      window: "4h",
      best_lag_minutes: 60,
      strength: 0.09,
      sample_size: 50,
      computed_ts: "2024-01-06T04:00:00Z",
    },
    {
      leader: "BTC",
      follower: "ETH",
      window: "1d",
      best_lag_minutes: 90,
      strength: 0.51,
      sample_size: 64,
      computed_ts: "2024-01-07T00:00:00Z",
    },
  ],
  last_updated: "2024-01-07T00:00:00Z",
  freshness: { age_minutes: 6 },
};

export const grangerResponse = {
  status: "ok",
  data: [
    {
      source: "AAPL",
      target: "MSFT",
      window: "1d",
      direction: "forward",
      p_value: 0.03,
      reject_null: true,
      computed_ts: "2024-01-07T00:00:00Z",
    },
    {
      source: "MSFT",
      target: "AAPL",
      window: "1w",
      direction: "forward",
      p_value: 0.12,
      reject_null: false,
      computed_ts: "2024-01-08T00:00:00Z",
    },
  ],
  last_updated: "2024-01-08T00:00:00Z",
  freshness: { age_minutes: 20 },
};

export const influenceGraphResponse = {
  status: "ok",
  graph: {
    nodes: ["BTC", "ETH", "SOL", "DOGE", "USDT", "XRP"],
    edges: [
      {
        source: "BTC",
        target: "ETH",
        window: "1h",
        weight: 0.76,
        previous_weight: 0.61,
        lag: 12,
        cross_correlation: 0.68,
        computed_ts: "2024-01-09T00:00:00Z",
      },
      {
        source: "ETH",
        target: "SOL",
        window: "1h",
        weight: 0.42,
        previous_weight: 0.4,
        lag: 18,
        correlation: 0.51,
        computed_ts: "2024-01-09T00:15:00Z",
      },
      {
        source: "SOL",
        target: "BTC",
        window: "1h",
        weight: -0.28,
        previous_weight: -0.3,
        lag: 10,
        correlation: -0.19,
        computed_ts: "2024-01-09T00:30:00Z",
      },
      {
        source: "ETH",
        target: "BTC",
        window: "4h",
        weight: 0.58,
        previous_weight: 0.47,
        lag: 45,
        granger_p_value: 0.04,
        granger_reject_null: true,
        computed_ts: "2024-01-09T04:00:00Z",
      },
      {
        source: "DOGE",
        target: "BTC",
        window: "4h",
        weight: 0.31,
        lag: 30,
        cross_correlation: 0.22,
        computed_ts: "2024-01-09T04:20:00Z",
      },
      {
        source: "USDT",
        target: "ETH",
        window: "1h",
        weight: 0.18,
        lag: 8,
        correlation: 0.23,
        computed_ts: "2024-01-09T00:45:00Z",
      },
      {
        source: "XRP",
        target: "SOL",
        window: "4h",
        weight: 0.22,
        lag: 60,
        correlation: 0.27,
        computed_ts: "2024-01-09T05:00:00Z",
      },
    ],
  },
  last_updated: "2024-01-10T00:00:00Z",
  freshness: { age_minutes: 25 },
};

export const sentimentResponse = {
  status: "ok",
  symbol: "AAPL",
  window: "1d",
  series: [
    {
      ts: "2024-01-01T10:00:00Z",
      polarity: 0.12,
      confidence: 0.9,
      zscore: 1.1,
      price_usd: 189.32,
      aspects: ["demand", "growth"],
    },
    {
      ts: "2024-01-01T11:00:00Z",
      polarity: -0.05,
      confidence: 0.7,
      zscore: -0.4,
      price_usd: 187.91,
      aspects: ["risk"],
    },
  ],
  last_updated: "2024-01-01T12:00:00Z",
  freshness: { age_minutes: 8 },
};

export const eventsResponse = {
  status: "ok",
  data: [
    {
      id: "evt-2",
      title: "Solana outage resolved, validators restart network",
      summary: "SOL validators coordinated a network restart after downtime.",
      source: "Status Page",
      url: "https://status.solana.com/outage",
      published_at: "2024-03-02T09:45:00Z",
      symbols: ["SOL", "USDC"],
      sentiment: 0.18,
    },
    {
      id: "evt-3",
      title: "Core inflation surprise sends risk assets lower",
      summary: "US CPI ran hotter than forecast, pressuring beta exposure.",
      source: "Macro Desk",
      url: "https://example.com/macro-cpi",
      published_at: "2024-02-29T12:00:00Z",
      symbols: ["BTC", "ETH"],
      sentiment: null,
    },
    {
      id: "evt-1",
      title: "Ethereum ETF approved with accelerated timeline",
      summary: "Regulators grant approval, boosting staking demand outlook.",
      source: "Newswire",
      url: "https://example.com/eth-etf",
      published_at: "2024-03-02T14:30:00Z",
      symbols: ["ETH"],
      sentiment: 0.92,
    },
  ],
  last_updated: "2024-03-02T15:00:00Z",
};

export const analyticsHandlers = [
  http.get("/analytics/correlation", () =>
    HttpResponse.json(correlationResponse),
  ),
  http.get("/analytics/leadlag", () => HttpResponse.json(leadLagResponse)),
  http.get("/analytics/granger", () => HttpResponse.json(grangerResponse)),
  http.get("/analytics/influence-graph", () =>
    HttpResponse.json(influenceGraphResponse),
  ),
  http.get("/sentiment", (req) => {
    const url = new URL(req.url);
    const symbol = url.searchParams.get("symbol") ?? "";
    const window = url.searchParams.get("window") ?? "";
    return HttpResponse.json({
      ...sentimentResponse,
      symbol,
      window,
    });
  }),
  http.get("/events", () => HttpResponse.json(eventsResponse)),
];
