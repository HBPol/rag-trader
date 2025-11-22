import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import InfluenceGraph from "@/app/dashboard/InfluenceGraph";
import { AuthContext } from "@/app/providers";

function renderWithProviders(children: ReactNode, queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={{ isAuthenticated: true }}>
        {children}
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

function InfluenceGraphHarness() {
  const [base, setBase] = useState("BTC");
  const [quote, setQuote] = useState("ETH");
  const [windowSize, setWindowSize] = useState("1h");
  const symbols = ["BTC", "ETH", "SOL", "DOGE", "USDT"];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Base</span>
          <select
            aria-label="Base coin"
            value={base}
            onChange={(event) => setBase(event.target.value)}
          >
            {symbols.map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Quote</span>
          <select
            aria-label="Quote coin"
            value={quote}
            onChange={(event) => setQuote(event.target.value)}
          >
            {symbols.map((symbol) => (
              <option key={symbol} value={symbol}>
                {symbol}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Window</span>
          <select
            aria-label="Influence window"
            value={windowSize}
            onChange={(event) => setWindowSize(event.target.value)}
          >
            {["1h", "4h"].map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>
      <InfluenceGraph source={base} target={quote} windowSize={windowSize} />
    </div>
  );
}

describe("InfluenceGraph", () => {
  it("renders nodes and edges from the fixture", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { container } = renderWithProviders(
      <InfluenceGraph source="BTC" target="ETH" windowSize="1h" />,
      queryClient,
    );

    await screen.findByTestId("influence-node-BTC");
    const nodes = container.querySelectorAll(
      '[data-testid^="influence-node-"]',
    );
    const edges = container.querySelectorAll(
      '[data-testid^="influence-edge-"]',
    );

    expect(nodes.length).toBe(6);
    expect(edges.length).toBe(7);
  });

  it("exposes zoom and pan controls", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    renderWithProviders(
      <InfluenceGraph source="BTC" target="ETH" windowSize="1h" />,
      queryClient,
    );

    await screen.findByTestId("influence-graph-canvas");
    expect(screen.getByLabelText("Zoom in")).toBeInTheDocument();
    expect(screen.getByLabelText("Zoom out")).toBeInTheDocument();
    expect(screen.getByLabelText("Reset view")).toBeInTheDocument();
  });

  it("creates distinct query keys as selectors change", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    renderWithProviders(<InfluenceGraphHarness />, queryClient);

    await screen.findByTestId("influence-node-BTC");

    fireEvent.change(screen.getByLabelText("Base coin"), {
      target: { value: "SOL" },
    });
    fireEvent.change(screen.getByLabelText("Quote coin"), {
      target: { value: "DOGE" },
    });
    fireEvent.change(screen.getByLabelText("Influence window"), {
      target: { value: "4h" },
    });

    await waitFor(() => {
      const keys = queryClient
        .getQueryCache()
        .findAll({ queryKey: ["analytics", "influence-graph"] })
        .map((query) => query.queryKey);

      expect(keys).toContainEqual([
        "analytics",
        "influence-graph",
        "BTC",
        "ETH",
        "1h",
      ]);
      expect(keys).toContainEqual([
        "analytics",
        "influence-graph",
        "SOL",
        "DOGE",
        "4h",
      ]);
    });
  });
});
