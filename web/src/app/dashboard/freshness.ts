export function renderFreshness(ageMinutes?: number | null): string {
  if (
    ageMinutes === undefined ||
    ageMinutes === null ||
    !Number.isFinite(ageMinutes)
  ) {
    return "Unknown";
  }
  if (ageMinutes < 1) return "<1 min ago";
  if (ageMinutes < 60) return `${ageMinutes.toFixed(1)} mins ago`;
  return `${(ageMinutes / 60).toFixed(1)} hrs ago`;
}
