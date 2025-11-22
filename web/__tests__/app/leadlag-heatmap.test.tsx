import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import LeadLagHeatmap from "@/app/dashboard/LeadLagHeatmap";
import { AuthContext } from "@/app/providers";

const symbols = ["BTC", "ETH", "SOL", "DOGE", "USDT"];

function renderWithProviders(children: ReactNode, queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={{ isAuthenticated: true }}>
        {children}
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

function HeatmapHarness({
  initialLeader = "BTC",
  initialFollower = "ETH",
  initialWindow = "1h",
}: {
  initialLeader?: string;
  initialFollower?: string;
  initialWindow?: string;
}) {
  const [leader, setLeader] = useState(initialLeader);
  const [follower, setFollower] = useState(initialFollower);
  const [window, setWindow] = useState(initialWindow);

  return (
    <LeadLagHeatmap
      symbols={symbols}
      leader={leader}
      follower={follower}
      window={window}
      onLeaderChange={setLeader}
      onFollowerChange={setFollower}
      onWindowChange={setWindow}
    />
  );
}

describe("LeadLagHeatmap", () => {
  it("scales color intensity with strength", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    renderWithProviders(<HeatmapHarness />, queryClient);

    const strongCell = await screen.findByTestId("leadlag-cell-BTC-ETH");
    const weakerCell = await screen.findByTestId("leadlag-cell-ETH-SOL");

    const parseAlpha = (value: string) => {
      const match = value.match(/rgba\([^,]+,[^,]+,[^,]+,\s*([0-9.]+)\)/);
      return match ? Number.parseFloat(match[1]) : null;
    };

    expect(parseAlpha(strongCell.style.backgroundColor)).toBeCloseTo(0.7, 2);
    expect(parseAlpha(weakerCell.style.backgroundColor)).toBeCloseTo(0.34, 2);
  });

  it("renders tooltip details for a populated cell", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    renderWithProviders(<HeatmapHarness />, queryClient);

    const cell = await screen.findByTestId("leadlag-cell-BTC-ETH");
    expect(cell.getAttribute("title")).toContain("Lag: 15m");
    expect(cell.getAttribute("title")).toContain("Strength: 0.820");
    expect(cell.getAttribute("title")).toContain("Sample size: 240");
    expect(cell.getAttribute("title")).toContain("Freshness: 6.0 mins ago");
  });

  it("falls back gracefully when a cell has no data", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    renderWithProviders(<HeatmapHarness />, queryClient);

    await screen.findByTestId("leadlag-cell-BTC-ETH");
    const emptyCell = screen.getByTestId("leadlag-cell-USDT-BTC");
    expect(emptyCell).toHaveTextContent("—");
    expect(emptyCell).toHaveTextContent("No lag data");
    expect(emptyCell.getAttribute("title")).toContain(
      "No lead/lag data available",
    );
  });

  it("creates distinct query keys when filters change", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    renderWithProviders(<HeatmapHarness />, queryClient);

    await screen.findByTestId("leadlag-cell-BTC-ETH");

    fireEvent.change(screen.getByLabelText("Lead/lag window"), {
      target: { value: "4h" },
    });
    fireEvent.change(screen.getByLabelText("Leader symbol"), {
      target: { value: "SOL" },
    });

    await waitFor(() => {
      const keys = queryClient
        .getQueryCache()
        .findAll({ queryKey: ["analytics", "leadlag", "matrix"] })
        .map((query) => query.queryKey);
      expect(keys).toContainEqual([
        "analytics",
        "leadlag",
        "matrix",
        "1h",
        "BTC",
        "ETH",
      ]);
      expect(keys).toContainEqual([
        "analytics",
        "leadlag",
        "matrix",
        "4h",
        "SOL",
        "ETH",
      ]);
    });
  });
});
