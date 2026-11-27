import { GLYPH_ICONS, glyphTone } from '../constants/mergedTones';
import { outcomeShape, shapeClipPath } from '../utils/materialShapes';

/**
 * An outcome as a Material shape, as the Android app's StatusGlyph: the
 * outcome's own outline (the sunny seal for cleared, the four-sided cookie for
 * refused, the twelve-sided cookie while it runs, the gem for ceased) filled
 * in the outcome's colour, with its glyph inside.
 *
 * `size` is in pixels because `clip-path: path()` is: the path is generated at
 * the tile's exact size, so the caller fixes it rather than letting the layout
 * decide. Shape is never the only signal — the outcome goes to the accessible
 * name unless `decorative`, where the words are already beside it.
 */
export default function MaterialShape({ status, size = 36, decorative = false, className = '' }) {
  const Icon = GLYPH_ICONS[status] || null;
  return (
    <span
      {...(decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': status })}
      className={`inline-grid flex-shrink-0 place-items-center ${glyphTone(status)} ${className}`}
      style={{
        width: size,
        height: size,
        clipPath: shapeClipPath(outcomeShape(status), size),
      }}
    >
      {Icon ? (
        <Icon style={{ width: size * 0.4, height: size * 0.4 }} aria-hidden="true" />
      ) : (
        <span
          className="rounded-full bg-current"
          style={{ width: size * 0.22, height: size * 0.22 }}
          aria-hidden="true"
        />
      )}
    </span>
  );
}
