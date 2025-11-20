import {
  QueryClient,
  QueryClientProvider,
  type QueryClientConfig,
} from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "../../../vendor/msw/lib/index.js";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import {
  useCorrelationQuery,
  useEventsQuery,
  useGrangerQuery,
  useInfluenceGraphQuery,
  useLeadLagQuery,
  useSentimentQuery,
} from "@/lib/queries/analytics";
import {
  correlationResponse,
  eventsResponse,
  grangerResponse,
  influenceGraphResponse,
  leadLagResponse,
  sentimentResponse,
} from "@/mocks/handlers/analytics";
import { server } from "../../../vitest.setup";

function createQueryClient(config?: QueryClientConfig) {
  const defaultOptions: QueryClientConfig["defaultOptions"] = {
    queries: {
      retry: false,
      retryDelay: 0,
      ...(config?.defaultOptions?.queries ?? {}),
    },
    ...config?.defaultOptions,
  };

  return new QueryClient({
    ...config,
    defaultOptions,
  });
}

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("analytics queries", () => {
  it("returns correlation payloads and entry", async () => {
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ symbol, window }) => useCorrelationQuery(symbol, window),
      {
        wrapper: createWrapper(queryClient),
        initialProps: { symbol: "aapl", window: "1d" },
      },
    );

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.payload).toEqual(correlationResponse);
    expect(result.current.data?.entry?.asset).toBe("AAPL");
    expect(result.current.data?.entry?.window).toBe("1d");

    expect(
      queryClient.getQueryCache().find({
        queryKey: ["analytics", "correlation", "AAPL", "1d"],
      }),
    ).toBeDefined();

    rerender({ symbol: "msft", window: "1w" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      queryClient.getQueryCache().find({
        queryKey: ["analytics", "correlation", "MSFT", "1w"],
      }),
    ).toBeDefined();
  });

  it("handles correlation error responses", async () => {
    server.use(
      http.get("/analytics/correlation", () =>
        HttpResponse.json({ message: "boom" }, { status: 500 }),
      ),
    );

    const { result } = renderHook(
      ({ symbol, window }) => useCorrelationQuery(symbol, window),
      {
        wrapper: createWrapper(createQueryClient()),
        initialProps: { symbol: "aapl", window: "1d" },
      },
    );

    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 2000,
    });
    expect(result.current.error?.message).toContain(
      "Request failed with status 500",
    );
  });

  it("returns lead/lag edges and updates cache keys", async () => {
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ leader, follower, window }) =>
        useLeadLagQuery(leader, follower, window),
      {
        wrapper: createWrapper(queryClient),
        initialProps: { leader: "aapl", follower: "msft", window: "1d" },
      },
    );

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.payload).toEqual(leadLagResponse);
    expect(result.current.data?.edge?.leader).toBe("AAPL");
    expect(result.current.data?.edge?.follower).toBe("MSFT");

    rerender({ leader: "msft", follower: "aapl", window: "1w" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      queryClient.getQueryCache().find({
        queryKey: ["analytics", "leadlag", "MSFT", "AAPL", "1w"],
      }),
    ).toBeDefined();
  });

  it("yields granger statistics and caches by pair", async () => {
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ source, target, window }) => useGrangerQuery(source, target, window),
      {
        wrapper: createWrapper(queryClient),
        initialProps: { source: "aapl", target: "msft", window: "1d" },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.payload).toEqual(grangerResponse);
    expect(result.current.data?.edge?.p_value).toBeCloseTo(0.03);

    rerender({ source: "msft", target: "aapl", window: "1w" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      queryClient.getQueryCache().find({
        queryKey: ["analytics", "granger", "MSFT", "AAPL", "1w"],
      }),
    ).toBeDefined();
  });

  it("returns influence graph data and matching edges", async () => {
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ source, target, window }) =>
        useInfluenceGraphQuery(source, target, window),
      {
        wrapper: createWrapper(queryClient),
        initialProps: { source: "aapl", target: "msft", window: "1d" },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.payload).toEqual(influenceGraphResponse);
    expect(result.current.data?.matchingEdge?.target).toBe("MSFT");

    rerender({ source: "goog", target: "aapl", window: "1w" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      queryClient.getQueryCache().find({
        queryKey: ["analytics", "influence-graph", "GOOG", "AAPL", "1w"],
      }),
    ).toBeDefined();
  });

  it("resolves sentiment series for each symbol/window", async () => {
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ symbol, window }) => useSentimentQuery(symbol, window),
      {
        wrapper: createWrapper(queryClient),
        initialProps: { symbol: "aapl", window: "1d" },
      },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toMatchObject({
      ...sentimentResponse,
      symbol: "aapl",
      window: "1d",
    });

    rerender({ symbol: "msft", window: "1w" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      queryClient.getQueryCache().find({
        queryKey: ["sentiment", "MSFT", "1w"],
      }),
    ).toBeDefined();
  });

  it("returns events feed", async () => {
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useEventsQuery(), {
      wrapper: createWrapper(queryClient),
    });

    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(eventsResponse);
  });

  it("handles server errors for events", async () => {
    server.use(
      http.get("/events", () =>
        HttpResponse.json({ message: "oops" }, { status: 500 }),
      ),
    );

    const { result } = renderHook(() => useEventsQuery(), {
      wrapper: createWrapper(createQueryClient()),
    });

    await waitFor(() => expect(result.current.isError).toBe(true), {
      timeout: 2000,
    });
    expect(result.current.error?.message).toContain(
      "Request failed with status 500",
    );
  });
});
