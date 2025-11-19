import { z } from "zod";

export const leadLagEntrySchema = z.object({
  leader: z.string(),
  follower: z.string(),
  window: z.string(),
  best_lag_minutes: z.number().nullable(),
  strength: z.number().nullable(),
  computed_ts: z.string().nullable(),
});

export const leadLagResponseSchema = z.object({
  status: z.string(),
  data: z.array(leadLagEntrySchema),
  last_updated: z.string().nullable(),
  freshness: z.object({
    age_minutes: z.number().nullable(),
  }),
  message: z.string().optional(),
});

export type LeadLagEntry = z.infer<typeof leadLagEntrySchema>;
export type LeadLagResponse = z.infer<typeof leadLagResponseSchema>;
