/**
 * How a decided merger's result is read out of its record.
 *
 * The merger detail page leads with an outcome banner
 * (components/MergerOutcomeBanner.jsx) and lays the rest of its header out
 * around it, so both need the same answer to "is this matter decided, and what
 * was the result?". That answer lives here rather than in the component so the
 * page and the banner cannot disagree, and so the wording can be tested
 * directly.
 */

import { MERGER_STATUS, PHASES } from '../constants/mergerStatus';
import { resolveEffectiveDetermination } from '../constants/appeal';
import { calculateBusinessDays, calculateDuration, formatDateLong } from './dates';

// Determinations that end a matter. A live matter's accc_determination is null,
// so a decided outcome only ever appears once the register has published one.
const DECIDED_DETERMINATIONS = new Set([
  MERGER_STATUS.APPROVED,
  MERGER_STATUS.NOT_APPROVED,
  MERGER_STATUS.NOT_OPPOSED,
  MERGER_STATUS.DECLINED,
]);

// Determinations that let the acquisition proceed.
const CLEARED = new Set([MERGER_STATUS.APPROVED, MERGER_STATUS.NOT_OPPOSED]);

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

// "Phase 1"/"Phase 2" out of the register's longer stage label
// ("Phase 2 - detailed assessment"), or null for a waiver application.
function phaseOf(merger) {
  const stage = merger.stage || '';
  if (stage.includes(PHASES.PHASE_2)) return PHASES.PHASE_2;
  if (stage.includes(PHASES.PHASE_1)) return PHASES.PHASE_1;
  return null;
}

/**
 * Plain-English sentence for what the ACCC itself decided, and when.
 *
 * Always describes the ACCC's own determination rather than the effective one,
 * so it stays true where a tribunal appeal has since replaced the outcome — the
 * appeal is described on its own line instead.
 */
export function acccDecisionSentence(merger, decidedDate) {
  const on = decidedDate ? ` on ${formatDateLong(decidedDate)}` : '';

  if (merger.status === MERGER_STATUS.ASSESSMENT_CEASED) {
    return `The ACCC ceased its assessment of this acquisition${on}.`;
  }

  const cleared = CLEARED.has(merger.accc_determination);

  if (merger.is_waiver) {
    return cleared
      ? `The ACCC granted a notification waiver${on}.`
      : `The ACCC did not grant a notification waiver${on}.`;
  }

  const phase = phaseOf(merger);
  const inPhase = phase ? ` in ${phase}` : '';
  if (cleared) {
    return merger.has_conditions
      ? `The ACCC cleared this acquisition subject to conditions${inPhase}${on}.`
      : `The ACCC cleared this acquisition${inPhase}${on}.`;
  }
  return `The ACCC refused to approve this acquisition${inPhase}${on}.`;
}

/**
 * How long the assessment ran, from the notification (or waiver application)
 * that started the clock to the day it was decided. Null when either end is
 * missing, which is the case for a handful of older register entries.
 */
export function durationSentence(merger, startDate, decidedDate) {
  const calendarDays = calculateDuration(startDate, decidedDate);
  const businessDays = calculateBusinessDays(startDate, decidedDate);
  if (calendarDays === null || businessDays === null) return null;
  const from = merger.is_waiver ? 'the waiver application' : 'notification';
  return `${calendarDays} calendar days (${businessDays} business days) from ${from}.`;
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
