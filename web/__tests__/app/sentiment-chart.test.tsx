import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import SentimentPriceChart from "@/app/dashboard/SentimentPriceChart";
import { useSentimentQuery } from "@/lib/queries/analytics";
import type { SentimentResponse } from "@/lib/schemas/sentiment";

vi.mock("@/lib/queries/analytics", () => ({
  useSentimentQuery: vi.fn(),
}));

const mockedUseSentimentQuery = vi.mocked(useSentimentQuery);

type QueryResult = ReturnType<typeof useSentimentQuery>;

const basePayload: SentimentResponse = {
  status: "ok",
  symbol: "BTC",
  window: "1h",
  series: [
    {
      ts: "2024-01-01T10:00:00Z",
      polarity: 0.2,
      confidence: 0.9,
      zscore: 0.8,
      price_usd: 22100,
      aspects: [],
    },
    {
      ts: "2024-01-01T11:00:00Z",
      polarity: -0.1,
      confidence: 0.7,
      zscore: -0.4,
      price_usd: 22250,
      aspects: [],
    },
  ],
  last_updated: "2024-01-01T12:00:00Z",
  freshness: { age_minutes: 5 },
};

const baseResult = {
  data: basePayload,
  error: null,
  isError: false,
  isLoading: false,
  isSuccess: true,
  isFetching: false,
  isPending: false,
  refetch: vi.fn(),
  remove: vi.fn(),
  status: "success",
  dataUpdatedAt: 0,
  errorUpdatedAt: 0,
  failureCount: 0,
  errorUpdateCount: 0,
  failureReason: null,
  fetchStatus: "idle",
  isFetched: true,
  isFetchedAfterMount: true,
  isInitialLoading: false,
  isLoadingError: false,
  isPlaceholderData: false,
  isPaused: false,
  isRefetchError: false,
  isRefetching: false,
  isRefetchingAfterMount: false,
  isStale: false,
} as unknown as QueryResult;

function renderChart() {
  return render(<SentimentPriceChart symbol="BTC" />);
}

describe("SentimentPriceChart", () => {
  beforeEach(() => {
    mockedUseSentimentQuery.mockReturnValue(baseResult);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("requests new data when the window toggle changes", () => {
    renderChart();

    expect(mockedUseSentimentQuery).toHaveBeenCalledWith("BTC", "1h");

    fireEvent.click(screen.getByRole("button", { name: "4h" }));

    expect(mockedUseSentimentQuery).toHaveBeenLastCalledWith("BTC", "4h");
  });

  it("displays converted price units and axis labels", () => {
    renderChart();

    expect(screen.getByTestId("price-summary")).toHaveTextContent("$22,250.00");
    expect(
      screen.getByText(/Price axis scaled to USD thousands/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("price-axis-label")).toHaveTextContent(
      "Price (USD, thousands)",
    );
    expect(screen.getByTestId("zscore-axis-label")).toHaveTextContent(
      "Sentiment z-score",
    );
  });

  it("handles empty and error states gracefully", () => {
    mockedUseSentimentQuery
      .mockReturnValueOnce({
        ...baseResult,
        data: { ...basePayload, series: [] },
      })
      .mockReturnValueOnce({
        ...baseResult,
        data: undefined,
        error: new Error("upstream failed"),
        isError: true,
      });

    renderChart();
    expect(
      screen.getByText(
        "No sentiment or price data available for the selected window.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "4h" }));

    expect(
      screen.getByLabelText(/unable to load sentiment chart/i),
    ).toBeInTheDocument();
  });
});
