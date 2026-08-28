import { FaBan, FaCheck, FaTimes } from 'react-icons/fa';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { getOutcomeHeaderStyle } from '../constants/outcomeHeader';
import { getDecidedOutcome } from '../utils/mergerOutcome';

const OUTCOME_ICONS = {
  [MERGER_STATUS.APPROVED]: FaCheck,
  [MERGER_STATUS.NOT_OPPOSED]: FaCheck,
  [MERGER_STATUS.NOT_APPROVED]: FaTimes,
  [MERGER_STATUS.DECLINED]: FaTimes,
  [MERGER_STATUS.ASSESSMENT_CEASED]: FaBan,
};

/**
 * The result line above a decided merger's title, sitting on the outcome-
 * coloured header block the detail page paints around it. It states the
 * outcome in the register's own words; the colour behind it does the shouting,
 * so the line itself stays a small eyebrow rather than competing with the h1.
 *
 * Renders nothing while a matter is still under assessment, where the header
 * keeps its white background and its status badge.
 */
function MergerOutcomeHeading({ merger }) {
  const decided = getDecidedOutcome(merger);
  if (!decided) return null;

  const { outcome, appealSuffix } = decided;
  const style = getOutcomeHeaderStyle(outcome);
  const Icon = OUTCOME_ICONS[outcome] || FaCheck;

  // Mirrors StatusBadge: a stale conditions flag on any other outcome stays
  // hidden rather than reading as a conditional clearance.
  const showConditions =
    Boolean(merger.has_conditions) && merger.accc_determination === MERGER_STATUS.APPROVED;

  const chip = `inline-flex items-center px-1.5 py-0.5 rounded normal-case tracking-normal text-[11px] font-medium ${style.chip}`;

  return (
    <p className="flex items-center gap-2 flex-wrap mb-2 text-sm font-bold uppercase tracking-widest">
      <Icon className="w-3.5 h-3.5 flex-shrink-0" aria-hidden="true" />
      {/* Without this the outcome reads as a bare adjective ahead of the
          merger's name. */}
      <span className="sr-only">Outcome:</span>
      <span>{outcome}</span>
      {showConditions && <span className={chip}>with conditions</span>}
      {appealSuffix && <span className={chip}>{appealSuffix}</span>}
    </p>
  );
}

export default MergerOutcomeHeading;
