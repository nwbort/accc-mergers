import { shapePath } from '../utils/materialShapes';

/**
 * One of Material 3 Expressive's shapes (utils/materialShapes.js) as an
 * inline SVG filled with `currentColor`, so its colour is a text utility
 * (`text-primary`). Decorative by default; anything it means has to be said
 * in words beside it, as the outcome glyphs do.
 *
 * `children` are drawn on top in the same 100×100 box, for a glyph inside the
 * shape.
 */
function MaterialShape({ shape, className = '', children, style }) {
  return (
    <svg
      viewBox="0 0 100 100"
      className={className}
      style={style}
      aria-hidden="true"
      focusable="false"
    >
      <path d={shapePath(shape)} fill="currentColor" />
      {children}
    </svg>
  );
}

export default MaterialShape;
