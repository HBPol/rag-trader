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
      leader: "AAPL",
      follower: "MSFT",
      window: "1d",
      best_lag_minutes: 30,
      strength: 0.71,
      computed_ts: "2024-01-05T00:00:00Z",
    },
    {
      leader: "MSFT",
      follower: "AAPL",
      window: "1w",
      best_lag_minutes: 60,
      strength: 0.44,
      computed_ts: "2024-01-06T00:00:00Z",
    },
  ],
  last_updated: "2024-01-06T00:00:00Z",
  freshness: { age_minutes: 18 },
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
    nodes: ["AAPL", "MSFT", "GOOG"],
    edges: [
      {
        source: "AAPL",
        target: "MSFT",
        window: "1d",
        weight: 0.4,
        computed_ts: "2024-01-09T00:00:00Z",
      },
      {
        source: "GOOG",
        target: "AAPL",
        window: "1w",
        weight: 0.29,
        computed_ts: "2024-01-10T00:00:00Z",
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
      id: "evt-1",
      title: "Earnings beat expectations",
      summary: "AAPL posts record revenue",
      source: "Newswire",
      url: "https://example.com/aapl-earnings",
      published_at: "2024-01-01T13:00:00Z",
      symbols: ["AAPL"],
      sentiment: 0.7,
    },
    {
      id: "evt-2",
      title: "MSFT unveils new cloud features",
      summary: "Azure expands AI capabilities",
      source: "Newswire",
      url: "https://example.com/msft-cloud",
      published_at: "2024-01-02T09:00:00Z",
      symbols: ["MSFT"],
      sentiment: 0.55,
    },
  ],
  last_updated: "2024-01-02T10:00:00Z",
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
