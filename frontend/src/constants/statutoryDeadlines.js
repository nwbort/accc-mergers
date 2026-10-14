/**
 * The statutory clocks a duration chart is read against.
 *
 * These are the deadlines the Act puts on the ACCC, not observed durations:
 * a phase 1 review runs 30 business days from an effective notification, and
 * a waiver application 25. Charts draw them as a reference line so a curve
 * can be read against the promise rather than only against its own median.
 */

/** Business days the ACCC has to complete a phase 1 review. */
export const PHASE_1_DEADLINE_BD = 30;

/** Business days the ACCC has to decide a notification waiver application. */
export const WAIVER_DEADLINE_BD = 25;

/**
 * Business days the ACCC has to complete a phase 2 review, counted from the
 * day phase 1 was due (not from the referral, which can land early).
 */
export const PHASE_2_DEADLINE_BD = 90;
