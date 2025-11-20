import { z } from "zod";

export const sentimentPointSchema = z.object({
  ts: z.string().nullable(),
  polarity: z.number().nullable(),
  confidence: z.number().nullable(),
  zscore: z.number().nullable(),
  price_usd: z.number().nullable().optional(),
  aspects: z.array(z.string()),
});

export const sentimentResponseSchema = z.object({
  status: z.string().optional(),
  symbol: z.string(),
  window: z.string(),
  series: z.array(sentimentPointSchema),
  last_updated: z.string().nullable(),
  freshness: z.object({
    age_minutes: z.number(),
  }),
  message: z.string().optional(),
});

export type SentimentPoint = z.infer<typeof sentimentPointSchema>;
export type SentimentResponse = z.infer<typeof sentimentResponseSchema>;
