import { useEffect, useRef, useState } from 'react';

/**
 * Entrance animations for things that should play as they scroll into view —
 * the /merged deck's counting figures and growing bars.
 *
 * Both hooks share one rule: **the final state is the default.** Where the
 * animation can't or shouldn't run — a reader who asked for reduced motion, a
 * browser without IntersectionObserver, the build-time prerender, jsdom — the
 * element renders finished, with the real figure in the DOM, and nothing ever
 * animates from a zero that a screen reader or a crawler might read.
 */

const COUNT_MS = 900;

/**
 * Whether an entrance should animate at all.
 *
 * `matchMedia` missing counts as "don't": it is absent in jsdom and in the
 * prerender, and in both of those the right answer is to draw the end state.
 */
function canAnimate() {
  if (typeof window === 'undefined') return false;
  if (typeof IntersectionObserver === 'undefined') return false;
  if (typeof window.matchMedia !== 'function') return false;
  return !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * `[ref, entered]` for an element that animates in.
 *
 * `entered` means "show the final state". It starts true wherever the
 * animation won't run, and otherwise flips once the element is in view —
 * once, so scrolling back up doesn't replay it.
 */
export function useEntrance({ threshold = 0.35 } = {}) {
  const ref = useRef(null);
  const [entered, setEntered] = useState(() => !canAnimate());

  useEffect(() => {
    if (entered) return undefined;
    const element = ref.current;
    if (!element) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) setEntered(true);
      },
      { threshold },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [entered, threshold]);

  return [ref, entered];
}

/**
 * `[ref, shown]` for a figure that counts up to `target` as it arrives.
 *
 * `shown` is the number to render this frame, and is `target` from the first
 * render wherever the count won't run. The ramp plays once per value.
 */
export function useCountUp(target, { duration = COUNT_MS } = {}) {
  const [ref, entered] = useEntrance();
  // Decided once, at mount, and read by both the initial value and the
  // effect: without it the effect would have to correct the state it is
  // already rendering with, which is a cascading render for nothing.
  const [counting] = useState(canAnimate);
  const [shown, setShown] = useState(() => (counting ? 0 : target));
  const played = useRef(false);

  // A card whose figure changes under it (a background refresh) counts again.
  useEffect(() => {
    played.current = false;
  }, [target]);

  useEffect(() => {
    if (!entered || played.current || !counting) return undefined;
    played.current = true;

    let frame = null;
    const started = performance.now();
    const tick = (now) => {
      const progress = Math.min(1, (now - started) / duration);
      // Ease out: fast off the mark, settling onto the figure rather than
      // stopping dead on it.
      setShown(target * (1 - (1 - progress) ** 3));
      if (progress < 1) frame = requestAnimationFrame(tick);
      else setShown(target);
    };
    frame = requestAnimationFrame(tick);
    return () => {
      if (frame) cancelAnimationFrame(frame);
    };
  }, [entered, counting, target, duration]);

  return [ref, shown];
}

/**
 * `[ref, {total, filled}]` for a business-day rail that fills as it arrives.
 *
 * A rail that fits its statutory clock just fills: nothing to 18 of 30. A rail
 * that *outgrew* it fills twice, which is the whole point of the card it sits
 * on — the clock runs out at day 30, and only then does the rail grow to 56
 * and the days past the limit appear. The ticks are flexed, so growing the
 * total squeezes them, and the statutory marker slides left as it happens.
 *
 * As everywhere else here, the finished rail is the default.
 */
export function useRailFill({ used, total, statutory }, { stage = 700, pause = 250 } = {}) {
  const [ref, entered] = useEntrance();
  const [filling] = useState(canAnimate);
  const grows = total > statutory;
  const final = { total, filled: used };

  const [frameState, setFrameState] = useState(() =>
    filling ? { total: grows ? statutory : total, filled: 0 } : final,
  );
  const played = useRef(false);

  useEffect(() => {
    played.current = false;
  }, [used, total, statutory]);

  useEffect(() => {
    if (!entered || played.current || !filling) return undefined;
    played.current = true;

    // Stage one fills the clock itself; stage two, only for a rail that ran
    // past it, grows the rail and fills what is left in the overrun's colour.
    const firstFill = grows ? statutory : used;
    const span = grows ? stage + pause + stage : stage;
    let frame = null;
    const started = performance.now();

    const tick = (now) => {
      const elapsed = now - started;
      const ease = (p) => 1 - (1 - Math.min(1, Math.max(0, p))) ** 3;

      if (!grows) {
        setFrameState({ total, filled: firstFill * ease(elapsed / stage) });
      } else if (elapsed < stage + pause) {
        setFrameState({ total: statutory, filled: firstFill * ease(elapsed / stage) });
      } else {
        const p = ease((elapsed - stage - pause) / stage);
        setFrameState({
          total: statutory + (total - statutory) * p,
          filled: statutory + (used - statutory) * p,
        });
      }

      if (elapsed < span) frame = requestAnimationFrame(tick);
      else setFrameState(final);
    };

    frame = requestAnimationFrame(tick);
    return () => {
      if (frame) cancelAnimationFrame(frame);
    };
    // `final` is rebuilt each render; its parts are the real dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entered, filling, grows, used, total, statutory, stage, pause]);

  return [ref, frameState];
}
