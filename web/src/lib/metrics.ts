export const NFR_THRESHOLDS = {
  loadMs: 1200,
  swapMs: 800,
  windowChangeMs: 900,
  graphRenderMs: 850,
  freshnessMs: 1000,
};

function canMeasurePerformance(): boolean {
  return (
    typeof performance !== "undefined" && typeof performance.mark === "function"
  );
}

function markExists(name: string): boolean {
  if (!canMeasurePerformance()) return false;
  return performance.getEntriesByName(name, "mark").length > 0;
}

export function markMetric(name: string, detail?: Record<string, unknown>) {
  if (!canMeasurePerformance()) return;
  if (markExists(name)) return;

  performance.mark(name, { detail });
  // eslint-disable-next-line no-console
  console.info(`[metrics] mark: ${name}`, detail ?? {});
}

export function markMetricUnsafe(
  name: string,
  detail?: Record<string, unknown>,
) {
  if (!canMeasurePerformance()) return;

  performance.mark(name, { detail });
  // eslint-disable-next-line no-console
  console.info(`[metrics] mark: ${name}`, detail ?? {});
}

export function measureMetric(
  measureName: string,
  startMark: string,
  endMark: string,
  thresholdMs = NFR_THRESHOLDS.loadMs,
) {
  if (!canMeasurePerformance()) return;

  try {
    performance.measure(measureName, startMark, endMark);
    const [entry] = performance.getEntriesByName(measureName, "measure");
    if (entry) {
      const duration = Number(entry.duration.toFixed(2));
      const label = duration <= thresholdMs ? "ok" : "slow";
      // eslint-disable-next-line no-console
      console.info(`[metrics] measure:${label}`, {
        measureName,
        duration,
        thresholdMs,
      });
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn(`[metrics] unable to measure ${measureName}`, error);
  }
}

export function markAndMeasureNextFrame({
  startMark,
  endMark,
  measureName,
  thresholdMs = NFR_THRESHOLDS.loadMs,
  detail,
}: {
  startMark: string;
  endMark: string;
  measureName: string;
  thresholdMs?: number;
  detail?: Record<string, unknown>;
}) {
  if (!canMeasurePerformance() || typeof requestAnimationFrame === "undefined")
    return;

  markMetricUnsafe(startMark, detail);
  requestAnimationFrame(() => {
    markMetricUnsafe(endMark, detail);
    measureMetric(measureName, startMark, endMark, thresholdMs);
  });
}

export function reportFreshnessTimestamp(
  name: string,
  ageMinutes: number | null | undefined,
  detail?: Record<string, unknown>,
) {
  if (ageMinutes === null || ageMinutes === undefined) return;
  const ageMs = ageMinutes * 60 * 1000;
  // eslint-disable-next-line no-console
  console.info(`[metrics] freshness:${name}`, {
    ageMinutes,
    stale: ageMs > NFR_THRESHOLDS.freshnessMs,
    detail,
  });
}
