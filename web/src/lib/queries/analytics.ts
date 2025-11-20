"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import {
  correlationResponseSchema,
  type CorrelationResponse,
} from "@/lib/schemas/correlation";
import {
  leadLagResponseSchema,
  type LeadLagResponse,
} from "@/lib/schemas/leadlag";
import {
  grangerResponseSchema,
  type GrangerResponse,
} from "@/lib/schemas/granger";
import {
  influenceGraphResponseSchema,
  type InfluenceGraphEdge,
  type InfluenceGraphResponse,
} from "@/lib/schemas/influenceGraph";
import {
  sentimentResponseSchema,
  type SentimentResponse,
} from "@/lib/schemas/sentiment";
import {
  eventsResponseSchema,
  type EventsResponse,
} from "@/lib/schemas/events";

function normalizeSymbol(value: string): string {
  return value.trim().toUpperCase();
}

export function useCorrelationQuery(symbol: string, window: string) {
  return useQuery({
    queryKey: ["analytics", "correlation", normalizeSymbol(symbol), window],
    enabled: Boolean(symbol && window),
    retry: false,
    queryFn: async () => {
      const payload = correlationResponseSchema.parse(
        await apiFetch<CorrelationResponse>("/analytics/correlation", {
          throwOnError: true,
        }),
      );
      const normalizedSymbol = normalizeSymbol(symbol);
      const entry = payload.data.find(
        (item) =>
          normalizeSymbol(item.asset) === normalizedSymbol &&
          item.window === window,
      );
      return { payload, entry: entry ?? null } as const;
    },
  });
}

export function useLeadLagQuery(
  leader: string,
  follower: string,
  window: string,
) {
  return useQuery({
    queryKey: [
      "analytics",
      "leadlag",
      normalizeSymbol(leader),
      normalizeSymbol(follower),
      window,
    ],
    enabled: Boolean(leader && follower && window),
    retry: false,
    queryFn: async () => {
      const payload = leadLagResponseSchema.parse(
        await apiFetch<LeadLagResponse>("/analytics/leadlag"),
      );
      const normalizedLeader = normalizeSymbol(leader);
      const normalizedFollower = normalizeSymbol(follower);
      const edge = payload.data.find(
        (item) =>
          normalizeSymbol(item.leader) === normalizedLeader &&
          normalizeSymbol(item.follower) === normalizedFollower &&
          item.window === window,
      );
      return { payload, edge: edge ?? null } as const;
    },
  });
}

export function useGrangerQuery(
  source: string,
  target: string,
  window: string,
) {
  return useQuery({
    queryKey: [
      "analytics",
      "granger",
      normalizeSymbol(source),
      normalizeSymbol(target),
      window,
    ],
    enabled: Boolean(source && target && window),
    retry: false,
    queryFn: async () => {
      const payload = grangerResponseSchema.parse(
        await apiFetch<GrangerResponse>("/analytics/granger"),
      );
      const normalizedSource = normalizeSymbol(source);
      const normalizedTarget = normalizeSymbol(target);
      const edge = payload.data.find(
        (item) =>
          normalizeSymbol(item.source) === normalizedSource &&
          normalizeSymbol(item.target) === normalizedTarget &&
          item.window === window,
      );
      return { payload, edge: edge ?? null } as const;
    },
  });
}

export function useInfluenceGraphQuery(
  source: string | null,
  target: string | null,
  window: string | null,
) {
  return useQuery({
    queryKey: [
      "analytics",
      "influence-graph",
      source ? normalizeSymbol(source) : null,
      target ? normalizeSymbol(target) : null,
      window,
    ],
    enabled: Boolean(window),
    retry: false,
    queryFn: async () => {
      const payload = influenceGraphResponseSchema.parse(
        await apiFetch<InfluenceGraphResponse>("/analytics/influence-graph"),
      );
      let matchingEdge: InfluenceGraphEdge | null = null;
      if (source && target && window) {
        const normalizedSource = normalizeSymbol(source);
        const normalizedTarget = normalizeSymbol(target);
        matchingEdge =
          payload.graph.edges.find(
            (edge) =>
              normalizeSymbol(edge.source) === normalizedSource &&
              normalizeSymbol(edge.target) === normalizedTarget &&
              edge.window === window,
          ) ?? null;
      }
      return { payload, matchingEdge } as const;
    },
  });
}

export function useSentimentQuery(symbol: string, window: string) {
  return useQuery({
    queryKey: ["sentiment", normalizeSymbol(symbol), window],
    enabled: Boolean(symbol && window),
    retry: false,
    queryFn: async () => {
      const params = new URLSearchParams({ symbol, window }).toString();
      const payload = sentimentResponseSchema.parse(
        await apiFetch<SentimentResponse>(`/sentiment?${params}`),
      );
      return payload;
    },
  });
}

export function useEventsQuery(options?: { enabled?: boolean }) {
  const enabled = options?.enabled ?? true;
  return useQuery({
    queryKey: ["events"],
    enabled,
    retry: false,
    queryFn: async () => {
      const response = await apiFetch<EventsResponse>("/events", {
        throwOnError: true,
      });

      const payload = eventsResponseSchema.parse(response);

      if (payload.status.toLowerCase() !== "ok") {
        throw new Error(payload.message ?? "Failed to fetch events feed");
      }

      return payload;
    },
  });
}
