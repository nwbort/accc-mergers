import { calculateBusinessDays, isDatePast } from './dates';
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

  const rawElapsed = calculateBusinessDays(merger.effective_notification_datetime, new Date());
  if (rawElapsed === null) return null;

  return {
    elapsed: Math.min(Math.max(rawElapsed, 0), total),
    total,
    overdue: isDatePast(merger.end_of_determination_period),
  };
}
