/**
 * The vocabulary of a matter's pre-notification summary, as the pipeline
 * publishes it on each detail file (`pre_notification_summary`, written by
 * pre_notification_summary in scripts/generate/static_data/prenotification.py,
 * the only copy of the rule; the API publishes the same object).
 *
 * Pre-notification — the stretch of ACCC engagement before a notification is
 * formally filed — never appears on the public register. The pipeline infers it
 * from the order ACCC case numbers were issued in, and how firmly it can date
 * the start decides how the estimate is worded: the summary's `kind` says how
 * to read its `start_date`, and its `confidence` how much weight it carries.
 */

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
