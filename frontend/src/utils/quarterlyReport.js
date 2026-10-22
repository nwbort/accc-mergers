/**
 * Reading helpers for quarterly.json, the /quarterly page's data.
 *
 * The generator publishes one block per calendar quarter (see
 * scripts/generate/static_data/outputs/quarterly.py). Everything here is about
 * reading one quarter against the one before it: which quarter the URL names,
 * how far a figure moved, and the handful of sentences the page leads with.
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

function plural(n, one, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`;
}

function volumeClause(after, before, previousLabel) {
  const change = percentChange(after, before);
  if (change === null) return '';
  if (change === 0) return `, level with ${previousLabel}`;
  return `, ${change > 0 ? 'up' : 'down'} ${Math.abs(change)}% on ${previousLabel}`;
}

function timingClause(after, before, previousLabel) {
  if (after == null || before == null) return '';
  const delta = Math.round((after - before) * 10) / 10;
  if (delta === 0) return `, the same as ${previousLabel}`;
  const magnitude = Math.abs(delta);
  return `, ${magnitude} ${magnitude === 1 ? 'day' : 'days'} ${delta > 0 ? 'slower' : 'faster'} than ${previousLabel}`;
}

const OUTCOME_KINDS = new Set(['phase_2_outcome', 'public_benefit_outcome']);

/**
 * The page's lead: what moved this quarter, as a short list of sentences.
 *
 * Volume comparisons are left off for a quarter still in progress — a few
 * weeks of filings against a full quarter would always read as a fall — but
 * its timing figures still compare, since a median doesn't scale with time.
 */
export function keyFindings(quarter, previous) {
  if (!quarter) return [];
  const prevLabel = previous?.label;
  const compareVolume = Boolean(previous) && quarter.complete;
  const n = quarter.notifications;
  const w = quarter.waivers;
  const findings = [];

  findings.push(
    `${plural(n.filed, 'notification')} filed${
      compareVolume ? volumeClause(n.filed, previous.notifications.filed, prevLabel) : ''
    }, and ${plural(w.decided, 'waiver application')} decided${
      compareVolume ? volumeClause(w.decided, previous.waivers.decided, prevLabel) : ''
    }.`
  );

  if (n.timing.median != null) {
    findings.push(
      `Phase 1 reviews concluded in a median ${n.timing.median} business days${
        previous ? timingClause(n.timing.median, previous.notifications.timing.median, prevLabel) : ''
      }; waivers in ${w.timing.median ?? '–'}${
        previous ? timingClause(w.timing.median, previous.waivers.timing.median, prevLabel) : ''
      }.`
    );
  }

  if (n.phase_1_decided || w.decided) {
    findings.push(
      `${formatRate(w.clearance_rate)} of waivers were granted and ${formatRate(n.clearance_rate)} of phase 1 reviews ended in approval.`
    );
  }

  const referred = n.referred_to_phase_2;
  const outcomes = quarter.milestones.filter((m) => OUTCOME_KINDS.has(m.kind));
  if (referred || outcomes.length) {
    const parts = [];
    if (referred) parts.push(`${plural(referred, 'matter')} referred to phase 2`);
    if (outcomes.length) {
      const counts = {};
      for (const m of outcomes) counts[m.detail] = (counts[m.detail] || 0) + 1;
      const detail = Object.entries(counts)
        .map(([label, count]) => `${count} ${label.toLowerCase()}`)
        .join(', ');
      parts.push(`${plural(outcomes.length, 'phase 2 review')} concluded (${detail})`);
    }
    const joined = parts.join('; ');
    findings.push(`${joined.charAt(0).toUpperCase()}${joined.slice(1)}.`);
  }

  return findings;
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
