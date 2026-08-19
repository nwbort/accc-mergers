import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router';
import { FaCheckCircle } from 'react-icons/fa';
import { FEEDBACK_ENDPOINT, TURNSTILE_SITE_KEY } from '../config';
import SEO from '../components/SEO';
import { CARD } from '../utils/classNames';

// Matches the textarea's maxLength — a ?message= link can seed the box, but
// never with more than someone could have typed into it themselves.
const MAX_MESSAGE_LENGTH = 5000;

export default function Feedback() {
  // Pages that know what they'd like reported (e.g. the pre-notification
  // estimate callout) link here with the message part-written, naming the
  // matter so the reply arrives attached to something.
  const [searchParams] = useSearchParams();
  const prefill = (searchParams.get('message') || '').slice(0, MAX_MESSAGE_LENGTH);
  const [message, setMessage] = useState(prefill);
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef(null);
  const widgetIdRef = useRef(null);
  const messageRef = useRef(null);

  // Land in the message box with the caret after the part already written, so
  // a seeded message is finished rather than edited.
  useEffect(() => {
    if (!prefill || !messageRef.current) return;
    messageRef.current.focus();
    messageRef.current.setSelectionRange(prefill.length, prefill.length);
    // Seeded once on arrival; retyping the URL is what changes it after that.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

        <div className={`${CARD} p-8`}>
          {status === 'success' ? (
            <div className="flex items-center gap-3 py-2">
              <FaCheckCircle className="h-6 w-6 text-primary shrink-0" aria-hidden="true" />
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
                  ref={messageRef}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Your feedback…"
                  rows={5}
                  maxLength={MAX_MESSAGE_LENGTH}
                  disabled={status === 'loading'}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary resize-none disabled:opacity-50"
                />
              </div>
              <div>
                <label htmlFor="feedback-email" className="block text-sm font-medium text-gray-700 mb-1">
                  Email <span className="text-gray-500 font-normal">(optional, if you'd like a reply)</span>
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
