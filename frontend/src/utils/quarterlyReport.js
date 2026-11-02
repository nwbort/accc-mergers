/**
 * Reading helpers for quarterly.json, the /quarterly page's data.
 *
 * The generator publishes one block per calendar quarter (see
 * scripts/generate/static_data/outputs/quarterly.py). Everything here is about
 * reading one quarter against the one before it: which quarter the URL names
 * and how far a figure moved. The sentences the page leads with are written by
 * the generator (each quarter's `findings`), so the PDF report says the same.
 */

import { format } from 'date-fns';
import { parseDateOnly } from './dates';

/** The quarter a `/quarterly/26Q3` path names (any case), else null. */
export function findQuarter(quarters, key) {
  const wanted = key?.trim().toUpperCase();
  if (!wanted) return null;
  return (quarters || []).find((q) => q.url_key?.toUpperCase() === wanted) || null;
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

/**
 * Which edition of a quarter's report this is: `{ short: 'v2 · 2 Nov 2026',
 * long: 'Version 2, updated 2 November 2026' }`, or null for a block with no
 * version. A quarter's figures keep moving after it ends, so the generator
 * bumps `version` whenever its block changes: `'3'` for a change a reader
 * would notice, `'3.1'` when only a histogram moved (see
 * scripts/generate/static_data/quarterly_versions.py); the PDF's band carries
 * the same short form.
 */
export function versionLabel(quarter) {
  if (!quarter?.version) return null;
  const dated = quarter.version_date ? parseDateOnly(quarter.version_date) : null;
  return {
    short: dated ? `v${quarter.version} · ${format(dated, 'd MMM yyyy')}` : `v${quarter.version}`,
    long: dated
      ? `Version ${quarter.version}, updated ${format(dated, 'd MMMM yyyy')}`
      : `Version ${quarter.version}`,
  };
}
