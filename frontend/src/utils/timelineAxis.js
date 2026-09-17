/**
 * Shared geometry for the horizontal milestone tracks.
 *
 * Phase2Timeline and the refiled-notifications cards both draw the same
 * figure: a track spanning two dates, with milestones positioned along it as a
 * percentage and labels sitting above or below the line. The maths and the
 * label offsets used to be copied into each file, with a comment in one of
 * them noting that it mirrored the other — which is exactly the arrangement
 * that drifts. They live here instead.
 *
 * MergerTimeline draws the same figure but carries extra machinery of its own
 * (a prediction band, a mid-axis label that has to dodge the end labels), so
 * it keeps its own positioning code and only the conventions are shared.
 */

import { differenceInCalendarDays, parseISO, isValid } from 'date-fns';

// Every label sits its bottom this far above the line; every date sits its top
// this far below it. Shared across the start/track/end columns so the three
// line up (MergerTimeline uses the same offsets for its aboveLine/belowLine).
export const ABOVE_LINE = 'absolute bottom-1/2 mb-2';
export const BELOW_LINE = 'absolute top-1/2 mt-2';

/**
 * Position of `dateStr` along the `startStr` → `endStr` axis, as a percentage
 * clamped to [0, 100].
 *
 * Clamping matters: a milestone landing outside the span (bad data, a clock
 * restart) still renders inside the bar rather than breaking the layout.
 *
 * Returns null when any date is missing or unparseable, or when the span has
 * no positive length — callers treat null as "nothing to mark".
 */
export function percentAlong(dateStr, startStr, endStr) {
  if (!dateStr || !startStr || !endStr) return null;
  const date = parseISO(dateStr);
  const start = parseISO(startStr);
  const end = parseISO(endStr);
  if (!isValid(date) || !isValid(start) || !isValid(end)) return null;
  const total = differenceInCalendarDays(end, start);
  if (total <= 0) return null;
  const elapsed = differenceInCalendarDays(date, start);
  return Math.min(100, Math.max(0, (elapsed / total) * 100));
}

/**
 * Inline style centring a label of half-width `half` on `percent` along the
 * track, clamped so a label near either end stops at the edge instead of
 * hanging off it.
 *
 * The clamp is CSS rather than JS so it stays correct as the track resizes —
 * `half` is a CSS length (e.g. '4.75rem'), and a width-relative translate
 * would behave differently on a narrow mobile track.
 */
export function clampedLabelStyle(percent, half, translate) {
  return {
    left: `clamp(${half}, ${percent}%, calc(100% - ${half}))`,
    transform: translate,
  };
}
