/**
 * Reading the pipeline's pre-notification estimate (see
 * scripts/static_data/prenotification.py) into something displayable.
 *
 * Pre-notification — the stretch of ACCC engagement before a notification is
 * formally filed — never appears on the public register. The pipeline infers it
 * from the order ACCC case numbers were issued in, and how firmly it can date
 * the start decides how the estimate is worded.
 */

import { isVoluntaryPeriodNotification } from '../constants/regime';

/** No pre-notification period is detectable — the case number was issued the day the notification landed. */
export const PRE_NOTIFICATION_NONE = 'none';
/** The start is bracketed, so it can be given as a date. */
export const PRE_NOTIFICATION_AROUND = 'around';
/** Only the earliest possible start is known, so the date is a floor rather than a point. */
export const PRE_NOTIFICATION_AFTER = 'after';

/**
 * How a merger's pre-notification period should be described, or null when
 * there's nothing to say.
 *
 * Skipped entirely for voluntary-period notifications, which predate the waiver
 * applications that date the case-number counter.
 * @param {object} merger - A merger record
 * @returns {{kind: string, startDate: string|null}|null}
 */
export const getPreNotificationEstimate = (merger) => {
  const estimate = merger?.pre_notification;
  if (!estimate?.id_issued_estimated) return null;
  if (estimate.estimated_days == null) return null;
  if (isVoluntaryPeriodNotification(merger)) return null;

  // A nought-day estimate dates the case number to the filing day itself, which
  // is the absence of a pre-notification period rather than a measurement of
  // one — there's no date to give.
  if (estimate.estimated_days <= 0) {
    return { kind: PRE_NOTIFICATION_NONE, startDate: null };
  }

  // An upper bound alone says only that the case number can't have been issued
  // before its anchor, so the date is where the period starts at the earliest.
  const kind = estimate.basis === 'upper-bound-only'
    ? PRE_NOTIFICATION_AFTER
    : PRE_NOTIFICATION_AROUND;

  return { kind, startDate: estimate.id_issued_estimated };
};
