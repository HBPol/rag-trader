"use client";

import { useMemo, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useBacktestMutation, useDslMutation } from "@/lib/queries/backtest";

const promptPlaceholder =
  "Go long when price crosses above the 20-day SMA and size based on volatility.";

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(2)}%`;
}

function formatRatio(value: number | null | undefined) {
  if (value === null || value === undefined) return "—";
  return value.toFixed(2);
}

function MetricTile({
  label,
  value,
  helper,
}: {
  label: string;
  value: string;
  helper?: string;
}) {
  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1">
        <p className="text-2xl font-semibold text-foreground">{value}</p>
        {helper ? (
          <p className="text-xs text-muted-foreground">{helper}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SeriesCard({
  title,
  helper,
  values,
  formatter,
  emptyLabel,
}: {
  title: string;
  helper: string;
  values: Array<{ timestamp: string; value: number }> | undefined;
  formatter: (value: number) => string;
  emptyLabel: string;
}) {
  const hasValues = values && values.length > 0;

  return (
    <Card className="border shadow-sm">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold text-foreground">
          {title}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{helper}</p>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {hasValues ? (
          <ul className="space-y-1">
            {values.map((point) => (
              <li
                key={`${title}-${point.timestamp}-${point.value}`}
                className="flex items-center justify-between rounded border border-muted px-3 py-2"
              >
                <span className="text-muted-foreground">
                  {new Date(point.timestamp).toLocaleDateString()}
                </span>
                <span className="font-semibold text-foreground">
                  {formatter(point.value)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="rounded border border-dashed border-muted bg-muted/20 p-3 text-muted-foreground">
            {emptyLabel}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function StudioPage() {
  const [prompt, setPrompt] = useState("");
  const [renderedDsl, setRenderedDsl] = useState("");

  const dslMutation = useDslMutation();
  const backtestMutation = useBacktestMutation();

  const backtestData = backtestMutation.data;

  const metrics = backtestData?.metrics;

  const equitySeries = useMemo(
    () =>
      backtestData?.equity_curve.map((point) => ({
        timestamp: point.timestamp,
        value: point.equity,
      })),
    [backtestData?.equity_curve],
  );

  const drawdownSeries = useMemo(
    () =>
      backtestData?.drawdown_curve.map((point) => ({
        timestamp: point.timestamp,
        value: point.drawdown,
      })),
    [backtestData?.drawdown_curve],
  );

  const exposureSeries = useMemo(
    () =>
      backtestData?.exposure_curve.map((point) => ({
        timestamp: point.timestamp,
        value: point.gross,
      })),
    [backtestData?.exposure_curve],
  );

  const handleRenderDsl = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    dslMutation.mutate(prompt, {
      onSuccess: (data) => setRenderedDsl(data.dsl),
    });
  };

  const handleRunBacktest = () => {
    const dsl = renderedDsl || dslMutation.data?.dsl || prompt;
    if (!dsl) return;
    backtestMutation.mutate(dsl);
  };

  const dslError = dslMutation.error as { message?: string } | null;
  const backtestError = backtestMutation.error as { message?: string } | null;

  return (
    <main className="flex min-h-screen flex-col gap-6 bg-background p-6 text-foreground">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight">
          Strategy Studio
        </h1>
        <p className="text-sm text-muted-foreground">
          Convert natural language prompts into executable DSL and preview a
          mock backtest.
        </p>
        <p className="text-xs font-medium uppercase tracking-wide text-amber-600">
          Educational use only. Not investment advice.
        </p>
      </header>

      <Card className="border shadow-sm">
        <CardHeader className="gap-2 pb-0">
          <CardTitle className="text-xl font-semibold">Prompt to DSL</CardTitle>
          <p className="text-sm text-muted-foreground">
            Enter a trading hypothesis, transform it into a sandbox DSL, and
            execute a sample backtest.
          </p>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
          <form className="space-y-3" onSubmit={handleRenderDsl}>
            <label className="flex flex-col gap-2 text-sm font-medium text-foreground">
              Natural language prompt
              <textarea
                className="min-h-[120px] w-full rounded-md border border-input bg-background p-3 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                placeholder={promptPlaceholder}
                aria-label="Natural language prompt"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
              />
            </label>
            <div className="flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={!prompt}>
                {dslMutation.isPending ? "Rendering..." : "Render DSL"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={handleRunBacktest}
                disabled={
                  backtestMutation.isPending ||
                  (!renderedDsl && !dslMutation.data && !prompt)
                }
              >
                {backtestMutation.isPending
                  ? "Running backtest..."
                  : "Run backtest"}
              </Button>
              <span className="text-xs text-muted-foreground">
                Runs are mocked with fixed fixtures to make UI review quick.
              </span>
            </div>
          </form>

          {dslError?.message ? (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {dslError.message}
            </div>
          ) : null}

          <label className="flex flex-col gap-2 text-sm font-medium text-foreground">
            Rendered DSL
            <textarea
              className="min-h-[160px] w-full rounded-md border border-dashed border-input bg-muted/20 p-3 text-sm text-foreground"
              aria-label="Rendered DSL"
              value={renderedDsl || dslMutation.data?.dsl || ""}
              readOnly
            />
          </label>

          {dslMutation.data?.summary ? (
            <p className="text-sm text-muted-foreground">
              {dslMutation.data.summary}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <section className="grid gap-4 md:grid-cols-5">
        <MetricTile
          label="Total return"
          value={formatPercent(metrics?.total_return_pct)}
          helper="Aggregate performance from the mock backtest"
        />
        <MetricTile
          label="Sharpe"
          value={formatRatio(metrics?.sharpe)}
          helper="Risk-adjusted return"
        />
        <MetricTile
          label="Max drawdown"
          value={formatPercent(metrics?.max_drawdown_pct)}
          helper="Peak-to-trough decline"
        />
        <MetricTile
          label="Win rate"
          value={formatPercent(metrics?.win_rate_pct)}
          helper="Percentage of profitable trades"
        />
        <MetricTile
          label="Avg exposure"
          value={formatPercent(
            metrics ? metrics.avg_exposure * 100 : undefined,
          )}
          helper="Average gross capital deployed"
        />
      </section>

      {backtestError?.message ? (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {backtestError.message}
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <SeriesCard
          title="Equity curve"
          helper="End-of-day equity snapshots"
          values={equitySeries}
          formatter={(value) => value.toLocaleString()}
          emptyLabel="Run a backtest to populate equity marks"
        />
        <SeriesCard
          title="Drawdown"
          helper="Peak-to-trough depth over time"
          values={drawdownSeries}
          formatter={(value) => formatPercent(value * 100)}
          emptyLabel="Drawdown timeline will appear after running a backtest"
        />
        <SeriesCard
          title="Exposure"
          helper="Gross exposure across the sample period"
          values={exposureSeries}
          formatter={(value) => formatPercent(value * 100)}
          emptyLabel="Exposure by date will render once a backtest has run"
        />
      </section>
    </main>
  );
}
