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
 * The quarter a `?q=` value names, else the latest complete quarter, else the
 * latest of any kind.
 *
 * Defaulting to the latest *complete* quarter is what a quarterly report means:
 * the quarter in progress is a few weeks of filings, and leading with it would
 * read every figure as a collapse.
 */
export function pickQuarter(quarters, key) {
  if (!quarters?.length) return null;
  const named = key && quarters.find((q) => q.quarter === key);
  if (named) return named;
  const complete = quarters.filter((q) => q.complete);
  return complete.length ? complete[complete.length - 1] : quarters[quarters.length - 1];
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

/** Display label for a milestone kind. */
export const MILESTONE_LABELS = {
  referred: 'Referred to phase 2',
  phase_1_refused: 'Not approved at phase 1',
  phase_2_outcome: 'Phase 2 outcome',
  ceased: 'Phase 1 review ceased',
  public_benefit_application: 'Public benefit application',
  public_benefit_outcome: 'Public benefit outcome',
  tribunal_application: 'Tribunal review sought',
  judicial_review: 'Federal Court review sought',
};
