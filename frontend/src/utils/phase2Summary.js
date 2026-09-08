/**
 * Summary statistics for the Phase 2 tracker's status cards, derived from
 * phase2.json rather than from the pipeline: the file is a handful of matters
 * and already fetched by the page.
 */

import { calculateDuration } from './dates';
import {
  MERGER_STATUS,
  PHASE_2_OUTCOME_ORDER,
  isConditionalApproval,
} from '../constants/mergerStatus';

/**
 * The outcome a completed matter is counted under. Approvals split by whether
 * conditions were imposed: at Phase 2 that distinction is the point, since a
 * clearance bought with an undertaking is a different result from an outright
 * one. Mirrors the dashboard's Phase 2 doughnut (stats.by_phase_2_determination).
 */
export function phase2Outcome(matter) {
  return isConditionalApproval(matter)
    ? MERGER_STATUS.APPROVED_WITH_CONDITIONS
    : matter?.determination || null;
}

/**
 * Reduce the tracker's two lists to the figures behind the status cards:
 *
 * - `total` / `currentCount` / `completedCount` — how many matters have been
 *   referred to Phase 2, and how the count splits between running and finished
 * - `outcomes` — one entry per outcome of a completed review, in
 *   PHASE_2_OUTCOME_ORDER with anything unrecognised appended rather than
 *   dropped, each carrying its count and rounded share of completed reviews
 * - `averageDays` — mean calendar days from referral to determination across
 *   `averageBasis` matters. Ceased assessments are excluded: those end when the
 *   parties walk away, so counting them would measure how quickly a deal was
 *   abandoned rather than how long the ACCC takes to decide one. `ceasedCount`
 *   is how many were left out on that basis.
 */
export function summarisePhase2(current = [], completed = []) {
  const counts = new Map();
  const durations = [];
  let ceasedCount = 0;

  completed.forEach((matter) => {
    const outcome = phase2Outcome(matter);
    if (outcome) counts.set(outcome, (counts.get(outcome) || 0) + 1);

    if (matter?.determination === MERGER_STATUS.ASSESSMENT_CEASED) {
      ceasedCount += 1;
      return;
    }
    const duration = calculateDuration(matter?.referral_date, matter?.determination_date);
    if (duration !== null && duration >= 0) durations.push(duration);
  });

  const known = PHASE_2_OUTCOME_ORDER.filter((label) => counts.has(label));
  const unknown = [...counts.keys()].filter((label) => !PHASE_2_OUTCOME_ORDER.includes(label));
  const outcomes = [...known, ...unknown].map((label) => ({
    label,
    count: counts.get(label),
    share: Math.round((counts.get(label) / completed.length) * 100),
  }));

  const averageDays = durations.length
    ? Math.round(durations.reduce((sum, days) => sum + days, 0) / durations.length)
    : null;

  return {
    total: current.length + completed.length,
    currentCount: current.length,
    completedCount: completed.length,
    outcomes,
    averageDays,
    averageBasis: durations.length,
    ceasedCount,
  };
}
