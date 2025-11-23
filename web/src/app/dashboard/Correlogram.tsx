"use client";

import { useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLeadLagQuery } from "@/lib/queries/analytics";
import type { CorrelogramBucket } from "@/lib/schemas/correlogram";
import ExplainabilityChip from "./ExplainabilityChip";

type CorrelogramProps = {
  leader: string;
  follower: string;
  window: string;
};

function normalizeLabel(bucket: CorrelogramBucket, index: number): string {
  if (bucket.label?.trim()) return bucket.label.trim();
  if (Number.isFinite(bucket.lag_minutes)) {
    const value = bucket.lag_minutes;
    if (value === 0) return "0m";
    return `${value > 0 ? "+" : ""}${value}m`;
  }
  return `bucket-${index + 1}`;
}

export default function Correlogram({
  leader,
  follower,
  window,
}: CorrelogramProps) {
  const leadLagQuery = useLeadLagQuery(leader, follower, window);
  const correlogram = leadLagQuery.data?.edge?.correlogram;
  const buckets = useMemo(
    () => correlogram?.buckets ?? [],
    [correlogram?.buckets],
  );
  const bestLag =
    correlogram?.best_lag_minutes ?? leadLagQuery.data?.edge?.best_lag_minutes;

  const maxMagnitude = useMemo(() => {
    const magnitudes = buckets
      .map((bucket) => bucket.correlation)
      .filter((value): value is number => typeof value === "number")
      .map((value) => Math.abs(value));
    return magnitudes.length ? Math.max(...magnitudes) : 0;
  }, [buckets]);

  const badgeContent = leadLagQuery.isLoading
    ? "Calculating best lag..."
    : bestLag === null || bestLag === undefined
      ? "No best lag available"
      : `${bestLag}m lag`;

  return (
    <Card className="border shadow-sm" data-testid="correlogram-card">
      <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <CardTitle>Lagged Correlation</CardTitle>
          <p className="text-sm text-muted-foreground">
            Correlation by lag buckets for {leader} → {follower} in {window}{" "}
            window.
          </p>
          <p className="text-xs text-muted-foreground" aria-live="polite">
            Leader {leader} vs follower {follower} · Window {window}
          </p>
        </div>
        <div className="flex items-center gap-2" aria-live="polite">
          <span
            data-testid="best-lag-badge"
            className="rounded-full bg-primary/10 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-primary"
          >
            {badgeContent}
          </span>
          <ExplainabilityChip
            metricId={`best-lag:${leader}:${follower}:${window}`}
            label="Best lag"
            className="ml-1"
          />
        </div>
      </CardHeader>
      <CardContent>
        {leadLagQuery.isLoading ? (
          <div
            className="h-64 w-full animate-pulse rounded-md bg-muted"
            role="status"
            aria-label="Loading correlogram"
            data-testid="correlogram-loading"
          />
        ) : leadLagQuery.error ? (
          <div
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
          >
            Failed to load correlogram data. Please retry.
          </div>
        ) : !buckets.length ? (
          <div
            className="rounded-md border border-dashed p-6 text-sm text-muted-foreground"
            role="status"
          >
            No correlogram data available for the selected leader/follower and
            window.
          </div>
        ) : (
          <div>
            <div
              className="flex h-72 items-end gap-4 overflow-x-auto"
              role="img"
              aria-label="Correlation by lag bucket"
            >
              {buckets.map((bucket, index) => {
                const label = normalizeLabel(bucket, index);
                const correlation = bucket.correlation ?? 0;
                const heightPercent =
                  maxMagnitude > 0
                    ? Math.min(
                        100,
                        (Math.abs(correlation) / maxMagnitude) * 100,
                      )
                    : 0;
                const isBestLag =
                  bestLag !== null &&
                  bestLag !== undefined &&
                  bestLag === bucket.lag_minutes;
                const barColor =
                  bucket.correlation == null
                    ? "bg-muted"
                    : bucket.correlation >= 0
                      ? "bg-emerald-500"
                      : "bg-red-500";

                return (
                  <div
                    key={`${label}-${bucket.lag_minutes}-${index}`}
                    className="flex flex-col items-center gap-2 text-xs"
                    data-testid={`correlogram-bucket-${label}`}
                  >
                    <div className="h-48 w-14 rounded-md border border-border bg-background shadow-sm">
                      <div className="flex h-full items-end p-1">
                        <div
                          data-testid={`correlogram-bar-${label}`}
                          className={`w-full rounded-sm ${barColor}`}
                          style={{ height: `${heightPercent}%` }}
                          aria-label={`${label} correlation ${bucket.correlation ?? "N/A"}`}
                        />
                      </div>
                    </div>
                    <span className="font-semibold text-foreground">
                      {label}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      {bucket.correlation === null ||
                      bucket.correlation === undefined
                        ? "N/A"
                        : bucket.correlation.toFixed(2)}
                    </span>
                    {isBestLag ? (
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
                        Best
                      </span>
                    ) : null}
                  </div>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Positive bars indicate the follower moves with the leader at that
              lag; negative bars indicate inverse moves.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
