import { useState, useEffect, useRef } from 'react';
import { FEEDBACK_ENDPOINT, TURNSTILE_SITE_KEY } from '../config';
import SEO from '../components/SEO';

export default function Feedback() {
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef(null);
  const widgetIdRef = useRef(null);

  useEffect(() => {
    let scriptEl = null;

    const renderWidget = () => {
      if (turnstileRef.current && widgetIdRef.current === null) {
        widgetIdRef.current = window.turnstile.render(turnstileRef.current, {
          sitekey: TURNSTILE_SITE_KEY,
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
      }
    } catch {
      setErrorMsg('Could not connect. Please try again.');
      setStatus('error');
      resetTurnstile();
    }
  };

  return (
    <>
      <SEO
        title="Share feedback"
        description="Share your feedback or report an issue with mergers.fyi."
        url="/feedback"
      />

      <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-12 animate-fade-in">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Share feedback</h1>
          <p className="text-gray-500">Got a suggestion or spotted an issue? Let me know.</p>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-8">
          {status === 'success' ? (
            <div className="flex items-center gap-3 py-2">
              <svg className="h-6 w-6 text-primary shrink-0" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
              </svg>
              <p className="text-gray-700">Thanks for your feedback!</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              <div>
                <label htmlFor="feedback-message" className="block text-sm font-medium text-gray-700 mb-1">
                  Message <span className="text-red-500">*</span>
                </label>
                <textarea
                  id="feedback-message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Your feedback…"
                  rows={5}
                  maxLength={5000}
                  disabled={status === 'loading'}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary resize-none disabled:opacity-50"
                />
              </div>
              <div>
                <label htmlFor="feedback-email" className="block text-sm font-medium text-gray-700 mb-1">
                  Email <span className="text-gray-400 font-normal">(optional, if you'd like a reply)</span>
                </label>
                <input
                  id="feedback-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  disabled={status === 'loading'}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                />
              </div>
              <div ref={turnstileRef} />
              {status === 'error' && (
                <p className="text-sm text-red-600">{errorMsg}</p>
              )}
              <button
                type="submit"
                disabled={status === 'loading' || !message.trim() || !turnstileToken}
                className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50"
              >
                {status === 'loading' ? 'Sending…' : 'Send feedback'}
              </button>
            </form>
          )}
        </div>
      </div>
    </>
  );
}
