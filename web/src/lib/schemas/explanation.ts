import { z } from "zod";

export const explanationSourceSchema = z.object({
  label: z.string(),
  url: z.string().url(),
});

export const explanationSchema = z.object({
  id: z.string(),
  rationale: z.string().nullable().optional(),
  source: explanationSourceSchema.nullable().optional(),
});

export const explanationsResponseSchema = z.object({
  status: z.string(),
  data: z.array(explanationSchema),
  freshness: z
    .object({
      age_minutes: z.number().nullable(),
    })
    .optional(),
  message: z.string().optional(),
});

export type ExplanationSource = z.infer<typeof explanationSourceSchema>;
export type Explanation = z.infer<typeof explanationSchema>;
export type ExplanationsResponse = z.infer<typeof explanationsResponseSchema>;
