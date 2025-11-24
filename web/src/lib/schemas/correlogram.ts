import { z } from "zod";

export const correlogramBucketSchema = z.object({
  lag_minutes: z.number(),
  correlation: z.number().nullable(),
  label: z.string().optional(),
});

export const correlogramSchema = z.object({
  buckets: z.array(correlogramBucketSchema),
  best_lag_minutes: z.number().nullable().optional(),
  computed_ts: z.string().nullable().optional(),
  window: z.string().optional(),
});

export type CorrelogramBucket = z.infer<typeof correlogramBucketSchema>;
export type Correlogram = z.infer<typeof correlogramSchema>;
