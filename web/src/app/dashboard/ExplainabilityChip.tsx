"use client";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type MouseEvent,
  type FocusEvent,
  type KeyboardEvent,
} from "react";

import { useExplanationQuery } from "@/lib/queries/explanations";
import type { ExplanationSource } from "@/lib/schemas/explanation";
import { cn } from "@/lib/utils";

type ExplainabilityChipProps = {
  metricId: string | null | undefined;
  label?: string;
  fallbackRationale?: string | null;
  fallbackSource?: ExplanationSource | null;
  className?: string;
};

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;

    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReducedMotion(mediaQuery.matches);

    const handleChange = (event: MediaQueryListEvent) => {
      setPrefersReducedMotion(event.matches);
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleChange);
    } else {
      mediaQuery.addListener?.(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleChange);
      } else {
        mediaQuery.removeListener?.(handleChange);
      }
    };
  }, []);

  return prefersReducedMotion;
}

export default function ExplainabilityChip({
  metricId,
  label = "Why?",
  fallbackRationale,
  fallbackSource,
  className,
}: ExplainabilityChipProps) {
  const tooltipId = useId();
  const prefersReducedMotion = usePrefersReducedMotion();
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const explanationQuery = useExplanationQuery(metricId, {
    enabled: false,
    placeholderData:
      fallbackRationale || fallbackSource
        ? {
            id: metricId ?? "",
            rationale: fallbackRationale ?? undefined,
            source: fallbackSource ?? undefined,
          }
        : undefined,
  });

  const explanation = explanationQuery.data;

  const statusText = useMemo(() => {
    if (explanationQuery.isFetching && !explanationQuery.isError) {
      return "Loading rationale...";
    }
    if (explanationQuery.isError) {
      return "Could not load rationale.";
    }
    if (!explanation?.rationale) {
      return "No explanation available yet.";
    }
    return explanation.rationale;
  }, [
    explanation?.rationale,
    explanationQuery.isError,
    explanationQuery.isFetching,
  ]);

  const triggerFetch = () => {
    if (!metricId) return;
    if (
      !explanationQuery.isFetching &&
      (!explanationQuery.isFetched || explanationQuery.isError)
    ) {
      void explanationQuery.refetch();
    }
  };

  const handleOpen = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
    triggerFetch();
    setOpen(true);
  };

  const handleClose = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
    }
    closeTimer.current = setTimeout(
      () => setOpen(false),
      prefersReducedMotion ? 0 : 120,
    );
  };

  const handleMouseEnter = (event: MouseEvent) => {
    event.preventDefault();
    handleOpen();
  };

  const handleMouseLeave = (event: MouseEvent) => {
    event.preventDefault();
    handleClose();
  };

  const handleFocus = (event: FocusEvent) => {
    event.preventDefault();
    handleOpen();
  };

  const handleBlur = () => {
    handleClose();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Escape") {
      setOpen(false);
    }
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      if (!open) {
        handleOpen();
      } else {
        setOpen(false);
      }
    }
  };

  return (
    <div className={cn("relative inline-flex", className)}>
      <button
        type="button"
        className={cn(
          "inline-flex items-center gap-1 rounded-full border border-primary/30 bg-primary/5 px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-primary transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
          explanationQuery.isFetching ? "animate-pulse" : "",
        )}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        aria-expanded={open}
        aria-controls={open ? tooltipId : undefined}
        aria-label={`Explain ${label}`}
        disabled={!metricId}
      >
        <span aria-hidden className="text-base">
          ℹ︎
        </span>
        <span>{label}</span>
      </button>
      {open ? (
        <div
          role="tooltip"
          id={tooltipId}
          className={cn(
            "absolute z-20 mt-2 min-w-[220px] max-w-xs rounded-md border bg-popover px-3 py-2 text-xs shadow-lg",
            "text-foreground",
            prefersReducedMotion ? "" : "transition-opacity duration-150",
          )}
        >
          <div className="space-y-1">
            <p
              className="leading-relaxed"
              data-testid="explainability-rationale"
            >
              {explanationQuery.isFetching && !explanation?.rationale ? (
                <span className="inline-block h-4 w-3/4 animate-pulse rounded bg-muted" />
              ) : (
                statusText
              )}
            </p>
            {explanation?.source ? (
              <p className="text-[11px] text-muted-foreground">
                Source:{" "}
                <a
                  href={explanation.source.url ?? undefined}
                  className="font-semibold text-primary underline underline-offset-2"
                  target="_blank"
                  rel="noreferrer"
                >
                  {explanation.source.label}
                </a>
              </p>
            ) : explanationQuery.isError ? (
              <p className="text-[11px] text-destructive" aria-live="polite">
                Explanation unavailable.
              </p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
