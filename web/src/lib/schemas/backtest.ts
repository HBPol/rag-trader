import { z } from "zod";

export const dslResponseSchema = z.object({
  dsl: z.string(),
  summary: z.string().optional(),
});

export type DslResponse = z.infer<typeof dslResponseSchema>;

export const backtestPointSchema = z.object({
  timestamp: z.string(),
});

export const equityPointSchema = backtestPointSchema.extend({
  equity: z.number(),
});

export const drawdownPointSchema = backtestPointSchema.extend({
  drawdown: z.number(),
});

export const exposurePointSchema = backtestPointSchema.extend({
  gross: z.number(),
});

export const backtestResponseSchema = z.object({
  dsl: z.string(),
  metrics: z.object({
    total_return_pct: z.number(),
    sharpe: z.number(),
    max_drawdown_pct: z.number(),
    win_rate_pct: z.number(),
    avg_exposure: z.number(),
  }),
  equity_curve: z.array(equityPointSchema),
  drawdown_curve: z.array(drawdownPointSchema),
  exposure_curve: z.array(exposurePointSchema),
});

export type BacktestResponse = z.infer<typeof backtestResponseSchema>;
