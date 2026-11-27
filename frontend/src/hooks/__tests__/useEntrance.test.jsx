import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useCountUp, useEntrance } from '../useEntrance';

// The point of these hooks is that the *finished* state is the default: a
// reader with reduced motion, a crawler, the build-time prerender and jsdom
// all get the real figure, and only a browser that can animate ever sees a
// zero. That is easy to invert by accident and impossible to see in a
// screenshot, so both paths are pinned here.

function Counter({ value }) {
  const [ref, shown] = useCountUp(value);
  return <span ref={ref} data-testid="figure">{shown.toFixed(1)}</span>;
}

function Entrance() {
  const [ref, entered] = useEntrance();
  return <span ref={ref} data-testid="state">{entered ? 'final' : 'start'}</span>;
}

/** A browser that can animate: matchMedia present and not asking for less. */
function animatingBrowser() {
  const observers = [];
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
  vi.stubGlobal(
    'IntersectionObserver',
    class {
      constructor(callback) {
        this.callback = callback;
        observers.push(this);
      }
      observe() {}
      disconnect() {}
      enter() {
        this.callback([{ isIntersecting: true }]);
      }
    },
  );
  return observers;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('useCountUp', () => {
  it('renders the real figure where it cannot animate', () => {
    // jsdom has no matchMedia, which is the same answer the prerender needs.
    render(<Counter value={896} />);
    expect(screen.getByTestId('figure')).toHaveTextContent('896.0');
  });

  it('renders the real figure when the reader asked for reduced motion', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }));
    vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} });
    render(<Counter value={99.7} />);
    expect(screen.getByTestId('figure')).toHaveTextContent('99.7');
  });

  it('starts at zero and lands on the figure once the card arrives', async () => {
    const observers = animatingBrowser();
    const frames = [];
    vi.stubGlobal('requestAnimationFrame', (fn) => frames.push(fn));
    vi.stubGlobal('cancelAnimationFrame', () => {});

    render(<Counter value={100} />);
    expect(screen.getByTestId('figure')).toHaveTextContent('0.0');

    act(() => observers.at(-1).enter());
    // Run the ramp to completion: the last frame must settle exactly on the
    // figure rather than wherever the easing happened to stop.
    act(() => {
      while (frames.length) frames.shift()(performance.now() + 10_000);
    });
    expect(screen.getByTestId('figure')).toHaveTextContent('100.0');
  });

  it('counts only once, so scrolling back does not replay it', () => {
    const observers = animatingBrowser();
    const frames = [];
    vi.stubGlobal('requestAnimationFrame', (fn) => frames.push(fn));
    vi.stubGlobal('cancelAnimationFrame', () => {});

    render(<Counter value={50} />);
    act(() => observers.at(-1).enter());
    act(() => {
      while (frames.length) frames.shift()(performance.now() + 10_000);
    });
    expect(screen.getByTestId('figure')).toHaveTextContent('50.0');

    act(() => observers.at(-1).enter());
    expect(frames).toHaveLength(0);
    expect(screen.getByTestId('figure')).toHaveTextContent('50.0');
  });
});

describe('useEntrance', () => {
  it('is already finished where it cannot animate', () => {
    render(<Entrance />);
    expect(screen.getByTestId('state')).toHaveTextContent('final');
  });

  it('waits for the element to come into view where it can', () => {
    const observers = animatingBrowser();
    render(<Entrance />);
    expect(screen.getByTestId('state')).toHaveTextContent('start');

    act(() => observers.at(-1).enter());
    expect(screen.getByTestId('state')).toHaveTextContent('final');
  });
});
