"use client";

import type { Dispatch, SetStateAction } from "react";
import { Fragment, useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLeadLagMatrixQuery } from "@/lib/queries/analytics";
import type { LeadLagEntry } from "@/lib/schemas/leadlag";
import { cn } from "@/lib/utils";
import { renderFreshness } from "./freshness";

const fallbackSymbols = ["BTC", "ETH", "SOL", "DOGE", "USDT"];

function normalizeSymbol(value: string): string {
  return value.trim().toUpperCase();
}

function strengthToBackground(
  strength: number | null | undefined,
  maxStrength: number,
): string | undefined {
  if (
    strength === null ||
    strength === undefined ||
    !Number.isFinite(maxStrength) ||
    maxStrength <= 0
  ) {
    return undefined;
  }

  const intensity = Math.min(Math.abs(strength) / maxStrength, 1);
  const alpha = 0.15 + 0.55 * intensity;
  if (strength < 0) {
    return `rgba(239, 68, 68, ${alpha.toFixed(2)})`;
  }
  return `rgba(22, 163, 74, ${alpha.toFixed(2)})`;
}

function buildEntriesMap(entries: LeadLagEntry[]): Map<string, LeadLagEntry> {
  const map = new Map<string, LeadLagEntry>();
  entries.forEach((entry) => {
    const leader = normalizeSymbol(entry.leader);
    const follower = normalizeSymbol(entry.follower);
    map.set(`${leader}->${follower}`, entry);
  });
  return map;
}

function formatLag(value: number | null | undefined): string {
  if (value === null || value === undefined) return "Unknown";
  if (!Number.isFinite(value)) return "Unknown";
  return `${value}m`;
}

function cellTooltip(
  leader: string,
  follower: string,
  entry: LeadLagEntry | null,
  freshnessMinutes: number | null | undefined,
): string {
  if (!entry) {
    return `${leader} → ${follower}: No lead/lag data available.`;
  }

  const lagText = formatLag(entry.best_lag_minutes);
  const strengthText =
    typeof entry.strength === "number" && Number.isFinite(entry.strength)
      ? entry.strength.toFixed(3)
      : "Unknown";
  const sampleText =
    entry.sample_size === null || entry.sample_size === undefined
      ? "Unknown"
      : `${entry.sample_size}`;

  return `${leader} → ${follower}\nLag: ${lagText}\nStrength: ${strengthText}\nSample size: ${sampleText}\nFreshness: ${renderFreshness(freshnessMinutes)}`;
}

export type LeadLagHeatmapProps<Window extends string = string> = {
  symbols?: string[];
  leader: string;
  follower: string;
  window: Window;
  onLeaderChange: (value: string) => void;
  onFollowerChange: (value: string) => void;
  onWindowChange: ((value: Window) => void) | Dispatch<SetStateAction<Window>>;
};

