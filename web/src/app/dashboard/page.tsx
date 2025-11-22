"use client";

import { useMemo, useState } from "react";

import AuthGate from "@/components/AuthGate";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useCorrelationQuery,
  useEventsQuery,
  useGrangerQuery,
  useInfluenceGraphQuery,
  useSentimentQuery,
} from "@/lib/queries/analytics";
import type { CorrelationEntry } from "@/lib/schemas/correlation";
import Correlogram from "./Correlogram";
import LeadLagHeatmap from "./LeadLagHeatmap";
import SentimentPriceChart from "./SentimentPriceChart";
import { renderFreshness } from "./freshness";

const coins = ["BTC", "ETH", "SOL", "USDT", "USDC", "ARB", "DOGE"];
const analyticsWindows = ["1h", "4h", "1d"] as const;

function renderMetric(
  isLoading: boolean,
  error: unknown,
  value: string | number | null,
): string | number {
  if (isLoading) return "Loading...";
  if (error) return "Unavailable";
  if (value === null || value === undefined) return "No data";
  return value;
}

function formatCorrelationValue(
  entry: CorrelationEntry | null,
  primaryMetric: string | null,
): string | null {
  if (!entry) return null;
  const metricValue =
    entry.value ??
    (primaryMetric ? (entry.metrics[primaryMetric]?.value ?? null) : null);
  if (typeof metricValue === "number") {
    return metricValue.toFixed(3);
  }
  return null;
}

