import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { type ReactNode, useState } from "react";
import { act } from "react-dom/test-utils";
import { vi } from "vitest";

import Correlogram from "@/app/dashboard/Correlogram";
import { leadLagResponse } from "@/mocks/handlers/analytics";

import { server } from "../../vitest.setup";

function renderWithClient(ui: ReactNode, client: QueryClient) {
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("Correlogram", () => {
  it("updates the best-lag badge within one second of data resolving", async () => {
    vi.useFakeTimers();
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    server.use(
      http.get("/analytics/leadlag", async () => {
        await new Promise((resolve) => setTimeout(resolve, 500));
        return HttpResponse.json(leadLagResponse);
      }),
    );

    renderWithClient(
      <Correlogram leader="BTC" follower="ETH" window="1h" />,
      client,
    );

    const badge = screen.getByTestId("best-lag-badge");
    expect(badge).toHaveTextContent(/Calculating best lag/i);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(750);
    });

    vi.useRealTimers();

    await waitFor(() => {
      expect(badge).toHaveTextContent("15m lag");
    });
  });

  it("renders bars and labels from the correlogram fixture", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderWithClient(
      <Correlogram leader="BTC" follower="ETH" window="1h" />,
      client,
    );

    const bestBar = await screen.findByTestId("correlogram-bar-+15m");
    const zeroLagBar = screen.getByTestId("correlogram-bar-0m");

    expect(Number.parseFloat(bestBar.style.height)).toBeCloseTo(100, 1);
    expect(Number.parseFloat(zeroLagBar.style.height)).toBeCloseTo(58.5, 1);

    expect(screen.getByText("+15m")).toBeInTheDocument();
    expect(screen.getByText("0.82")).toBeInTheDocument();
    expect(screen.getByText("0m")).toBeInTheDocument();
    expect(screen.getByText("0.48")).toBeInTheDocument();
  });

  it("shows loading, error, and empty states", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    server.use(
      http.get("/analytics/leadlag", () => HttpResponse.json(leadLagResponse)),
    );

    renderWithClient(
      <Correlogram leader="BTC" follower="ETH" window="1h" />,
      client,
    );

    expect(screen.getByTestId("correlogram-loading")).toBeInTheDocument();

    server.use(
      http.get("/analytics/leadlag", () =>
        HttpResponse.json({ message: "boom" }, { status: 500 }),
      ),
    );

    const errorClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderWithClient(
      <Correlogram leader="BTC" follower="ETH" window="1h" />,
      errorClient,
    );

    await screen.findByRole("alert");
    expect(
      screen.getByText(/Failed to load correlogram data/i),
    ).toBeInTheDocument();

    server.use(
      http.get("/analytics/leadlag", () =>
        HttpResponse.json(
          {
            ...leadLagResponse,
            data: [
              {
                leader: "BTC",
                follower: "ETH",
                window: "1h",
                best_lag_minutes: null,
                strength: null,
                sample_size: null,
                computed_ts: null,
                correlogram: { buckets: [], best_lag_minutes: null },
              },
            ],
          },
          { status: 200 },
        ),
      ),
    );

    const emptyClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderWithClient(
      <Correlogram leader="BTC" follower="ETH" window="1h" />,
      emptyClient,
    );

    await screen.findByText(/No correlogram data available/i);
  });

  it("creates distinct query keys when the selected pair changes", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    function Harness() {
      const [leader, setLeader] = useState("BTC");
      const [follower, setFollower] = useState("ETH");

      return (
        <div>
          <Correlogram leader={leader} follower={follower} window="1h" />
          <button onClick={() => setLeader("ETH")} aria-label="swap leader">
            swap leader
          </button>
          <button onClick={() => setFollower("BTC")} aria-label="swap follower">
            swap follower
          </button>
        </div>
      );
    }

    renderWithClient(<Harness />, client);

    await screen.findByTestId("correlogram-card");

    fireEvent.click(screen.getByLabelText("swap leader"));
    fireEvent.click(screen.getByLabelText("swap follower"));

    await waitFor(() => {
      const keys = client
        .getQueryCache()
        .findAll({ queryKey: ["analytics", "leadlag"] })
        .map((query) => query.queryKey);

      expect(keys).toContainEqual(["analytics", "leadlag", "BTC", "ETH", "1h"]);
      expect(keys).toContainEqual(["analytics", "leadlag", "ETH", "BTC", "1h"]);
    });
  });
});
