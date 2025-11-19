import { z } from "zod";

export const influenceGraphEdgeSchema = z.object({
  source: z.string(),
  target: z.string(),
  window: z.string(),
  lag: z.number().nullable().optional(),
  correlation: z.number().nullable().optional(),
  cross_correlation: z.number().nullable().optional(),
  granger_p_value: z.number().nullable().optional(),
  granger_reject_null: z.boolean().nullable().optional(),
  weight: z.number().nullable().optional(),
  computed_ts: z.string().nullable().optional(),
});

export const influenceGraphSchema = z.object({
  nodes: z.array(z.string()),
  edges: z.array(influenceGraphEdgeSchema),
});

export const influenceGraphResponseSchema = z.object({
  status: z.string(),
  graph: influenceGraphSchema,
  last_updated: z.string().nullable(),
  freshness: z.object({
    age_minutes: z.number().nullable(),
  }),
  message: z.string().optional(),
});

export type InfluenceGraphEdge = z.infer<typeof influenceGraphEdgeSchema>;
export type InfluenceGraph = z.infer<typeof influenceGraphSchema>;
export type InfluenceGraphResponse = z.infer<
  typeof influenceGraphResponseSchema
>;
