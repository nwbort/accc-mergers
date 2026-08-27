/**
 * Key dates in Australia's merger notification regime.
 *
 * The new regime opened for business on 1 July 2025, but notifying was
 * optional until 1 January 2026 — matters filed in between are "voluntary
 * period" notifications. They behave differently enough (a thin, self-selected
 * caseload, filed before the register had any waiver applications to date the
 * case-number counter against) that inferences drawn from the shape of the
 * caseload don't carry over to them.
 */

/** First day notification became mandatory. Compared against a YYYY-MM-DD prefix. */
export const MANDATORY_REGIME_START = '2026-01-01';

/**
 * Whether a merger was notified before the mandatory regime began.
 * @param {object} merger - A merger record
 * @returns {boolean} True when the matter was filed in the voluntary period
 */
export const isVoluntaryPeriodNotification = (merger) => {
  const notified = merger?.original_notification_datetime
    || merger?.effective_notification_datetime;
  if (!notified) return false;
  return notified.slice(0, 10) < MANDATORY_REGIME_START;
};
