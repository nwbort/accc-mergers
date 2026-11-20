import { shapePath, LOADING_SEQUENCE } from '../utils/materialShapes';

// Material 3 Expressive's loading indicator, as the app's `LoadingIndicator`:
// a shape that turns while it morphs from one of the Material shapes into the
// next. Every path has the same commands (utils/materialShapes.js), which is
// what lets SMIL's <animate> tween between them. Under reduced motion it
// holds still: SMIL ignores the stylesheet's prefers-reduced-motion rule, so
// the animation elements are left out instead.
const MORPH_VALUES = [...LOADING_SEQUENCE, LOADING_SEQUENCE[0]].map(shapePath).join(';');
const STEP_SECONDS = 0.65;
const DURATION = `${LOADING_SEQUENCE.length * STEP_SECONDS}s`;
const KEY_TIMES = LOADING_SEQUENCE.map((_, i) => i / LOADING_SEQUENCE.length).concat(1).join(';');
// Each step springs: quick out of one shape, settling into the next.
const KEY_SPLINES = LOADING_SEQUENCE.map(() => '0.3 0 0 1').join(';');

function prefersReducedMotion() {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

// The indicator itself. Also used on its own where something loads inside a
// page (an expanded industry row, the notification panel), so those match
// the full-page state.
export function Spinner({ className = '' }) {
  const still = prefersReducedMotion();
  return (
    <div
      className={`relative h-12 w-12 rounded-full bg-primary-container flex items-center justify-center ${className}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 100 100" className="h-8 w-8 text-primary">
        <g>
          {!still && (
            <animateTransform
              attributeName="transform"
              type="rotate"
              values="0 50 50;360 50 50"
              dur={DURATION}
              repeatCount="indefinite"
            />
          )}
          <path d={shapePath(LOADING_SEQUENCE[0])} fill="currentColor">
            {!still && (
              <animate
                attributeName="d"
                values={MORPH_VALUES}
                keyTimes={KEY_TIMES}
                keySplines={KEY_SPLINES}
                calcMode="spline"
                dur={DURATION}
                repeatCount="indefinite"
              />
            )}
          </path>
        </g>
      </svg>
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div
      className="flex flex-col justify-center items-center min-h-screen gap-3"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <Spinner />
      <span className="sr-only">Loading...</span>
    </div>
  );
}

export default LoadingSpinner;
