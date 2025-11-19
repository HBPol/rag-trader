import { z } from "zod";

export const eventItemSchema = z.object({
  id: z.string().optional(),
  title: z.string(),
  summary: z.string().optional(),
  source: z.string().optional(),
  url: z.string().url().optional(),
  published_at: z.string(),
  symbols: z.array(z.string()).default([]),
  sentiment: z.number().nullable().optional(),
});

export const eventsResponseSchema = z.object({
  status: z.string(),
  data: z.array(eventItemSchema),
  last_updated: z.string().nullable().optional(),
  message: z.string().optional(),
});

export type EventItem = z.infer<typeof eventItemSchema>;
export type EventsResponse = z.infer<typeof eventsResponseSchema>;
