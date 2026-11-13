import {
  STATUS_COLORS,
  SOLID_STATUS_COLORS,
  EMPHATIC_OUTCOMES,
  DEFAULT_STATUS_STYLE,
  DEFAULT_SOLID_STATUS_STYLE,
  GLYPH_BADGE_SHAPE_CLASSES,
  SOLID_BADGE_SHAPE_CLASSES,
} from '../constants/mergerStatus';
import { OUTCOME_ICONS, LIVE_GLYPHS } from '../constants/outcomeIcons';
import { resolveStatusDisplay } from '../utils/statusDisplay';

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
  // Which outcome the badge speaks for, shared with StatusGlyph
  // (utils/statusDisplay.js) so the two always agree. Everything below —
  // colour, emphasis, glyph — keys off styleKey, so they cannot end up
  // describing different outcomes. 'Declined' and 'Not approved' share the
  // same red palette (both map to the same STATUS_COLORS entry).
  const { styleKey, displayText, showConditions, appealSuffix, ariaLabel } =
    resolveStatusDisplay({ status, determination, label, hasConditions, appeal });

  const filled = solid || glyph || EMPHATIC_OUTCOMES.includes(styleKey);
  const statusStyle =
    (styleKey && (filled ? SOLID_STATUS_COLORS[styleKey] : STATUS_COLORS[styleKey])) ||
    (solid ? DEFAULT_SOLID_STATUS_STYLE : DEFAULT_STATUS_STYLE);

  // A glyph as well as a colour, so an outcome is not distinguished by colour
  // alone (WCAG 1.4.1) and can be picked out of a long list without reading
  // it. Only decided outcomes have one; a live matter shows text only.
  const Icon = styleKey ? OUTCOME_ICONS[styleKey] : null;

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
        {Symbol ? <Symbol className="w-3 h-3" aria-hidden="true" /> : '•'}
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
