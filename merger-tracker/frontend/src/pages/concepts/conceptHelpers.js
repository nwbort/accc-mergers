// Shared helpers for the dashboard design concepts (/concepts/*).
//
// These pages are exploratory design mockups. They read the same live data the
// production dashboard uses (stats.json + upcoming-events.json) but present it
// in three deliberately different visual languages so the layouts can be
// compared against real numbers rather than lorem-ipsum.

import { parseISO, isValid, formatDistanceToNowStrict, differenceInCalendarDays } from 'date-fns';

/**
 * Merge recently notified mergers and recent determinations into a single,
 * reverse-chronological "activity stream". Each item is tagged with a `kind`
 * so the UI can colour/iconify it.
 */
export function buildActivityFeed(stats) {
  if (!stats) return [];

  const items = [];

  (stats.recent_mergers ?? []).forEach((m) => {
    items.push({
      kind: m.is_waiver ? 'waiver_filed' : 'notified',
      id: m.merger_id,
      name: m.merger_name,
      date: m.effective_notification_datetime,
      status: m.status,
      determination: m.accc_determination,
      isWaiver: m.is_waiver,
    });
  });

  (stats.recent_determinations ?? []).forEach((d) => {
    const cleared = d.determination === 'Approved' || d.determination === 'Not opposed';
    items.push({
      kind: cleared ? 'cleared' : (d.determination === 'Referred to phase 2' ? 'phase2' : 'decided'),
      id: d.merger_id,
      name: d.merger_name,
      date: d.determination_date,
      determination: d.determination,
      isWaiver: d.is_waiver,
      stage: d.stage,
    });
  });

  return items
    .filter((i) => i.date && isValid(parseISO(i.date)))
    .sort((a, b) => parseISO(b.date) - parseISO(a.date));
}

/** "3 days ago", "today", etc. Returns null on bad input. */
export function relativeTime(dateString) {
  if (!dateString) return null;
  try {
    const d = parseISO(dateString);
    if (!isValid(d)) return null;
    const days = differenceInCalendarDays(new Date(), d);
    if (days === 0) return 'today';
    if (days === 1) return 'yesterday';
    return formatDistanceToNowStrict(d, { addSuffix: true });
  } catch {
    return null;
  }
}

/**
 * Count activity that happened within the last `days` days, split by kind.
 * Used to generate the editorial "state of play" headline sentences.
 */
export function recentActivitySummary(stats, days = 7) {
  const feed = buildActivityFeed(stats);
  const within = feed.filter((i) => {
    const diff = differenceInCalendarDays(new Date(), parseISO(i.date));
    return diff >= 0 && diff <= days;
  });
  return {
    notified: within.filter((i) => i.kind === 'notified' || i.kind === 'waiver_filed').length,
    cleared: within.filter((i) => i.kind === 'cleared').length,
    phase2: within.filter((i) => i.kind === 'phase2').length,
  };
}

/** Clearance rate across completed phase-1 determinations (0-100). */
export function clearanceRate(stats) {
  const det = stats?.by_determination ?? {};
  const total = Object.values(det).reduce((s, v) => s + v, 0);
  if (!total) return null;
  const approved = det['Approved'] ?? 0;
  return Math.round((approved / total) * 100);
}
