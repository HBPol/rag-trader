"use client";

import { useState } from "react";

import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api/client";
import { ragResponseSchema, type RagResponse } from "@/lib/schemas/rag";

function renderSummary(summary: string, snippets: RagResponse["snippets"]) {
  const citationMap = snippets.reduce<Map<string, string>>((map, snippet) => {
    map.set(String(snippet.citation), `snippet-${snippet.citation}`);
    return map;
  }, new Map());

  const parts: React.ReactNode[] = [];
  const pattern = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(summary)) !== null) {
    const [token, citation] = match;
    if (match.index > lastIndex) {
      parts.push(summary.slice(lastIndex, match.index));
    }

    const target = citationMap.get(citation) ?? "";
    parts.push(
      <a
        key={`${citation}-${match.index}`}
        className="font-semibold text-primary underline decoration-dotted underline-offset-2"
        href={`#${target}`}
        aria-label={`Jump to source ${citation}`}
      >
        {token}
      </a>,
    );
    lastIndex = match.index + token.length;
  }

  if (lastIndex < summary.length) {
    parts.push(summary.slice(lastIndex));
  }

  return parts;
}

function formatPublished(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export default function RagPage() {
  const [query, setQuery] = useState(
    "How are macro risks shaping bitcoin price action this week?",
  );

  const mutation = useMutation({
    mutationFn: async (payload: { query: string }) => {
      const response = await apiFetch<RagResponse>("/rag", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return ragResponseSchema.parse(response);
    },
  });

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!query.trim()) return;
    await mutation.mutateAsync({ query: query.trim() });
  };

  return (
    <main className="flex min-h-screen flex-col gap-6 bg-background p-6 text-foreground">
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Retrieval Playground
        </p>
        <h1 className="text-3xl font-semibold leading-tight tracking-tight">
          Ask the RAG cluster
        </h1>
        <p className="text-sm text-muted-foreground">
          Issue a query to retrieve the top matches from the Qdrant vector
          store, then review the LLM summary with citations back to the source
          snippets.
        </p>
      </div>

      <Card className="border shadow-sm">
        <CardHeader>
          <CardTitle className="text-lg">Search the corpus</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="grid gap-2">
              <label
                className="text-sm font-medium text-foreground"
                htmlFor="rag-query"
              >
                Query
              </label>
              <textarea
                id="rag-query"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                minLength={3}
                rows={3}
                placeholder="What do you want to learn from the retriever?"
                className="min-h-[120px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                Responses include citations like [1] and [2] you can click to
                jump to the matching snippet.
              </p>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Searching..." : "Run retrieval"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {mutation.isError ? (
        <Card className="border-destructive/40 bg-destructive/10">
          <CardContent className="pt-6 text-sm text-destructive-foreground">
            {(mutation.error as Error).message || "Request failed"}
          </CardContent>
        </Card>
      ) : null}

      {mutation.isSuccess ? (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg">Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="leading-relaxed text-muted-foreground">
                {renderSummary(mutation.data.summary, mutation.data.snippets)}
              </p>
            </CardContent>
          </Card>

          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="text-lg">Snippets</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {mutation.data.snippets.map((snippet) => (
                <div
                  key={snippet.id}
                  id={`snippet-${snippet.citation}`}
                  className="rounded-lg border border-border/80 bg-card p-4 shadow-sm"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <p className="text-sm font-semibold leading-tight text-foreground">
                        {snippet.title}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatPublished(snippet.published_at)}
                      </p>
                    </div>
                    <span className="rounded-full bg-muted px-3 py-1 text-xs font-semibold text-muted-foreground">
                      {snippet.source}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                    {snippet.content}
                  </p>
                  <div className="mt-3 text-xs text-muted-foreground">
                    Citation [{snippet.citation}]
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </main>
  );
}
