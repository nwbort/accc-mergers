/**
 * Empirical CDF over analysis.json's duration histograms: "X% of reviews
 * conclude by day N".
 */

/**
 * Points for one ECDF curve, read out of a duration histogram.
 *
 * `histogram` is analysis.json's nested count map — business days → calendar
 * days → number of completed reviews with exactly that pair. It replaced a
 * flat list holding one object per review, which said the same thing several
 * hundred times over; the counts carry the same distribution without the
 * repetition. Reading business days means summing each inner map without
 * looking at its keys; reading calendar days means folding the inner keys
 * together across every outer key.
 *
 * The curve is right-continuous: the cumulative percentage jumps at each
 * distinct duration and holds flat until the next one (drawn with Chart.js
 * `stepped`). The leading `{x: 0}` point anchors it at the origin.
 *
 * Returns `[]` for an empty or absent histogram, which is how the page knows
 * to omit the chart — including for an analysis.json generated before these
 * histograms existed.
 */
export function computeEcdf(histogram, calendarDays) {
  const counts = new Map();
  for (const [businessDays, byCalendarDays] of Object.entries(histogram || {})) {
    for (const [calendar, n] of Object.entries(byCalendarDays)) {
      const value = Number(calendarDays ? calendar : businessDays);
      counts.set(value, (counts.get(value) || 0) + n);
    }
  }

  let total = 0;
  for (const n of counts.values()) total += n;
  if (total === 0) return [];

  const points = [{ x: 0, y: 0, n: 0, total }];
  let cumulative = 0;
  for (const value of [...counts.keys()].sort((a, b) => a - b)) {
    cumulative += counts.get(value);
    points.push({ x: value, y: Math.round((cumulative / total) * 1000) / 10, n: cumulative, total });
  }
  return points;
}