export default function LeadLagHeatmap<Window extends string = string>({
  symbols,
  leader,
  follower,
  window,
  onLeaderChange,
  onFollowerChange,
  onWindowChange,
}: LeadLagHeatmapProps<Window>) {
  const leadLagQuery = useLeadLagMatrixQuery(window, leader, follower);

  const normalizedSymbols = useMemo(() => {
    const provided = symbols?.length ? symbols : fallbackSymbols;
    const fromData = leadLagQuery.data?.entries
      ? leadLagQuery.data.entries.flatMap((entry) => [
          normalizeSymbol(entry.leader),
          normalizeSymbol(entry.follower),
        ])
      : [];
    const combined = new Set([
      ...provided.map((symbol) => normalizeSymbol(symbol)),
      ...fromData,
    ]);
    return Array.from(combined).sort();
  }, [symbols, leadLagQuery.data?.entries]);

  const entryMap = useMemo(() => {
    return buildEntriesMap(leadLagQuery.data?.entries ?? []);
  }, [leadLagQuery.data?.entries]);

  const maxStrength = useMemo(() => {
    const strengths = (leadLagQuery.data?.entries ?? [])
      .map((entry) => entry.strength)
      .filter((value): value is number => typeof value === "number");
    return strengths.length
      ? Math.max(...strengths.map((value) => Math.abs(value)))
      : 0;
  }, [leadLagQuery.data?.entries]);

  const freshnessMinutes = leadLagQuery.data?.payload.freshness.age_minutes;

  return (
    <Card className="border shadow-sm" data-testid="leadlag-heatmap">
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <CardTitle>Lead/Lag Heatmap</CardTitle>
            <p className="text-sm text-muted-foreground">
              Explore leader → follower strength by symbol and analytics window.
            </p>
            <p className="text-xs text-muted-foreground" aria-live="polite">
              Freshness: {renderFreshness(freshnessMinutes)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-foreground">
            <label className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Leader</span>
              <select
                aria-label="Leader symbol"
                className="rounded-md border border-input bg-background p-2"
                value={leader}
                onChange={(event) => onLeaderChange(event.target.value)}
              >
                {normalizedSymbols.map((symbol) => (
                  <option key={symbol} value={symbol}>
                    {symbol}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Follower</span>
              <select
                aria-label="Follower symbol"
                className="rounded-md border border-input bg-background p-2"
                value={follower}
                onChange={(event) => onFollowerChange(event.target.value)}
              >
                {normalizedSymbols.map((symbol) => (
                  <option key={symbol} value={symbol}>
                    {symbol}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Window</span>
              <select
                aria-label="Lead/lag window"
                className="rounded-md border border-input bg-background p-2"
                value={window}
                onChange={(event) =>
                  onWindowChange(event.target.value as Window)
                }
              >
                {Array.from(
                  new Set([
                    window,
                    ...(leadLagQuery.data?.entries?.map(
                      (entry) => entry.window,
                    ) ?? []),
                    "1h",
                    "4h",
                    "1d",
                  ]),
                )
                  .filter(Boolean)
                  .sort()
                  .map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
              </select>
            </label>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {leadLagQuery.isLoading ? (
          <div
            className="h-64 w-full animate-pulse rounded-md bg-muted"
            aria-label="Loading lead/lag heatmap"
          />
        ) : leadLagQuery.error ? (
          <p className="text-sm text-destructive">
            Failed to load lead/lag analytics. Please retry.
          </p>
        ) : !leadLagQuery.data?.entries.length ? (
          <p className="text-sm text-muted-foreground">
            No lead/lag data available.
          </p>
        ) : (
          <div className="overflow-auto">
            <div className="min-w-[520px]">
              <div
                className="grid"
                style={{
                  gridTemplateColumns: `120px repeat(${normalizedSymbols.length}, minmax(80px, 1fr))`,
                }}
              >
                <div className="sticky left-0 top-0 z-10 bg-background px-3 py-2 text-xs font-semibold text-muted-foreground">
                  Leader \ Follower
                </div>
                {normalizedSymbols.map((symbol) => (
                  <div
                    key={`header-${symbol}`}
                    className="px-3 py-2 text-center text-xs font-semibold uppercase text-muted-foreground"
                  >
                    {symbol}
                  </div>
                ))}
                {normalizedSymbols.map((leaderSymbol) => (
                  <Fragment key={leaderSymbol}>
                    <div className="sticky left-0 bg-background px-3 py-2 text-xs font-semibold uppercase text-muted-foreground">
                      {leaderSymbol}
                    </div>
                    {normalizedSymbols.map((followerSymbol) => {
                      const key = `${leaderSymbol}->${followerSymbol}`;
                      const entry = entryMap.get(key) ?? null;
                      const backgroundColor = strengthToBackground(
                        entry?.strength ?? null,
                        maxStrength,
                      );

                      return (
                        <div
                          key={`cell-${key}`}
                          data-testid={`leadlag-cell-${leaderSymbol}-${followerSymbol}`}
                          className={cn(
                            "flex h-16 flex-col items-center justify-center gap-1 border",
                            leaderSymbol === leader &&
                              followerSymbol === follower
                              ? "border-primary"
                              : "border-border",
                            backgroundColor
                              ? "text-foreground"
                              : "text-muted-foreground",
                          )}
                          style={{ backgroundColor }}
                          title={cellTooltip(
                            leaderSymbol,
                            followerSymbol,
                            entry,
                            freshnessMinutes,
                          )}
                        >
                          <span className="text-sm font-semibold">
                            {entry?.strength !== null &&
                            entry?.strength !== undefined
                              ? entry.strength.toFixed(2)
                              : "—"}
                          </span>
                          <span className="text-[11px] text-muted-foreground">
                            {entry?.best_lag_minutes != null
                              ? `${entry.best_lag_minutes}m lag`
                              : "No lag data"}
                          </span>
                        </div>
                      );
                    })}
                  </Fragment>
                ))}
              </div>
            </div>
          </div>
        )}
        <p className="mt-3 text-xs text-muted-foreground">
          Color intensity scales with absolute strength; green indicates leader
          outpaces follower, red indicates inverse moves.
        </p>
      </CardContent>
    </Card>
  );
}
