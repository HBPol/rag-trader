import { z } from "zod";

export const ragSnippetSchema = z.object({
  id: z.string(),
  title: z.string(),
  source: z.string(),
  published_at: z.string(),
  content: z.string(),
  citation: z.number(),
  score: z.number().optional().nullable(),
});

export const ragResponseSchema = z.object({
  query: z.string(),
  summary: z.string(),
  snippets: z.array(ragSnippetSchema),
});

export type RagSnippet = z.infer<typeof ragSnippetSchema>;
export type RagResponse = z.infer<typeof ragResponseSchema>;
