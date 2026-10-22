import {
  MERGER_STATUS,
  STATUS_COLORS,
  SOLID_STATUS_COLORS,
  EMPHATIC_OUTCOMES,
  DEFAULT_STATUS_STYLE,
  DEFAULT_SOLID_STATUS_STYLE,
  GLYPH_BADGE_SHAPE_CLASSES,
  SOLID_BADGE_SHAPE_CLASSES,
} from '../constants/mergerStatus';
import { FaPause, FaRegClock } from 'react-icons/fa';
import { OUTCOME_ICONS } from '../constants/outcomeIcons';
import { resolveEffectiveDetermination } from '../constants/appeal';

// Determinations take precedence over statuses, so the badge is styled by
// whichever of the two it is actually showing.
const STYLED_DETERMINATIONS = [
  MERGER_STATUS.APPROVED,
  MERGER_STATUS.DECLINED,
  MERGER_STATUS.NOT_APPROVED,
  MERGER_STATUS.REFERRED_TO_PHASE_2,
  MERGER_STATUS.ASSESSMENT_CEASED,
];

const STYLED_STATUSES = [
  MERGER_STATUS.UNDER_ASSESSMENT,
  MERGER_STATUS.ASSESSMENT_SUSPENDED,
  MERGER_STATUS.ASSESSMENT_COMPLETED,
  MERGER_STATUS.ASSESSMENT_CEASED,
];

// Symbols for the states OUTCOME_ICONS deliberately leaves without one,
// used only by the `glyph` form, where there is no text to fall back on. A
// "2" rather than an icon for a Phase 2 referral: no stock glyph says it.
const LIVE_GLYPHS = {
  [MERGER_STATUS.UNDER_ASSESSMENT]: FaRegClock,
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: FaPause,
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: '2',
};

/**
 * The status or determination a matter is carrying, as a badge.
 *
 * `solid` asks for the loud form: the outcome filled and set in small caps
 * rather than tinted. The merger list wears it above every card's title, where
 * the result is what the reader came for. Everywhere else the badge is a tint,
 * and only the few adverse outcomes (EMPHATIC_OUTCOMES) fill anyway.
 *
 * `glyph` shrinks the solid form to its symbol alone (the merger table at
 * phone width): same colour, and the words move to the accessible name and a
 * tooltip. "With conditions" and an appeal's result are left to those too.
 */
function StatusBadge({ status, determination, label, hasConditions, appeal, solid = false, glyph = false }) {
  // A concluded tribunal appeal can replace the ACCC's determination with the
  // one that now stands, plus a suffix noting whether it was confirmed or
  // overturned (mirrors the "· with conditions" treatment). Resolved by the
  // shared helper so this badge and the detail page's outcome banner always
  // agree.
  const { determination: effectiveDetermination, appealSuffix } =
    resolveEffectiveDetermination(determination, appeal);

  // The single outcome this badge is speaking for. Everything below — colour,
  // emphasis, glyph — keys off it, so they cannot end up describing different
  // outcomes. 'Declined' and 'Not approved' share the same red palette (both
  // map to the same STATUS_COLORS entry).
  let styleKey = null;
  if (STYLED_DETERMINATIONS.includes(effectiveDetermination)) {
    styleKey = effectiveDetermination;
  } else if (STYLED_STATUSES.includes(status)) {
    styleKey = status;
  }

  const filled = solid || glyph || EMPHATIC_OUTCOMES.includes(styleKey);
  const statusStyle =
    (styleKey && (filled ? SOLID_STATUS_COLORS[styleKey] : STATUS_COLORS[styleKey])) ||
    (solid ? DEFAULT_SOLID_STATUS_STYLE : DEFAULT_STATUS_STYLE);

  // A glyph as well as a colour, so an outcome is not distinguished by colour
  // alone (WCAG 1.4.1) and can be picked out of a long list without reading
  // it. Only decided outcomes have one; a live matter shows text only.
  const Icon = styleKey ? OUTCOME_ICONS[styleKey] : null;

  const displayText = label || effectiveDetermination || status;
  const showConditions =
    hasConditions && effectiveDetermination === MERGER_STATUS.APPROVED;

  const ariaLabelBase = effectiveDetermination
    ? `Determination: ${effectiveDetermination}${showConditions ? ', with conditions' : ''}`
    : `Status: ${status}`;
  const ariaLabel = appealSuffix ? `${ariaLabelBase}, ${appealSuffix}` : ariaLabelBase;

  if (glyph) {
    const Symbol = Icon || (styleKey && LIVE_GLYPHS[styleKey]);
    const words = [displayText, showConditions && 'with conditions', appealSuffix].filter(Boolean).join(' · ');
    return (
      <span
        className={`inline-flex items-center flex-shrink-0 border ${GLYPH_BADGE_SHAPE_CLASSES} ${statusStyle}`}
        role="img"
        aria-label={ariaLabel}
        title={words}
      >
        {typeof Symbol === 'string' ? Symbol : Symbol ? <Symbol className="w-3 h-3" aria-hidden="true" /> : '•'}
      </span>
    );
  }

  return (
    // role="img" (not role="status", which would turn every badge in a list
    // into its own live region — see WaiverBadge).
    <span
      className={`inline-flex items-center border ${
        solid ? SOLID_BADGE_SHAPE_CLASSES : 'px-2.5 py-1 rounded-lg text-xs font-semibold'
      } ${statusStyle}`}
      role="img"
      aria-label={ariaLabel}
    >
      {Icon && <Icon className="w-3 h-3 mr-1.5 flex-shrink-0" aria-hidden="true" />}
      {displayText}
      {showConditions && (
        <span className="ml-1 font-normal normal-case tracking-normal">· with conditions</span>
      )}
      {appealSuffix && (
        <span className="ml-1 font-normal normal-case tracking-normal">· {appealSuffix}</span>
      )}
    </span>
  );
}

export default StatusBadge;
