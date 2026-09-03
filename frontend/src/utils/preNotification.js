/**
 * Reading the pipeline's pre-notification estimate (see
 * scripts/generate/static_data/prenotification.py) into something displayable.
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
/** Only the latest possible start is known, so the date is a ceiling rather than a point. */
export const PRE_NOTIFICATION_BEFORE = 'before';

/** How much weight the estimate can carry, from the evidence behind it. */
export const PRE_NOTIFICATION_CONFIDENCE = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
};

/**
 * A bracketed estimate whose proven floor and ceiling sit this close together
 * is pinned to about a fortnight, which is as tight as this method gets.
 */
export const HIGH_CONFIDENCE_WINDOW_DAYS = 14;

/**
 * Past this the bracket is wide enough that the estimate is little better than
 * a single bound — the counter is dated too sparsely around this case for the
 * interpolated date to mean much.
 */
export const MEDIUM_CONFIDENCE_WINDOW_DAYS = 42;

/**
 * How far apart the estimate's proven bounds are, in days, or null when only
 * one side of the case number is dated.
 *
 * min_days is the floor the counter proves and max_days the generous ceiling,
 * so their difference is the width of the window pre-notification could have
 * started in — the estimate's error bar.
 * @param {object} estimate - A merger's raw `pre_notification` record
 * @returns {number|null}
 */
export const getPreNotificationWindowDays = (estimate) => {
  const { min_days: minDays, max_days: maxDays } = estimate || {};
  if (typeof minDays !== 'number' || typeof maxDays !== 'number') return null;
  return Math.max(maxDays - minDays, 0);
};

/**
 * How much to trust an estimate, as low/medium/high.
 *
 * Only a bracketed estimate has evidence on both sides, and how good it is
 * depends on how far apart those two witnesses are: a narrow window pins the
 * start date, a wide one barely constrains it. An estimate resting on a single
 * bound is a floor or a ceiling being read as a point, so it is always low.
 * @param {object} estimate - A merger's raw `pre_notification` record
 * @returns {string} One of PRE_NOTIFICATION_CONFIDENCE
 */
export const getPreNotificationConfidence = (estimate) => {
  const windowDays = getPreNotificationWindowDays(estimate);
  if (estimate?.basis !== 'bracketed' || windowDays === null) {
    return PRE_NOTIFICATION_CONFIDENCE.LOW;
  }
  if (windowDays <= HIGH_CONFIDENCE_WINDOW_DAYS) return PRE_NOTIFICATION_CONFIDENCE.HIGH;
  if (windowDays <= MEDIUM_CONFIDENCE_WINDOW_DAYS) return PRE_NOTIFICATION_CONFIDENCE.MEDIUM;
  return PRE_NOTIFICATION_CONFIDENCE.LOW;
};

/**
 * How a merger's pre-notification period should be described, or null when
 * there's nothing to say.
 *
 * Skipped entirely for voluntary-period notifications, which predate the waiver
 * applications that date the case-number counter.
 * @param {object} merger - A merger record
 * @returns {{kind: string, startDate: string|null, confidence: string, windowDays: number|null}|null}
 */
export const getPreNotificationEstimate = (merger) => {
  const estimate = merger?.pre_notification;
  if (!estimate?.id_issued_estimated) return null;
  if (estimate.estimated_days == null) return null;
  if (isVoluntaryPeriodNotification(merger)) return null;

  // A nought-day estimate dates the case number to the filing day itself, which
  // is the absence of a pre-notification period rather than a measurement of
  // one — there's no date to give.
  const confidence = getPreNotificationConfidence(estimate);
  const windowDays = getPreNotificationWindowDays(estimate);

  if (estimate.estimated_days <= 0) {
    return { kind: PRE_NOTIFICATION_NONE, startDate: null, confidence, windowDays };
  }

  // A single bound gives an endpoint, not a point: an upper bound alone says
  // only that the case number can't have been issued before its anchor (the
  // period starts at the earliest there), and a lower bound alone only that it
  // was issued by the time a later case was filed (the period starts at the
  // latest there). Only a bracketed estimate has evidence on both sides and
  // earns "around".
  let kind = PRE_NOTIFICATION_AROUND;
  if (estimate.basis === 'upper-bound-only') kind = PRE_NOTIFICATION_AFTER;
  if (estimate.basis === 'lower-bound-only') kind = PRE_NOTIFICATION_BEFORE;

  return { kind, startDate: estimate.id_issued_estimated, confidence, windowDays };
};
