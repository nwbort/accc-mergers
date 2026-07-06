/**
 * Format a median duration value for display.
 *
 * `statistics.median` (used by both stats.json and analysis.json generators)
 * averages the two middle values for an even-length sample, so a median can
 * come back as a whole number or end in `.5`. Trim the trailing `.0` but keep
 * `.5` so we never show a value like "26.0 business days".
 */
export function formatMedian(value) {
  return Number.isInteger(value) ? value : value.toFixed(1);
}
