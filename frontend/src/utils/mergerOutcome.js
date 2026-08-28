/**
 * How a decided merger's result is read out of its record.
 *
 * The merger detail page fills its header card with the outcome's colour once
 * a matter is decided, and MergerOutcomeHeading states the result on top of
 * it, so both need the same answer to "is this matter decided, and what was
 * the result?". That answer lives here rather than in either of them so the
 * page and the heading cannot disagree.
 */

import { MERGER_STATUS } from '../constants/mergerStatus';
import { resolveEffectiveDetermination } from '../constants/appeal';

// Determinations that end a matter. A live matter's accc_determination is null,
// so a decided outcome only ever appears once the register has published one.
const DECIDED_DETERMINATIONS = new Set([
  MERGER_STATUS.APPROVED,
  MERGER_STATUS.NOT_APPROVED,
  MERGER_STATUS.NOT_OPPOSED,
  MERGER_STATUS.DECLINED,
]);

/**
 * The outcome that now stands for a matter, or null while it is still running.
 *
 * `outcome` is the effective determination — a concluded tribunal appeal can
 * replace the ACCC's own — and `appealSuffix` says why it changed, exactly as
 * StatusBadge shows it.
 */
export function getDecidedOutcome(merger) {
  if (!merger) return null;
  const ceased = merger.status === MERGER_STATUS.ASSESSMENT_CEASED;
  if (merger.status !== MERGER_STATUS.ASSESSMENT_COMPLETED && !ceased) return null;

  const { determination, appealSuffix } = resolveEffectiveDetermination(
    merger.accc_determination,
    merger.appeal
  );
  if (determination && DECIDED_DETERMINATIONS.has(determination)) {
    return { outcome: determination, appealSuffix, ceased: false };
  }
  // A ceased assessment never gets a determination — the ACCC simply stops.
  if (ceased) {
    return { outcome: MERGER_STATUS.ASSESSMENT_CEASED, appealSuffix, ceased: true };
  }
  return null;
}

/**
 * The document that carries the ACCC's reasons: a Phase 2 matter publishes a
 * separate statement of reasons, everything else puts them in the
 * determination itself.
 */
export function getDeterminationDocUrl(merger) {
  const events = merger?.events || [];
  if (merger?.phase_2_determination) {
    const statement = events.find(
      (e) => e.url_gh && e.title?.toLowerCase().includes('statement of reasons')
    );
    if (statement) return statement.url_gh;
  }
  return events.find((e) => e.is_determination_event)?.url_gh ?? null;
}
