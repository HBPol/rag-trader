import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act } from "react-dom/test-utils";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

async function flushAllTimers() {
  await act(async () => {
    vi.runOnlyPendingTimers();
  });
}

describe("InfluenceGraph edge pulsing", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("applies a pulse class for strengthening edges", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2024-01-09T00:40:00Z"));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderWithProviders(
      <InfluenceGraph source="BTC" target="ETH" windowSize="1h" />,
      queryClient,
    );

    await screen.findByTestId("influence-graph-canvas");
    await flushAllTimers();

    const strengtheningEdge = await screen.findByTestId(
      "influence-edge-BTC-ETH",
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(strengtheningEdge).toHaveClass("influence-edge--pulse");
    });

    const stableEdge = screen.getByTestId("influence-edge-SOL-BTC");
    expect(stableEdge).not.toHaveClass("influence-edge--pulse");
  });

  it("skips animation when the user prefers reduced motion", async () => {
    const matchMediaMock = vi.fn().mockImplementation((query) => ({
      matches: true,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    }));
    vi.spyOn(window, "matchMedia").mockImplementation(matchMediaMock as never);
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2024-01-09T00:40:00Z"));

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderWithProviders(
      <InfluenceGraph source="BTC" target="ETH" windowSize="1h" />,
      queryClient,
    );

    await screen.findByTestId("influence-graph-canvas");
    await flushAllTimers();

    const strengtheningEdge = await screen.findByTestId(
      "influence-edge-BTC-ETH",
    );

    act(() => {
      vi.advanceTimersByTime(20);
    });

    await waitFor(() => {
      expect(strengtheningEdge).not.toHaveClass("influence-edge--pulse");
    });
  });
});
