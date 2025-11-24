import { expect, type Locator, type Page, type Route } from "@playwright/test";

import {
  correlationResponse,
  leadLagResponse,
  grangerResponse,
  influenceGraphResponse,
  eventsResponse,
  explanationsResponse,
  sentimentResponse,
} from "../src/mocks/handlers/analytics";
import type { SentimentResponse } from "../src/lib/schemas/sentiment";

const sentimentByWindow: Record<string, SentimentResponse> = {
  "1h": {
    ...sentimentResponse,
    window: "1h",
    series: [
      {
        ...sentimentResponse.series[0],
        ts: "2024-01-01T10:00:00Z",
        price_usd: 189.32,
        zscore: 1.1,
      },
      {
        ...sentimentResponse.series[1],
        ts: "2024-01-01T11:00:00Z",
        price_usd: 187.91,
        zscore: -0.4,
      },
    ],
  },
  "4h": {
    ...sentimentResponse,
    window: "4h",
    series: [
      {
        ...sentimentResponse.series[0],
        ts: "2024-01-02T08:00:00Z",
        price_usd: 201.45,
        zscore: 0.64,
      },
      {
        ...sentimentResponse.series[1],
        ts: "2024-01-02T12:00:00Z",
        price_usd: 209.88,
        zscore: 1.34,
      },
    ],
    freshness: { age_minutes: 12 },
  },
};

function fulfillJson(route: Route, json: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(json),
  });
}

export async function installDashboardMocks(page: Page) {
  await page.route("**/analytics/correlation", (route) =>
    fulfillJson(route, correlationResponse),
  );
  await page.route("**/analytics/leadlag", (route) =>
    fulfillJson(route, leadLagResponse),
  );
  await page.route("**/analytics/granger", (route) =>
    fulfillJson(route, grangerResponse),
  );
  await page.route("**/analytics/influence-graph", (route) =>
    fulfillJson(route, influenceGraphResponse),
  );
  await page.route("**/events", (route) => fulfillJson(route, eventsResponse));
  await page.route("**/explanations**", (route) => {
    const url = new URL(route.request().url());
    const id = url.searchParams.get("id");
    const match = explanationsResponse.data.find((entry) => entry.id === id);
    if (!match) {
      return route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ message: "Not found" }),
      });
    }
    return fulfillJson(route, explanationsResponse);
  });

  await page.route("**/sentiment**", (route) => {
    const url = new URL(route.request().url());
    const window = url.searchParams.get("window") ?? "1h";
    const symbol = url.searchParams.get("symbol") ?? sentimentResponse.symbol;
    const payload = sentimentByWindow[window] ?? sentimentByWindow["1h"];

    return fulfillJson(route, {
      ...payload,
      symbol,
      window,
    });
  });
}

export async function authenticateThroughMockProvider(page: Page) {
  await page.goto("/");
  await expect(page.getByText(/Mock auth preview/i)).toBeVisible();
  await page.getByRole("link", { name: /Enter dashboard/i }).click();
  await page.waitForURL("**/dashboard");
  await page.waitForSelector("main");
}

export function dashboardSelectors(page: Page): {
  explainChip: () => Locator;
  influenceEdge: (source: string, target: string) => Locator;
  sentimentWindow: (label: string) => Locator;
  priceSummary: () => Locator;
  zscoreSummary: () => Locator;
  eventCard: (title: string) => Locator;
} {
  return {
    explainChip: () =>
      page.getByRole("button", { name: /Explain Correlation/i }),
    influenceEdge: (source: string, target: string) =>
      page.getByTestId(`influence-edge-${source}-${target}`),
    sentimentWindow: (label: string) =>
      page.getByRole("button", { name: label, exact: true }),
    priceSummary: () => page.getByTestId("price-summary"),
    zscoreSummary: () => page.getByTestId("zscore-summary"),
    eventCard: (title: string) =>
      page.getByTestId("event-card").filter({ hasText: title }),
  };
}
