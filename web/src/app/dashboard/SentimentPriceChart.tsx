"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSentimentQuery } from "@/lib/queries/analytics";
import type { SentimentPoint } from "@/lib/schemas/sentiment";

const windows = ["1h", "4h", "24h", "7d"] as const;

export function formatFreshness(ageMinutes?: number | null): string {
  if (ageMinutes === undefined || ageMinutes === null) return "Unknown";
  if (!Number.isFinite(ageMinutes)) return "Unknown";
  if (ageMinutes < 1) return "<1 min ago";
  if (ageMinutes < 60) return `${ageMinutes.toFixed(1)} mins ago`;
  return `${(ageMinutes / 60).toFixed(1)} hrs ago`;
}

function formatTimeLabel(timestamp: string | null): string {
  if (!timestamp) return "Unknown";
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return "Unknown";
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPrice(priceUsd: number | null | undefined): string {
  if (typeof priceUsd !== "number" || !Number.isFinite(priceUsd)) {
    return "Unknown";
  }
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(priceUsd);
}

function toThousands(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value / 1000;
}

type ChartPoint = {
  label: string;
  priceThousands: number | null;
  zscore: number | null;
  rawTimestamp: string | null;
  priceUsd: number | null;
};

function buildChartPoints(series: SentimentPoint[] | undefined): ChartPoint[] {
  if (!series) return [];
  return series.map((point) => ({
    label: formatTimeLabel(point.ts),
    priceThousands: toThousands(point.price_usd ?? null),
    zscore: typeof point.zscore === "number" ? point.zscore : null,
    rawTimestamp: point.ts,
    priceUsd: point.price_usd ?? null,
  }));
}

function buildPath(points: Array<[number, number]>): string {
  return points
    .map(
      ([x, y], index) =>
        `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`,
    )
    .join(" ");
}

export type SentimentPriceChartProps = {
  symbol: string;
};

export default function SentimentPriceChart({
  symbol,
}: SentimentPriceChartProps) {
  const [window, setWindow] = useState<(typeof windows)[number]>("1h");
  const sentimentQuery = useSentimentQuery(symbol, window);

  const chartPoints = useMemo(
    () => buildChartPoints(sentimentQuery.data?.series),
    [sentimentQuery.data?.series],
  );

  const latestPoint = chartPoints.at(-1) ?? null;

  const priceValues = chartPoints
    .map((point) => point.priceThousands)
    .filter((value): value is number => value !== null);
  const zscoreValues = chartPoints
    .map((point) => point.zscore)
    .filter((value): value is number => value !== null);

  const priceMax = priceValues.length ? Math.max(...priceValues) : 1;
  const priceMin = priceValues.length ? Math.min(...priceValues) : 0;
  const zscoreMax = zscoreValues.length ? Math.max(...zscoreValues) : 1;
  const zscoreMin = zscoreValues.length ? Math.min(...zscoreValues) : -1;

  const width = 720;
  const height = 320;
  const padding = 48;
  const chartWidth = width - padding * 2;
  const chartHeight = height - padding * 2;

  const coordinates = chartPoints.map((point, index) => {
    const x =
      padding + (chartWidth / Math.max(chartPoints.length - 1, 1)) * index;
    const priceRange = priceMax - priceMin || 1;
    const zscoreRange = zscoreMax - zscoreMin || 1;
    const priceValue = point.priceThousands ?? priceMin;
    const zValue = point.zscore ?? zscoreMin;

    const priceY =
      padding +
      chartHeight -
      ((priceValue - priceMin) / priceRange) * chartHeight;
    const zscoreY =
      padding +
      chartHeight -
      ((zValue - zscoreMin) / zscoreRange) * chartHeight;

    return {
      x,
      priceY,
      zscoreY,
      label: point.label,
      priceThousands: point.priceThousands,
      zscore: point.zscore,
    };
  });

  const pricePath = buildPath(
    coordinates.map((point) => [point.x, point.priceY]),
  );
  const zscorePath = buildPath(
    coordinates.map((point) => [point.x, point.zscoreY]),
  );

  const hasData = chartPoints.some(
    (point) => point.priceThousands !== null || point.zscore !== null,
  );

  return (
    <Card className="border shadow-sm" data-testid="sentiment-chart-card">
      <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <CardTitle>Price vs. Sentiment</CardTitle>
          <p className="text-sm text-muted-foreground">
            Dual-axis composed chart showing {symbol} price (USD, thousands) and
            sentiment z-score.
          </p>
          <p className="text-xs text-muted-foreground">
            Freshness:{" "}
            {formatFreshness(sentimentQuery.data?.freshness.age_minutes)}
          </p>
        </div>
        <div
          className="flex flex-wrap gap-2"
          aria-label="Select analytics window"
        >
          {windows.map((value) => (
            <Button
              key={value}
              variant={value === window ? "default" : "outline"}
              size="sm"
              aria-pressed={value === window}
              onClick={() => setWindow(value)}
            >
              {value}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          className="flex flex-wrap gap-4 text-sm text-muted-foreground"
          aria-live="polite"
        >
          <span data-testid="price-summary">
            Latest price: {formatPrice(latestPoint?.priceUsd)}
          </span>
          <span data-testid="zscore-summary">
            Latest z-score: {latestPoint?.zscore?.toFixed(2) ?? "Unknown"}
          </span>
          <span className="text-xs">
            Price axis scaled to USD thousands (÷1000)
          </span>
        </div>

        {sentimentQuery.isLoading ? (
          <div
            className="h-72 w-full animate-pulse rounded-md bg-muted"
            role="status"
            aria-label="Loading sentiment chart"
          />
        ) : sentimentQuery.error ? (
          <div
            role="alert"
            aria-label="Unable to load sentiment chart"
            className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
          >
            Unable to load sentiment chart:{" "}
            {(sentimentQuery.error as Error)?.message ?? "Unknown error"}
          </div>
        ) : !hasData ? (
          <div
            className="rounded-md border border-dashed p-6 text-sm text-muted-foreground"
            role="status"
          >
            No sentiment or price data available for the selected window.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <svg
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label="Price and sentiment composed chart"
              className="min-w-full"
              data-testid="sentiment-chart-svg"
            >
              <defs>
                <linearGradient
                  id="priceLine"
                  x1="0%"
                  y1="0%"
                  x2="0%"
                  y2="100%"
                >
                  <stop offset="0%" stopColor="#0f172a" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#0f172a" stopOpacity="0.2" />
                </linearGradient>
                <linearGradient
                  id="zscoreLine"
                  x1="0%"
                  y1="0%"
                  x2="0%"
                  y2="100%"
                >
                  <stop offset="0%" stopColor="#6366f1" stopOpacity="0.8" />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity="0.2" />
                </linearGradient>
              </defs>

              <g>
                <line
                  x1={padding}
                  y1={padding}
                  x2={padding}
                  y2={height - padding}
                  stroke="#e5e7eb"
                />
                <text
                  x={padding - 10}
                  y={padding - 12}
                  textAnchor="start"
                  className="fill-current text-sm"
                  data-testid="price-axis-label"
                >
                  Price (USD, thousands)
                </text>
                <line
                  x1={width - padding}
                  y1={padding}
                  x2={width - padding}
                  y2={height - padding}
                  stroke="#e5e7eb"
                />
                <text
                  x={width - padding + 10}
                  y={padding - 12}
                  textAnchor="end"
                  className="fill-current text-sm"
                  data-testid="zscore-axis-label"
                >
                  Sentiment z-score
                </text>

                <line
                  x1={padding}
                  y1={height - padding}
                  x2={width - padding}
                  y2={height - padding}
                  stroke="#e5e7eb"
                />

                {coordinates.map((point) => (
                  <g key={`${point.label}-${point.x}`}>
                    <line
                      x1={point.x}
                      y1={height - padding}
                      x2={point.x}
                      y2={height - padding + 6}
                      stroke="#cbd5e1"
                    />
                    <text
                      x={point.x}
                      y={height - padding + 20}
                      textAnchor="middle"
                      className="fill-current text-xs"
                    >
                      {point.label}
                    </text>
                  </g>
                ))}
              </g>

              <path
                d={pricePath}
                fill="none"
                stroke="url(#priceLine)"
                strokeWidth={3}
                data-testid="price-path"
              />
              <path
                d={zscorePath}
                fill="none"
                stroke="url(#zscoreLine)"
                strokeWidth={3}
                data-testid="zscore-path"
              />

              {coordinates.map((point) => (
                <g key={`dots-${point.label}-${point.x}`}>
                  {typeof point.priceThousands === "number" && (
                    <circle
                      cx={point.x}
                      cy={point.priceY}
                      r={4}
                      fill="#0f172a"
                    />
                  )}
                  {typeof point.zscore === "number" && (
                    <rect
                      x={point.x - 4}
                      y={point.zscoreY - 8}
                      width={8}
                      height={16}
                      rx={2}
                      fill="#6366f1"
                      opacity={0.7}
                    />
                  )}
                </g>
              ))}
            </svg>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
