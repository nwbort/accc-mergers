import { OUTCOME_ICONS, LIVE_GLYPHS } from '../constants/outcomeIcons';
import { getOutcomeCardStyle } from '../constants/outcomeCard';
import { outcomeShape, shapeClipPath } from '../utils/materialShapes';
import { resolveStatusDisplay } from '../utils/statusDisplay';

const SIZE = 32;

/**
 * An outcome as a symbol, as the Android app's StatusGlyph: the outcome's
 * Material shape (approved's sunny seal, refused's four-sided cookie, the
 * live clock's twelve-sided cookie, ceased's gem) filled in its colour, with
 * the outcome's glyph inside. role="img" with the outcome in words, like
 * every badge, so neither colour nor shape is the only signal. `decorative`
 * hides it from assistive tech where the outcome is written out beside it.
 */
function StatusGlyph({ status, determination, hasConditions, appeal, decorative = false }) {
  const { styleKey, ariaLabel } = resolveStatusDisplay({ status, determination, hasConditions, appeal });
  const Icon = (styleKey && (OUTCOME_ICONS[styleKey] || LIVE_GLYPHS[styleKey])) || null;
  return (
    <span
      {...(decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': ariaLabel })}
      className={`inline-flex flex-shrink-0 items-center justify-center h-8 w-8 ${getOutcomeCardStyle(styleKey).glyph}`}
      style={{ clipPath: shapeClipPath(outcomeShape(styleKey), SIZE) }}
    >
      {Icon ? (
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <span className="h-2 w-2 rounded-full bg-current" aria-hidden="true" />
      )}
    </span>
  );
}

export default StatusGlyph;
