import { useEffect, useRef, useState } from 'react';
import { TURNSTILE_SITE_KEY } from '../config';

const TURNSTILE_SCRIPT_SRC =
  'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

/**
 * Mounts a Cloudflare Turnstile widget and tracks its token.
 *
 * Two forms post to the Workers API — the digest signup and the feedback form —
 * and both need the same lifecycle: load the script once if it isn't already
 * there, render the widget explicitly into a container, hold the token, clear
 * it when the challenge expires or errors, reset after a failed submit, and
 * tear the widget down on unmount. Each page used to carry its own copy, which
 * had already drifted: one removed the injected <script> on unmount and the
 * other leaked it.
 *
 * Explicit rendering (rather than the auto-rendering `cf-turnstile` class) is
 * what lets a SPA route away and back without leaving a dead widget behind.
 *
 * Usage:
 *   const { ref, token, reset } = useTurnstile();
 *   ...
 *   <div ref={ref} />
 *   <button disabled={!token}>Submit</button>
 *
 * @returns {{ ref: object, token: string, reset: () => void }}
 *   `ref` goes on the element the widget renders into; `token` is '' until the
 *   challenge is solved, so it doubles as the "ready to submit" flag; `reset`
 *   clears the token and asks Turnstile for a fresh challenge, which a form
 *   must do after a rejected submit since a token is single-use.
 */
export function useTurnstile() {
  const [token, setToken] = useState('');
  const containerRef = useRef(null);
  const widgetIdRef = useRef(null);

  useEffect(() => {
    let scriptEl = null;

    const renderWidget = () => {
      if (containerRef.current && widgetIdRef.current === null) {
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          callback: (t) => setToken(t),
          'expired-callback': () => setToken(''),
          'error-callback': () => setToken(''),
        });
      }
    };

    if (window.turnstile) {
      renderWidget();
    } else {
      scriptEl = document.createElement('script');
      scriptEl.src = TURNSTILE_SCRIPT_SRC;
      scriptEl.async = true;
      scriptEl.onload = renderWidget;
      document.head.appendChild(scriptEl);
    }

    return () => {
      if (widgetIdRef.current !== null && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
      // Only the tag this hook injected is removed — a script already on the
      // page belongs to whoever put it there.
      if (scriptEl && document.head.contains(scriptEl)) {
        document.head.removeChild(scriptEl);
      }
    };
  }, []);

  const reset = () => {
    setToken('');
    if (widgetIdRef.current !== null && window.turnstile) {
      window.turnstile.reset(widgetIdRef.current);
    }
  };

  return { ref: containerRef, token, reset };
}
