import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useTurnstile } from '../useTurnstile';

// Stand-in for the Cloudflare widget API, capturing the callbacks the hook
// registers so a test can fire "solved" / "expired" / "errored".
function fakeTurnstile() {
  const api = {
    render: vi.fn((_el, opts) => {
      api.lastOptions = opts;
      return 'widget-1';
    }),
    remove: vi.fn(),
    reset: vi.fn(),
    lastOptions: null,
  };
  return api;
}

function Harness({ onHook }) {
  const { ref, token, reset } = useTurnstile();
  onHook({ token, reset });
  return <div data-testid="turnstile" ref={ref} />;
}

function injectedScripts() {
  return [...document.head.querySelectorAll('script')].filter(
    (el) => el.src.includes('challenges.cloudflare.com')
  );
}

afterEach(() => {
  delete window.turnstile;
  injectedScripts().forEach((el) => el.remove());
});

describe('useTurnstile', () => {
  describe('when the script is already loaded', () => {
    beforeEach(() => {
      window.turnstile = fakeTurnstile();
    });

    it('renders the widget into the element carrying the returned ref', () => {
      const { getByTestId } = render(<Harness onHook={() => {}} />);
      expect(window.turnstile.render).toHaveBeenCalledTimes(1);
      expect(window.turnstile.render.mock.calls[0][0]).toBe(getByTestId('turnstile'));
    });

    it('starts with an empty token, so a form cannot submit yet', () => {
      let hook;
      render(<Harness onHook={(h) => { hook = h; }} />);
      expect(hook.token).toBe('');
    });

    it('exposes the token once the challenge is solved', () => {
      let hook;
      render(<Harness onHook={(h) => { hook = h; }} />);
      act(() => window.turnstile.lastOptions.callback('tok-abc'));
      expect(hook.token).toBe('tok-abc');
    });

    it.each(['expired-callback', 'error-callback'])('clears the token on %s', (event) => {
      let hook;
      render(<Harness onHook={(h) => { hook = h; }} />);
      act(() => window.turnstile.lastOptions.callback('tok-abc'));
      act(() => window.turnstile.lastOptions[event]());
      expect(hook.token).toBe('');
    });

    it('reset clears the token and asks for a fresh challenge', () => {
      // A token is single-use, so a rejected submit has to start over.
      let hook;
      render(<Harness onHook={(h) => { hook = h; }} />);
      act(() => window.turnstile.lastOptions.callback('tok-abc'));
      act(() => hook.reset());
      expect(hook.token).toBe('');
      expect(window.turnstile.reset).toHaveBeenCalledWith('widget-1');
    });

    it('removes the widget on unmount', () => {
      // Without this a SPA route away and back leaves a dead widget behind.
      const { unmount } = render(<Harness onHook={() => {}} />);
      unmount();
      expect(window.turnstile.remove).toHaveBeenCalledWith('widget-1');
    });

    it('leaves a script it did not inject alone', () => {
      const existing = document.createElement('script');
      existing.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      document.head.appendChild(existing);
      const { unmount } = render(<Harness onHook={() => {}} />);
      unmount();
      expect(injectedScripts()).toContain(existing);
      existing.remove();
    });
  });

  describe('when the script has not loaded yet', () => {
    it('injects it and renders the widget on load', () => {
      render(<Harness onHook={() => {}} />);
      const [script] = injectedScripts();
      expect(script).toBeDefined();
      expect(script.async).toBe(true);

      window.turnstile = fakeTurnstile();
      act(() => script.onload());
      expect(window.turnstile.render).toHaveBeenCalledTimes(1);
    });

    it('removes the injected script on unmount', () => {
      // The copy in Digest.jsx did this and the one in Feedback.jsx did not;
      // the hook is what keeps the two from disagreeing again.
      const { unmount } = render(<Harness onHook={() => {}} />);
      expect(injectedScripts()).toHaveLength(1);
      unmount();
      expect(injectedScripts()).toHaveLength(0);
    });
  });
});
