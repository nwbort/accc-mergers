/**
 * Reading the pipeline's pre-notification estimate (see
 * scripts/static_data/prenotification.py) into something displayable.
 *
 * Pre-notification — the stretch of ACCC engagement before a notification is
 * formally filed — never appears on the public register. The pipeline infers it
 * from the order ACCC case numbers were issued in, and hands each notification
 * a bracket of dates rather than a single fact.
 */

import { isVoluntaryPeriodNotification } from '../constants/regime';

/**
 * How confidently the estimate can be stated, keyed off the `basis` the
 * pipeline recorded. A matter bracketed by waiver applications on both sides of
 * its case number gets a range; one with evidence from a single side only gets
 * the bound that side proves.
 * @param {object} estimate - A merger's pre_notification record
 * @returns {string} A phrase describing the period, e.g. "At least 7 days"
 */
const describeBounds = (estimate) => {
  const { basis, min_days: minDays, max_days: maxDays } = estimate;

  if (basis === 'bracketed' && minDays > 0 && maxDays != null && minDays !== maxDays) {
    return `Between ${minDays} and ${maxDays} days`;
  }
  // A nought-day floor proves nothing, so a bracket resting on one is stated as
  // the ceiling alone rather than as a range starting at zero.
  if (maxDays != null) {
    return `No more than ${maxDays} days`;
  }
  if (minDays > 0) {
    return `At least ${minDays} days`;
  }
  return `About ${estimate.estimated_days} days`;
};

/**
 * The estimated start of a merger's pre-notification period, or null when
 * there's nothing worth showing.
 *
 * Skipped for voluntary-period notifications, and for matters where the
 * estimate collapses to the filing date itself — a nought-day estimate says the
 * case number was issued the day the notification landed, which is the absence
 * of a pre-notification period rather than a measurement of one.
 * @param {object} merger - A merger record
 * @returns {{startDate: string, notifiedDate: string, bounds: string}|null}
 */
export const getPreNotificationEstimate = (merger) => {
  const estimate = merger?.pre_notification;
  if (!estimate?.id_issued_estimated) return null;
  if (!(estimate.estimated_days > 0)) return null;
  if (isVoluntaryPeriodNotification(merger)) return null;

  const notifiedDate = merger.original_notification_datetime
    || merger.effective_notification_datetime;
  if (!notifiedDate) return null;

  return {
    startDate: estimate.id_issued_estimated,
    notifiedDate,
    bounds: describeBounds(estimate),
  };
};
