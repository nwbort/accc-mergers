/**
 * Empirical CDF over analysis.json's duration histograms: "X% of reviews
 * conclude by day N".
 */

/**
 * Points for one ECDF curve, read out of a flat count map.
 *
 * `counts` is `{duration: number of matters that took exactly that long}` —
 * the shape `current_status`'s per-window `duration_histogram` publishes, and
 * what the nested all-time histograms fold down to (see `computeEcdf`).
 *
 * The curve is right-continuous: the cumulative percentage jumps at each
 * distinct duration and holds flat until the next one (drawn with Chart.js
 * `stepped`). The leading `{x: 0}` point anchors it at the origin.
 *
 * Returns `[]` for an empty or absent map, which is how a page knows to omit
 * the chart — including for an analysis.json generated before these
 * histograms existed.
 */
export function computeEcdfFromCounts(counts) {
  const byDuration = new Map();
  for (const [duration, n] of Object.entries(counts || {})) {
    const value = Number(duration);
    byDuration.set(value, (byDuration.get(value) || 0) + n);
  }

  let total = 0;
  for (const n of byDuration.values()) total += n;
  if (total === 0) return [];

  const points = [{ x: 0, y: 0, n: 0, total }];
  let cumulative = 0;
  for (const value of [...byDuration.keys()].sort((a, b) => a - b)) {
    cumulative += byDuration.get(value);
    points.push({ x: value, y: Math.round((cumulative / total) * 1000) / 10, n: cumulative, total });
  }
  return points;
}

/**
 * Points for one ECDF curve, read out of a nested duration histogram.
 *
 * `histogram` is analysis.json's nested count map — business days → calendar
 * days → number of completed reviews with exactly that pair. It replaced a
 * flat list holding one object per review, which said the same thing several
 * hundred times over; the counts carry the same distribution without the
 * repetition. Reading business days means summing each inner map without
 * looking at its keys; reading calendar days means folding the inner keys
 * together across every outer key. Either way the result is a flat count map,
 * which `computeEcdfFromCounts` turns into the curve.
 */
export function computeEcdf(histogram, calendarDays) {
  const counts = {};
  for (const [businessDays, byCalendarDays] of Object.entries(histogram || {})) {
    for (const [calendar, n] of Object.entries(byCalendarDays)) {
      const key = calendarDays ? calendar : businessDays;
      counts[key] = (counts[key] || 0) + n;
    }
  }
  return computeEcdfFromCounts(counts);
}
