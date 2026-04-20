import { useState, useEffect, useRef, useCallback } from 'react';
import { FEEDBACK_ENDPOINT, TURNSTILE_SITE_KEY } from '../config';

// Bump this string whenever you want to resurface the popup for a new feedback campaign.
const CAMPAIGN = 'v1';
const STORAGE_KEY = `feedback_dismissed_${CAMPAIGN}`;
const SHOW_DELAY_MS = 30_000;

function FeedbackPopup() {
  const [isVisible, setIsVisible] = useState(false);
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef(null);
  const widgetIdRef = useRef(null);

  // Show after delay unless already dismissed for this campaign
  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY)) return;
    const timer = setTimeout(() => setIsVisible(true), SHOW_DELAY_MS);
    return () => clearTimeout(timer);
  }, []);

  // Mount Turnstile widget when popup becomes visible
  useEffect(() => {
    if (!isVisible) return;

    let scriptEl = null;

    const renderWidget = () => {
      if (turnstileRef.current && widgetIdRef.current === null) {
        widgetIdRef.current = window.turnstile.render(turnstileRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
          size: 'compact',
          callback: (token) => setTurnstileToken(token),
          'expired-callback': () => setTurnstileToken(''),
          'error-callback': () => setTurnstileToken(''),
        });
      }
    };

    if (window.turnstile) {
      renderWidget();
    } else {
      scriptEl = document.createElement('script');
      scriptEl.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      scriptEl.async = true;
      scriptEl.onload = renderWidget;
      document.head.appendChild(scriptEl);
    }

    return () => {
      if (widgetIdRef.current !== null && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current);
        widgetIdRef.current = null;
      }
    };
  }, [isVisible]);

  const dismiss = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, '1');
    setIsVisible(false);
  }, []);

  const resetTurnstile = () => {
    setTurnstileToken('');
    if (widgetIdRef.current !== null && window.turnstile) {
      window.turnstile.reset(widgetIdRef.current);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!message.trim() || !turnstileToken) return;
    setStatus('loading');
    setErrorMsg('');
    try {
      const resp = await fetch(FEEDBACK_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message.trim(),
          email: email.trim() || undefined,
          'cf-turnstile-response': turnstileToken,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        setErrorMsg(data.error || 'Something went wrong. Please try again.');
        setStatus('error');
        resetTurnstile();
      } else {
        setStatus('success');
        setTimeout(dismiss, 3000);
      }
    } catch {
      setErrorMsg('Could not connect. Please try again.');
      setStatus('error');
      resetTurnstile();
    }
  };

  if (!isVisible) return null;

  return (
    <div
      role="dialog"
      aria-label="Share feedback"
      className="fixed bottom-4 right-4 z-50 w-80 rounded-2xl bg-white shadow-elevated border border-gray-200 overflow-hidden animate-slide-up"
    >
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-800">Share your feedback</h3>
        <button
          onClick={dismiss}
          aria-label="Dismiss"
          className="text-gray-400 hover:text-gray-600 transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-4">
        {status === 'success' ? (
          <div className="flex items-center gap-3 py-1">
            <svg className="h-5 w-5 text-primary shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
            </svg>
            <p className="text-sm text-gray-700">Thanks for your feedback!</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <p className="text-xs text-gray-500">Got a suggestion or spotted an issue? Let me know.</p>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Your feedback…"
              rows={3}
              maxLength={5000}
              disabled={status === 'loading'}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary resize-none disabled:opacity-50"
            />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Your email (optional, if you'd like a reply)"
              disabled={status === 'loading'}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
            />
            <div ref={turnstileRef} />
            {status === 'error' && (
              <p className="text-xs text-red-600">{errorMsg}</p>
            )}
            <button
              type="submit"
              disabled={status === 'loading' || !message.trim() || !turnstileToken}
              className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50"
            >
              {status === 'loading' ? 'Sending…' : 'Send feedback'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default FeedbackPopup;
