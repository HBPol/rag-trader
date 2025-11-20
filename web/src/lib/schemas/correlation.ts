import { z } from "zod";

const correlationMetricPointSchema = z.object({
  value: z.number().nullable(),
  computed_ts: z.string().nullable().optional(),
});

export const correlationEntrySchema = z.object({
  asset: z.string(),
  window: z.string(),
  pair: z.tuple([z.string(), z.string()]).optional(),
  metrics: z.record(correlationMetricPointSchema),
  value: z.number().optional(),
  computed_ts: z.string().optional(),
});

export const correlationResponseSchema = z.object({
  status: z.string(),
  metric: z.string(),
  data: z.array(correlationEntrySchema),
  last_updated: z.string().nullable(),
  freshness: z.object({
    age_minutes: z.number().nullable(),
  }),
  message: z.string().optional(),
});

export type CorrelationMetricPoint = z.infer<
  typeof correlationMetricPointSchema
>;
export type CorrelationEntry = z.infer<typeof correlationEntrySchema>;
export type CorrelationResponse = z.infer<typeof correlationResponseSchema>;
