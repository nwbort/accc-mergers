/**
 * Reading helpers for quarterly.json, the /quarterly page's data.
 *
 * The generator publishes one block per calendar quarter (see
 * scripts/generate/static_data/outputs/quarterly.py). Everything here is about
 * reading one quarter against the one before it: which quarter the URL names
 * and how far a figure moved. The sentences the page leads with are written by
 * the generator (each quarter's `findings`), so the PDF report says the same.
 */

/**
 * The quarter a `?q=` value names, else the latest. quarterly.json publishes
 * complete quarters only, so the latest is the last quarter to have ended.
 *
 * `?q=` is the short `url_key` (`26Q3`), matched case-insensitively. The long
 * `2026-Q3` the page used to write is still accepted so older links work.
 */
export function pickQuarter(quarters, key) {
  if (!quarters?.length) return null;
  return findQuarter(quarters, key) || quarters[quarters.length - 1];
}

/** The quarter `key` names exactly (`26Q3`, any case, or `2026-Q3`), else null. */
export function findQuarter(quarters, key) {
  const wanted = key?.trim().toUpperCase();
  if (!wanted) return null;
  return (quarters || []).find((q) => q.url_key?.toUpperCase() === wanted || q.quarter === wanted) || null;
}

/** The quarter before `quarter` in the published list, or null for the first. */
export function previousQuarter(quarters, quarter) {
  const index = quarters.findIndex((q) => q.quarter === quarter?.quarter);
  return index > 0 ? quarters[index - 1] : null;
}

/** Whole-percent change from `before` to `after`; null without a usable base. */
export function percentChange(after, before) {
  if (after == null || !before) return null;
  return Math.round(((after - before) / before) * 100);
}

/** A 0–1 rate as a whole percentage string ("96%"), or an en dash. */
export function formatRate(rate) {
  return rate == null ? '–' : `${Math.round(rate * 100)}%`;
}

/** Each bucket's share of `buckets`' total, as whole percentages. */
export function bucketShares(buckets) {
  const total = (buckets || []).reduce((sum, n) => sum + n, 0);
  return (buckets || []).map((n) => (total ? Math.round((n / total) * 1000) / 10 : 0));
}
