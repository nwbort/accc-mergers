/**
 * Outcome -> the colour of the rail down the left edge of a merger list card.
 *
 * The detail page fills a decided matter's title block with its outcome colour
 * (constants/outcomeHeader.js), so the result is the first thing the page says.
 * The list page cannot do the same thing the same way: nine in ten matters on
 * the register are "Approved", so filling those cards would turn the page
 * emerald and bury the handful of refusals and ceased assessments a reader is
 * scanning for. The rail keeps the colour vocabulary and spends a fraction of
 * the ink — a margin you can read down rather than a wall of fill.
 *
 * Every card still states its outcome in words in the badge alongside, so the
 * rail is decoration and never the only carrier of the result (WCAG 1.4.1).
 * That is also why these are the mid shades rather than the deep ones
 * outcomeHeader.js needs: nothing sits on top of a rail, so it only has to be
 * told apart from its neighbours and from the white card.
 *
 * Live matters get a rail too. If only decided ones did, its mere presence
 * would become the signal and the colour would stop being the thing you read.
 *
 * Full class strings are required so Tailwind's scanner keeps them at build
 * time.
 */

import { MERGER_STATUS } from './mergerStatus';
import { resolveEffectiveDetermination } from './appeal';

export const OUTCOME_RAIL_COLORS = {
  // Determinations
  [MERGER_STATUS.APPROVED]: 'bg-emerald-500',
  [MERGER_STATUS.NOT_OPPOSED]: 'bg-emerald-500',
  [MERGER_STATUS.NOT_APPROVED]: 'bg-red-600',
  [MERGER_STATUS.DECLINED]: 'bg-red-600',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'bg-amber-500',
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'bg-purple-500',

  // Statuses, for a matter with no determination yet
  [MERGER_STATUS.UNDER_ASSESSMENT]: 'bg-primary',
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: 'bg-orange-500',
};

// A completed assessment whose determination is missing, and anything else the
// register throws up, lands here rather than borrowing another outcome's
// colour.
export const DEFAULT_OUTCOME_RAIL = 'bg-gray-300';

/**
 * The rail colour for a merger list entry.
 *
 * Determination takes precedence over status and a concluded appeal takes
 * precedence over the ACCC's own determination, both mirroring StatusBadge, so
 * the rail and the badge beside it can never name different outcomes.
 */
export function getOutcomeRail({ status, determination, appeal } = {}) {
  const { determination: effective } = resolveEffectiveDetermination(determination, appeal);
  return (
    OUTCOME_RAIL_COLORS[effective] || OUTCOME_RAIL_COLORS[status] || DEFAULT_OUTCOME_RAIL
  );
}
