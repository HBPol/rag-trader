"use client";

import { useMemo, useState } from "react";

import AuthGate from "@/components/AuthGate";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const coins = ["BTC", "ETH", "SOL", "USDT", "USDC", "ARB", "DOGE"];

export default function DashboardPage() {
  const [baseCoin, setBaseCoin] = useState(coins[0]);
  const [quoteCoin, setQuoteCoin] = useState(coins[1]);
  const [refreshedAt] = useState(() => new Date().toLocaleString());

  const environmentLabel = process.env.NEXT_PUBLIC_APP_ENV ?? "Local";

  const summaryText = useMemo(() => {
    return `Monitoring ${baseCoin}/${quoteCoin} for liquidity shifts, spreads, and cross-market volatility to guide the upcoming analytics modules.`;
  }, [baseCoin, quoteCoin]);

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
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{summaryText}</p>
          </CardContent>
        </Card>

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
