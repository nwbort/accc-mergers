/**
 * How a merger's result — or, until it has one, its standing — is read out of
 * its record.
 *
 * The merger detail page fills its header card with the colour of whatever the
 * matter is carrying, and MergerOutcomeHeading states that on top of it, so
 * both need the same answer to "what is this matter carrying, and has it
 * finished?". That answer lives here rather than in either of them so the page
 * and the heading cannot disagree.
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
 * What the detail page's header block is speaking for, decided or not.
 *
 * Every matter has one: the outcome once it has finished, otherwise whatever
 * it is carrying while it runs — a determination that doesn't end the matter
 * (a phase 2 referral) if there is one, else the register's status. That
 * precedence mirrors StatusBadge, which the header took over from: the page
 * must never say less than the badge in the corner used to.
 *
 * `decided` keeps the two apart, since "the ACCC determined X" and "this
 * matter is sitting at X" are different claims and are introduced differently
 * to a screen reader.
 */
export function getHeaderStatus(merger) {
  const decided = getDecidedOutcome(merger);
  if (decided) {
    return { label: decided.outcome, appealSuffix: decided.appealSuffix, decided: true };
  }
  // No appealSuffix while a matter is live: a suffix says how the Tribunal
  // changed the determination that stands, and there isn't one to change yet.
  const { determination } = resolveEffectiveDetermination(
    merger?.accc_determination,
    merger?.appeal
  );
  const label = determination || merger?.status;
  return label ? { label, appealSuffix: null, decided: false } : null;
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
