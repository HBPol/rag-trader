"use client";

import { useMutation } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import {
  backtestResponseSchema,
  dslResponseSchema,
  type BacktestResponse,
  type DslResponse,
} from "@/lib/schemas/backtest";

export function useDslMutation() {
  return useMutation({
    mutationKey: ["studio", "dsl"],
    mutationFn: async (prompt: string) => {
      const payload = await apiFetch<DslResponse>("/studio/dsl", {
        method: "POST",
        body: JSON.stringify({ prompt }),
        throwOnError: true,
      });

      return dslResponseSchema.parse(payload);
    },
  });
}

export function useBacktestMutation() {
  return useMutation({
    mutationKey: ["studio", "backtest"],
    mutationFn: async (dsl: string) => {
      const payload = await apiFetch<BacktestResponse>("/studio/backtest", {
        method: "POST",
        body: JSON.stringify({ dsl }),
        throwOnError: true,
      });

      return backtestResponseSchema.parse(payload);
    },
  });
}
