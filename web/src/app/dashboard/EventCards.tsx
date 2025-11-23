"use client";

import { useMemo } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useEventsQuery } from "@/lib/queries/analytics";
import type { EventItem } from "@/lib/schemas/events";

function formatTimestamp(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Unknown time";
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function sentimentBadge(event: EventItem) {
  const sentiment = event.sentiment;
  if (
    sentiment === null ||
    sentiment === undefined ||
    Number.isNaN(sentiment)
  ) {
    return {
      label: "No sentiment",
      tone: "bg-muted text-muted-foreground",
      detail: "N/A",
    } as const;
  }

  if (sentiment > 0.15) {
    return {
      label: "Positive",
      tone: "bg-emerald-100 text-emerald-800",
      detail: `+${(sentiment * 100).toFixed(0)}%`,
    } as const;
  }

  if (sentiment < -0.15) {
    return {
      label: "Negative",
      tone: "bg-rose-100 text-rose-800",
      detail: `${(sentiment * 100).toFixed(0)}%`,
    } as const;
  }

  return {
    label: "Neutral",
    tone: "bg-amber-100 text-amber-800",
    detail: `${(sentiment * 100).toFixed(0)}%`,
  } as const;
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4" data-testid="event-cards-loading">
      {Array.from({ length: 3 }).map((_, index) => (
        <div
          key={index}
          className="animate-pulse rounded-lg border bg-muted/20 p-4 shadow-inner"
        >
          <div className="mb-2 h-4 w-1/3 rounded bg-muted" />
          <div className="mb-3 h-3 w-1/2 rounded bg-muted" />
          <div className="flex flex-wrap gap-2">
            <div className="h-6 w-16 rounded-full bg-muted" />
            <div className="h-6 w-20 rounded-full bg-muted" />
            <div className="h-6 w-24 rounded-full bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function EventCards() {
  const eventsQuery = useEventsQuery();

  const sortedEvents = useMemo(() => {
    if (!eventsQuery.data?.data?.length) return [] as EventItem[];

    return [...eventsQuery.data.data].sort(
      (a, b) =>
        new Date(b.published_at).getTime() - new Date(a.published_at).getTime(),
    );
  }, [eventsQuery.data?.data]);

  const errorMessage =
    eventsQuery.error instanceof Error
      ? eventsQuery.error.message
      : "Failed to fetch events feed";

  return (
    <Card className="border shadow-sm">
      <CardHeader>
        <CardTitle>Events</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-muted-foreground">
        {eventsQuery.isLoading && <LoadingSkeleton />}

        {eventsQuery.isError && (
          <div
            role="alert"
            aria-label="Events feed error"
            className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-destructive"
          >
            {errorMessage}
          </div>
        )}

        {eventsQuery.isSuccess && sortedEvents.length === 0 && (
          <p className="text-muted-foreground">No events available yet.</p>
        )}

        {eventsQuery.isSuccess && sortedEvents.length > 0 && (
          <ul className="space-y-3" aria-label="Recent events">
            {sortedEvents.map((event) => {
              const sentiment = sentimentBadge(event);

              return (
                <li
                  key={event.id ?? event.title}
                  data-testid="event-card"
                  className="rounded-lg border bg-card p-4 text-foreground shadow-sm"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-2">
                      <h3 className="text-base font-semibold leading-tight">
                        {event.title}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {formatTimestamp(event.published_at)}
                      </p>
                      {event.summary ? (
                        <p className="text-sm text-muted-foreground">
                          {event.summary}
                        </p>
                      ) : null}
                      <div
                        className="flex flex-wrap gap-2"
                        aria-label="Affected symbols"
                      >
                        {event.symbols?.length ? (
                          event.symbols.map((symbol) => (
                            <span
                              key={symbol}
                              className="rounded-full border border-primary/20 bg-primary/5 px-2 py-1 text-xs font-semibold text-primary"
                            >
                              {symbol}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            No symbols listed
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-start gap-2 sm:items-end">
                      <span
                        className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${sentiment.tone}`}
                        aria-label={`Sentiment: ${sentiment.label}`}
                      >
                        {sentiment.label}
                        <span className="text-[10px] font-medium text-foreground">
                          {sentiment.detail}
                        </span>
                      </span>
                      {event.url ? (
                        <a
                          href={event.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm font-semibold text-primary underline-offset-4 hover:underline"
                          aria-label={`Source: ${event.title}`}
                        >
                          {event.source ?? "Source"}
                        </a>
                      ) : event.source ? (
                        <span className="text-sm font-medium text-muted-foreground">
                          {event.source}
                        </span>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
