import { australianToday, calculateBusinessDays, isDatePast } from './dates';
import { MERGER_STATUS } from '../constants/mergerStatus';

/**
 * Business-day progress for a non-waiver merger under assessment, or null if
 * the merger isn't eligible (waiver, not under assessment, or missing dates).
 * Totals are computed from the merger's own dates rather than hardcoded,
 * since extensions and Phase 2 referral make the statutory window vary.
 */
export function getBusinessDayProgress(merger) {
  if (
    !merger ||
    merger.is_waiver ||
    merger.status !== MERGER_STATUS.UNDER_ASSESSMENT ||
    !merger.effective_notification_datetime ||
    !merger.end_of_determination_period
  ) {
    return null;
  }

  const total = calculateBusinessDays(
    merger.effective_notification_datetime,
    merger.end_of_determination_period
  );
  if (total === null || total <= 0) return null;

  // Notification timestamps carry a fixed time-of-day (typically noon UTC), and
  // calculateBusinessDays does a plain datetime comparison as it walks forward
  // a day at a time — so comparing against the raw current instant undercounts
  // today whenever "now" is earlier in the day than that time-of-day. Anchor to
  // the ACCC's calendar (australianToday) and normalize to the end of that day
  // so today counts as soon as it's a business day, consistently for every viewer.
  const today = australianToday();
  today.setHours(23, 59, 59, 999);
  const rawElapsed = calculateBusinessDays(merger.effective_notification_datetime, today);
  if (rawElapsed === null) return null;

  return {
    elapsed: Math.min(Math.max(rawElapsed, 0), total),
    total,
    overdue: isDatePast(merger.end_of_determination_period),
  };
}