export default function DashboardPage() {
  const [baseCoin, setBaseCoin] = useState(coins[0]);
  const [quoteCoin, setQuoteCoin] = useState(coins[1]);
  const [analyticsWindow, setAnalyticsWindow] = useState<
    (typeof analyticsWindows)[number]
  >(analyticsWindows[0]);
  const [refreshedAt] = useState(() => new Date().toLocaleString());
  const environmentLabel = process.env.NEXT_PUBLIC_APP_ENV ?? "Local";

  const summaryText = useMemo(() => {
    return `Monitoring ${baseCoin}/${quoteCoin} for liquidity shifts, spreads, and cross-market volatility to guide the upcoming analytics modules.`;
  }, [baseCoin, quoteCoin]);

  const correlationQuery = useCorrelationQuery(baseCoin, analyticsWindow);
  const grangerQuery = useGrangerQuery(baseCoin, quoteCoin, analyticsWindow);
  const influenceGraphQuery = useInfluenceGraphQuery(
    baseCoin,
    quoteCoin,
    analyticsWindow,
  );
  const sentimentQuery = useSentimentQuery(baseCoin, analyticsWindow);
  const eventsQuery = useEventsQuery({ enabled: false });

  const placeholderWidgets = [
    "Market Heatmap",
    "Liquidity Funnels",
    "Custom Alerts",
    "Portfolio Blotter",
    "Retrieval Recipes",
    "Execution Quality",
  ];

  const handleSwap = () => {
    setBaseCoin(quoteCoin);
    setQuoteCoin(baseCoin);
  };

  return (
    <AuthGate>
      <main className="flex min-h-screen flex-col gap-8 bg-background p-6 text-foreground">
        <Card className="border shadow-sm">
          <CardHeader className="gap-6">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Environment
                  </span>
                  <span className="rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-primary">
                    {environmentLabel}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Refreshed {refreshedAt}
                </p>
              </div>
              <div className="flex w-full flex-col gap-3 sm:w-auto">
                <div className="flex flex-col gap-3 sm:flex-row">
                  <label className="flex flex-1 flex-col text-xs font-medium text-muted-foreground">
                    Base coin
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background p-2 text-sm text-foreground"
                      value={baseCoin}
                      onChange={(event) => setBaseCoin(event.target.value)}
                    >
                      {coins.map((coin) => (
                        <option key={coin} value={coin}>
                          {coin}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="flex items-end justify-center">
                    <Button
                      variant="outline"
                      size="icon"
                      className="mt-5"
                      onClick={handleSwap}
                    >
                      <span className="sr-only">Swap coins</span>⇄
                    </Button>
                  </div>
                  <label className="flex flex-1 flex-col text-xs font-medium text-muted-foreground">
                    Quote coin
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background p-2 text-sm text-foreground"
                      value={quoteCoin}
                      onChange={(event) => setQuoteCoin(event.target.value)}
                    >
                      {coins.map((coin) => (
                        <option key={coin} value={coin}>
                          {coin}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-1 flex-col text-xs font-medium text-muted-foreground">
                    Analytics window
                    <select
                      className="mt-1 w-full rounded-md border border-input bg-background p-2 text-sm text-foreground"
                      value={analyticsWindow}
                      onChange={(event) =>
                        setAnalyticsWindow(
                          event.target
                            .value as (typeof analyticsWindows)[number],
                        )
                      }
                    >
                      {analyticsWindows.map((window) => (
                        <option key={window} value={window}>
                          {window}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{summaryText}</p>
          </CardContent>
        </Card>

        <section className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <LeadLagHeatmap
              symbols={coins}
              leader={baseCoin}
              follower={quoteCoin}
              window={analyticsWindow}
              onLeaderChange={setBaseCoin}
              onFollowerChange={setQuoteCoin}
              onWindowChange={setAnalyticsWindow}
            />
          </div>
          <Correlogram
            leader={baseCoin}
            follower={quoteCoin}
            window={analyticsWindow}
          />
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <SentimentPriceChart symbol={baseCoin} />

          <Card className="border shadow-sm">
            <CardHeader>
              <CardTitle>Return vs Sentiment</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                Window:{" "}
                <span className="font-medium text-foreground">
                  {analyticsWindow}
                </span>
              </p>
              <p>
                Value:{" "}
                <span className="font-medium text-foreground">
                  {renderMetric(
                    correlationQuery.isLoading,
                    correlationQuery.error,
                    formatCorrelationValue(
                      correlationQuery.data?.entry ?? null,
                      correlationQuery.data?.payload.metric ?? null,
                    ),
                  )}
                </span>
              </p>
              <p>
                Freshness:{" "}
                {renderFreshness(
                  correlationQuery.data?.payload.freshness.age_minutes,
                )}
              </p>
            </CardContent>
          </Card>

          <Card className="border shadow-sm">
            <CardHeader>
              <CardTitle>Granger</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                P-value:{" "}
                <span className="font-medium text-foreground">
                  {renderMetric(
                    grangerQuery.isLoading,
                    grangerQuery.error,
                    grangerQuery.data?.edge?.p_value?.toFixed(4) ?? null,
                  )}
                </span>
              </p>
              <p>
                Reject Null:{" "}
                <span className="font-medium text-foreground">
                  {renderMetric(
                    grangerQuery.isLoading,
                    grangerQuery.error,
                    grangerQuery.data?.edge?.reject_null === null
                      ? null
                      : grangerQuery.data?.edge?.reject_null
                        ? "Yes"
                        : "No",
                  )}
                </span>
              </p>
              <p>
                Updated:{" "}
                {renderFreshness(
                  grangerQuery.data?.payload.freshness.age_minutes,
                )}
              </p>
            </CardContent>
          </Card>

          <Card className="border shadow-sm">
            <CardHeader>
              <CardTitle>Influence Graph</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                Edge Weight:{" "}
                <span className="font-medium text-foreground">
                  {renderMetric(
                    influenceGraphQuery.isLoading,
                    influenceGraphQuery.error,
                    influenceGraphQuery.data?.matchingEdge?.weight?.toFixed(
                      3,
                    ) ?? null,
                  )}
                </span>
              </p>
              <p>
                Nodes tracked:{" "}
                {influenceGraphQuery.data?.payload.graph.nodes.length ?? 0}
              </p>
              <p>
                Updated:{" "}
                {renderFreshness(
                  influenceGraphQuery.data?.payload.freshness.age_minutes,
                )}
              </p>
            </CardContent>
          </Card>

          <Card className="border shadow-sm">
            <CardHeader>
              <CardTitle>Sentiment</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                Observations:{" "}
                <span className="font-medium text-foreground">
                  {renderMetric(
                    sentimentQuery.isLoading,
                    sentimentQuery.error,
                    sentimentQuery.data?.series.length ?? null,
                  )}
                </span>
              </p>
              <p>
                Updated:{" "}
                {renderFreshness(sentimentQuery.data?.freshness.age_minutes)}
              </p>
            </CardContent>
          </Card>

          <Card className="border shadow-sm">
            <CardHeader>
              <CardTitle>Events</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                Endpoint wiring ready. Enable when backend is available to
                surface{" "}
                <span className="font-medium text-foreground">
                  {eventsQuery.data?.data.length ?? 0}
                </span>{" "}
                events.
              </p>
            </CardContent>
          </Card>
        </section>

        <section>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {placeholderWidgets.map((widget) => (
              <Card key={widget} className="border border-dashed bg-muted/20">
                <CardHeader>
                  <CardTitle>{widget}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">
                    Placeholder for the {widget.toLowerCase()} module.
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      </main>
    </AuthGate>
  );
}
