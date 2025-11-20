import { z } from "zod";

export const grangerEntrySchema = z.object({
  source: z.string(),
  target: z.string(),
  window: z.string(),
  direction: z.string().nullable().optional(),
  p_value: z.number().nullable(),
  reject_null: z.boolean().nullable(),
  computed_ts: z.string().nullable(),
});

export const grangerResponseSchema = z.object({
  status: z.string(),
  data: z.array(grangerEntrySchema),
  last_updated: z.string().nullable(),
  freshness: z.object({
    age_minutes: z.number().nullable(),
  }),
  message: z.string().optional(),
});

export type GrangerEntry = z.infer<typeof grangerEntrySchema>;
export type GrangerResponse = z.infer<typeof grangerResponseSchema>;
