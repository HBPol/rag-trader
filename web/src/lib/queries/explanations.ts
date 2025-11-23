"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import {
  explanationsResponseSchema,
  type Explanation,
  type ExplanationsResponse,
} from "@/lib/schemas/explanation";

function normalizeId(metricId: string | null | undefined): string | null {
  if (!metricId) return null;
  const trimmed = metricId.trim();
  return trimmed.length ? trimmed : null;
}

export function useExplanationQuery(
  metricId: string | null | undefined,
  options?: {
    enabled?: boolean;
    placeholderData?: Explanation | null;
  },
) {
  const normalizedId = normalizeId(metricId);
  const enabled = options?.enabled ?? true;

  return useQuery({
    queryKey: ["explanations", normalizedId],
    enabled: Boolean(normalizedId) && enabled,
    retry: false,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    placeholderData: options?.placeholderData ?? undefined,
    queryFn: async () => {
      if (!normalizedId) return null;

      let payload: ExplanationsResponse;

      try {
        const params = new URLSearchParams({ id: normalizedId }).toString();
        payload = explanationsResponseSchema.parse(
          await apiFetch<ExplanationsResponse>(`/explanations?${params}`, {
            throwOnError: true,
          }),
        );
      } catch (error) {
        const status = (error as { status?: number }).status;
        const statusText = (error as { response?: Response }).response
          ?.statusText;

        if (typeof status === "number") {
          const message = statusText
            ? `Request failed with status ${status}: ${statusText}`
            : `Request failed with status ${status}`;
          throw new Error(message);
        }

        throw error;
      }

      const explanation =
        payload.data.find((entry) => entry.id === normalizedId) ?? null;

      if (explanation) {
        return explanation;
      }

      throw new Error("Explanation not available");
    },
  });
}
