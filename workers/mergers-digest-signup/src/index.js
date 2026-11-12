/**
 * Cloudflare Worker — mergers.fyi signup + feedback handler
 *
 * Routes:
 *   POST /          — digest email signup (adds contact to Resend audience)
 *   POST /app-signup — digest signup from the Android app: no Turnstile, so
 *                      it emails a link to confirm instead (double opt-in)
 *   GET  /confirm   — the emailed link: a page with a button to confirm
 *   POST /confirm   — that button: adds the contact to the Resend audience
 *   POST /feedback  — stores feedback in Cloudflare D1
 *   POST /event     — increments an aggregate, privacy-preserving feature-usage counter
 *
 * Required Worker secrets (set via `wrangler secret put`):
 *   RESEND_API_KEY        — Resend API key
 *   RESEND_AUDIENCE_ID    — Resend audience ID (signup only)
 *   TURNSTILE_SECRET_KEY  — Cloudflare Turnstile secret key
 *   CONFIRM_SECRET        — optional: signs the app's confirmation links;
 *                           without it, a key derived from RESEND_API_KEY
 *
 * Required D1 binding (wrangler.toml):
 *   DB  — mergers-feedback D1 database
 *
 * Required KV binding (wrangler.toml):
 *   RATE_LIMIT_KV  — per-IP rate limit counters
 *
 * To view feedback: Cloudflare Dashboard → D1 → mergers-feedback → Console
 *   SELECT * FROM feedback ORDER BY created_at DESC;
 */

const RESEND_API_BASE = "https://api.resend.com";
const TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

const ALLOWED_ORIGIN = "https://mergers.fyi";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Feature-usage events the frontend is allowed to ping. Each entry is an
// aggregate daily counter only — no user identifiers of any kind are ever
// attached. To start tracking a new feature, add its event name here and
// have the frontend call pingFeatureEvent() (frontend/src/utils/trackEvent.js)
// at the point of use; no schema change or new endpoint is needed.
const ALLOWED_EVENT_TYPES = new Set([
  "feedback_popup_dismissed", // the feedback popup's close button was clicked
  "feedback_popup_clicked", // the feedback popup's "Share feedback" link was clicked
  "promo_card_dismissed", // the dashboard promo card's close button was clicked
  "promo_card_clicked", // the dashboard promo card was clicked through
]);

// A merger was added to the user's tracked list: `track_merger_{id}`, one
// counter per merger (e.g. track_merger_MN-01016). Matched by pattern, not
// listed, since the set of merger ids grows with the register.
const TRACK_MERGER_EVENT_RE = /^track_merger_(MN|WA)-\d{5}$/;

// An industry was followed: `track_industry_{code}`, one counter per ANZSIC
// node — a division letter (A-S) or a 2-4 digit subdivision/group/class code
// (e.g. track_industry_F, track_industry_4520). Matched by pattern for the
// same reason as the merger counter.
const TRACK_INDUSTRY_EVENT_RE = /^track_industry_([A-S]|\d{2,4})$/;

function isAllowedEventType(type) {
  return (
    ALLOWED_EVENT_TYPES.has(type) ||
    TRACK_MERGER_EVENT_RE.test(type) ||
    TRACK_INDUSTRY_EVENT_RE.test(type)
  );
}

// ---------------------------------------------------------------------------
// CORS helpers
// ---------------------------------------------------------------------------

function corsHeaders(origin, env = {}) {
  const allowedOrigins = env.ENVIRONMENT === 'development'
    ? [ALLOWED_ORIGIN, "http://localhost:5173", "http://localhost:4173"]
    : [ALLOWED_ORIGIN];
  const responseOrigin = allowedOrigins.includes(origin) ? origin : ALLOWED_ORIGIN;
  return {
    "Access-Control-Allow-Origin": responseOrigin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
}

function jsonResponse(body, status, origin = "", env = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(origin, env),
    },
  });
}

// ---------------------------------------------------------------------------
// Rate limiting: fixed-window counter in KV, keyed by IP + route
// ---------------------------------------------------------------------------

// Returns true if the request is within the limit, false if it should be
// rejected with 429. KV is eventually consistent, so under concurrent bursts
// the effective limit may be exceeded slightly — acceptable for abuse
// prevention (this isn't a billing-critical limit).
// KV rejects an expirationTtl under this many seconds.
const KV_MIN_TTL_SECONDS = 60;

async function checkRateLimit(env, key, limit, windowSeconds) {
  try {
    const now = Date.now();
    const raw = await env.RATE_LIMIT_KV.get(key);
    let entry = raw ? JSON.parse(raw) : null;

    if (!entry || typeof entry.count !== "number" || !(entry.resetAt > now)) {
      entry = { count: 0, resetAt: now + windowSeconds * 1000 };
    }

    // Already over the limit: reject without another write, so a client being
    // refused can't keep spending the namespace's write quota.
    if (entry.count >= limit) return false;

    entry.count += 1;
    // The TTL is only garbage collection (resetAt above is what ends the
    // window), so clamping it to KV's minimum is harmless. Unclamped, a
    // request in the last minute of a window made the put throw.
    await env.RATE_LIMIT_KV.put(key, JSON.stringify(entry), {
      expirationTtl: Math.max(KV_MIN_TTL_SECONDS, Math.ceil((entry.resetAt - now) / 1000) + 1),
    });

    return true;
  } catch (err) {
    // KV unavailable or its write quota spent. Fail open: the limiter is abuse
    // prevention, and signup and feedback are still gated by Turnstile, so a
    // KV outage shouldn't take the endpoints down with it.
    console.error("Rate limit check failed, allowing request:", err);
    return true;
  }
}

// ---------------------------------------------------------------------------
// Shared: verify Turnstile token
// ---------------------------------------------------------------------------

async function verifyTurnstile(token, remoteIp, env) {
  const resp = await fetch(TURNSTILE_VERIFY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      secret: env.TURNSTILE_SECRET_KEY,
      response: token,
      remoteip: remoteIp || undefined,
    }),
  });
  const data = await resp.json().catch(() => ({}));
  return { ok: !!data.success, status: resp.status, errorCodes: data["error-codes"] };
}

/**
 * Run the Turnstile check for a handler, returning an error Response to send
 * back, or null when the token is good and the handler should carry on.
 *
 * Both protected endpoints (signup and feedback) need the identical
 * missing-token / network-error / rejected-token treatment, down to the status
 * codes and the message the browser shows, so it is written once here. The
 * caller does its own cheap validation first — there is no point burning a
 * Turnstile round trip on a request that is already malformed.
 */
async function turnstileGate(token, request, env, origin) {
  if (!token) {
    return jsonResponse({ error: "CAPTCHA verification required" }, 400, origin, env);
  }

  let result;
  try {
    result = await verifyTurnstile(token, request.headers.get("CF-Connecting-IP"), env);
  } catch (err) {
    // Cloudflare unreachable — a 503 says "retry", not "you failed".
    console.error("Network error verifying Turnstile token:", err);
    return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 503, origin, env);
  }

  if (!result.ok) {
    const codes = Array.isArray(result.errorCodes) ? result.errorCodes.join(",") : "unknown";
    console.error("Turnstile verification failed:", result.status, codes);
    return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 400, origin, env);
  }

  return null;
}

// ---------------------------------------------------------------------------
// Request body helpers
// ---------------------------------------------------------------------------

// Parse the JSON body as a plain object, or return null. A body of `null`, an
// array or a bare scalar is valid JSON but not a request we understand.
async function readJsonObject(request) {
  try {
    const body = await request.json();
    return body && typeof body === "object" && !Array.isArray(body) ? body : null;
  } catch {
    return null;
  }
}

// A trimmed string field, or "" when it is missing or not a string, so a
// mistyped field fails validation as a 400 rather than throwing.
function stringField(body, key) {
  return typeof body[key] === "string" ? body[key].trim() : "";
}

// ---------------------------------------------------------------------------
// Handler: POST / — digest email signup
// ---------------------------------------------------------------------------

async function handleSubscribe(request, env, origin) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const withinLimit = await checkRateLimit(env, `signup:${ip}`, 5, 600);
  if (!withinLimit) {
    return jsonResponse(
      { error: "Too many attempts. Please try again in a few minutes." },
      429,
      origin,
      env
    );
  }

  const body = await readJsonObject(request);
  if (!body) {
    return jsonResponse({ error: "Invalid request body" }, 400, origin, env);
  }

  const email = stringField(body, "email").toLowerCase();
  const turnstileToken = stringField(body, "cf-turnstile-response");

  if (!email) {
    return jsonResponse({ error: "Email address is required" }, 400, origin, env);
  }

  if (!EMAIL_RE.test(email)) {
    return jsonResponse({ error: "Please enter a valid email address" }, 400, origin, env);
  }

  const turnstileError = await turnstileGate(turnstileToken, request, env, origin);
  if (turnstileError) return turnstileError;

  if (!(await addContact(email, env))) {
    return jsonResponse({ error: "Failed to subscribe. Please try again." }, 500, origin, env);
  }

  return jsonResponse(
    { success: true, message: "Subscribed! You\u2019ll get the weekly digest every Monday." },
    200,
    origin,
    env
  );
}

/**
 * Add [email] to the digest's Resend audience. True when it's on the list
 * (a 409, already there, counts), false when Resend couldn't be reached or
 * refused it.
 */
async function addContact(email, env) {
  let resendResp;
  try {
    resendResp = await fetch(
      `${RESEND_API_BASE}/audiences/${env.RESEND_AUDIENCE_ID}/contacts`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.RESEND_API_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, unsubscribed: false }),
      }
    );
  } catch (err) {
    console.error("Network error calling Resend:", err);
    return false;
  }

  if (!resendResp.ok) {
    const errData = await resendResp.json().catch(() => ({}));
    const errName = typeof errData?.name === "string" ? errData.name : "unknown";
    console.error("Resend API error:", resendResp.status, errName);
    if (resendResp.status !== 409) return false;
  }
  return true;
}


// ---------------------------------------------------------------------------
// The Android app's signup: double opt-in instead of Turnstile
//
// The app can't show Turnstile (it isn't a browser), so this route takes an
// email with no CAPTCHA and, rather than adding it, sends it a link to
// confirm. Only someone who can read that inbox can subscribe it, so the open
// route can't be used to sign up other people. The link opens a page with a
// button rather than confirming on GET: mail scanners (Outlook Safe Links and
// the like) open links in incoming mail, and would otherwise confirm for the
// reader. The link is signed (HMAC) and lasts CONFIRM_TTL_DAYS; nothing is
// stored until it is used.
// ---------------------------------------------------------------------------

const SIGNUP_ORIGIN = "https://signup.mergers.fyi";
const DEFAULT_SEND_FROM = "Australian Merger Tracker <digest@mergers.fyi>";
const CONFIRM_TTL_DAYS = 7;
// One confirmation email per address per hour, however often it's asked for,
// so the route can't be used to flood someone's inbox.
const CONFIRM_RESEND_SECONDS = 3600;
// A ceiling on confirmation emails a day across everyone, against a spread-out
// flood. Kept well under Resend's free-plan limit of 100 transactional emails a
// day, so a flood can't spend the whole allowance.
const CONFIRM_DAILY_CAP = 50;

const encoder = new TextEncoder();

function base64url(bytes) {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64url(text) {
  const bin = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// The signing key: CONFIRM_SECRET if set, else derived from the Resend key,
// which is secret already (rotating it voids links not yet used).
async function confirmKey(env) {
  const raw = env.CONFIRM_SECRET
    ? encoder.encode(env.CONFIRM_SECRET)
    : await crypto.subtle.digest("SHA-256", encoder.encode(`mergers-digest-confirm:${env.RESEND_API_KEY}`));
  return crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign", "verify"]);
}

/** A link token for [email]: its payload and signature, both base64url. */
async function signConfirmation(email, env, now = Date.now()) {
  const payload = base64url(
    encoder.encode(JSON.stringify({ e: email, x: now + CONFIRM_TTL_DAYS * 86400 * 1000 }))
  );
  const sig = await crypto.subtle.sign("HMAC", await confirmKey(env), encoder.encode(payload));
  return { t: payload, s: base64url(new Uint8Array(sig)) };
}

/** The email a link token confirms, or null if it's forged, mangled or expired. */
async function verifyConfirmation(t, s, env, now = Date.now()) {
  if (!t || !s) return null;
  try {
    const ok = await crypto.subtle.verify("HMAC", await confirmKey(env), fromBase64url(s), encoder.encode(t));
    if (!ok) return null;
    const { e, x } = JSON.parse(new TextDecoder().decode(fromBase64url(t)));
    if (typeof e !== "string" || !EMAIL_RE.test(e) || !(x > now)) return null;
    return e;
  } catch {
    return null;
  }
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

async function sendConfirmationEmail(email, env) {
  const { t, s } = await signConfirmation(email, env);
  const link = `${SIGNUP_ORIGIN}/confirm?t=${t}&s=${s}`;
  const text = [
    "Someone (we hope you) asked to get the mergers.fyi weekly digest at this address.",
    "",
    `Confirm your subscription: ${link}`,
    "",
    `The link lasts ${CONFIRM_TTL_DAYS} days. If you didn't ask for this, ignore this email and nothing more will be sent.`,
  ].join("\n");
  const html = `<p>Someone (we hope you) asked to get the <strong>mergers.fyi weekly digest</strong> at this address: a Monday catch-up on Australian merger reviews.</p>
<p><a href="${escapeHtml(link)}" style="display:inline-block;padding:10px 18px;border-radius:999px;background:#335145;color:#fff;text-decoration:none;font-weight:600">Confirm my subscription</a></p>
<p style="color:#6b7280;font-size:13px">The link lasts ${CONFIRM_TTL_DAYS} days. If you didn't ask for this, ignore this email and nothing more will be sent.</p>`;
  const resp = await fetch(`${RESEND_API_BASE}/emails`, {
    method: "POST",
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: env.SEND_FROM || DEFAULT_SEND_FROM,
      to: [email],
      subject: "Confirm your mergers.fyi weekly digest",
      text,
      html,
    }),
  });
  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({}));
    console.error("Resend send error:", resp.status, typeof errData?.name === "string" ? errData.name : "unknown");
  }
  return resp.ok;
}

async function handleAppSignup(request, env, origin) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (!(await checkRateLimit(env, `app-signup:${ip}`, 5, 600))) {
    return jsonResponse({ error: "Too many attempts. Please try again in a few minutes." }, 429, origin, env);
  }

  const body = await readJsonObject(request);
  if (!body) return jsonResponse({ error: "Invalid request body" }, 400, origin, env);
  const email = stringField(body, "email").toLowerCase();
  if (!email) return jsonResponse({ error: "Email address is required" }, 400, origin, env);
  if (!EMAIL_RE.test(email) || email.length > 254) {
    return jsonResponse({ error: "Please enter a valid email address" }, 400, origin, env);
  }

  const sent = { success: true, message: "Check your inbox: we’ve sent a link to confirm." };
  // Asked again within the hour: say the same, send nothing more.
  const perAddress = `confirm-sent:${await sha256Hex(email)}`;
  if (!(await checkRateLimit(env, perAddress, 1, CONFIRM_RESEND_SECONDS))) {
    return jsonResponse(sent, 200, origin, env);
  }
  if (!(await checkRateLimit(env, `confirm-day:${sydneyDay()}`, CONFIRM_DAILY_CAP, 86400))) {
    return jsonResponse({ error: "Sign-ups are busy right now. Please try again tomorrow." }, 503, origin, env);
  }

  let ok;
  try {
    ok = await sendConfirmationEmail(email, env);
  } catch (err) {
    console.error("Network error sending confirmation:", err);
    ok = false;
  }
  if (!ok) return jsonResponse({ error: "Couldn’t send the email. Please try again." }, 503, origin, env);
  return jsonResponse(sent, 200, origin, env);
}

function page(title, bodyHtml, status = 200) {
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title)} · mergers.fyi</title>
<style>body{font-family:system-ui,sans-serif;max-width:32rem;margin:15vh auto;padding:0 1.25rem;color:#111827;line-height:1.5}
h1{font-size:1.5rem}button,.button{display:inline-block;padding:.7rem 1.4rem;border:0;border-radius:999px;background:#335145;color:#fff;font:600 1rem system-ui,sans-serif;text-decoration:none;cursor:pointer}
p.small{color:#6b7280;font-size:.875rem}</style></head><body>${bodyHtml}</body></html>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "X-Robots-Tag": "noindex" } }
  );
}

const BAD_LINK_PAGE = () =>
  page(
    "Link expired",
    `<h1>This link has expired or isn&rsquo;t valid</h1><p>Ask again from the app, or sign up on the site.</p>
<p><a class="button" href="https://mergers.fyi/digest">Go to the digest</a></p>`,
    400
  );

// GET /confirm: the emailed link. Shows a button; nothing happens until it's pressed.
async function handleConfirmPage(request, env) {
  const url = new URL(request.url);
  const t = url.searchParams.get("t") || "";
  const s = url.searchParams.get("s") || "";
  const email = await verifyConfirmation(t, s, env);
  if (!email) return BAD_LINK_PAGE();
  return page(
    "Confirm your subscription",
    `<h1>Confirm your subscription</h1>
<p>Get the mergers.fyi weekly digest at <strong>${escapeHtml(email)}</strong> every Monday morning.</p>
<form method="post" action="/confirm"><input type="hidden" name="t" value="${escapeHtml(t)}"><input type="hidden" name="s" value="${escapeHtml(s)}">
<button type="submit">Confirm</button></form>
<p class="small">You can unsubscribe from any email. See our <a href="https://mergers.fyi/privacy">privacy policy</a>.</p>`
  );
}

// POST /confirm: the page's button. Adds the address to the list.
async function handleConfirm(request, env) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  if (!(await checkRateLimit(env, `confirm:${ip}`, 10, 600))) {
    return page("Too many attempts", "<h1>Too many attempts</h1><p>Please try again in a few minutes.</p>", 429);
  }
  let form;
  try {
    form = await request.formData();
  } catch {
    return BAD_LINK_PAGE();
  }
  const email = await verifyConfirmation(String(form.get("t") || ""), String(form.get("s") || ""), env);
  if (!email) return BAD_LINK_PAGE();
  if (!(await addContact(email, env))) {
    return page("Something went wrong", "<h1>Something went wrong</h1><p>We couldn&rsquo;t add you just now. Please press the link in the email again.</p>", 503);
  }
  return page(
    "You're subscribed",
    `<h1>You&rsquo;re subscribed</h1><p>The weekly digest will arrive at <strong>${escapeHtml(email)}</strong> every Monday morning.</p>
<p><a class="button" href="https://mergers.fyi/digest">See this week&rsquo;s digest</a></p>`
  );
}

// ---------------------------------------------------------------------------
// Handler: POST /feedback — store feedback in D1
// ---------------------------------------------------------------------------

async function handleFeedback(request, env, origin) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const withinBurstLimit = await checkRateLimit(env, `feedback:${ip}`, 5, 600);
  if (!withinBurstLimit) {
    return jsonResponse(
      { error: "Too many attempts. Please try again in a few minutes." },
      429,
      origin,
      env
    );
  }
  const withinDailyLimit = await checkRateLimit(env, `feedback-daily:${ip}`, 20, 86400);
  if (!withinDailyLimit) {
    return jsonResponse(
      { error: "You’ve reached today’s feedback limit. Please try again tomorrow." },
      429,
      origin,
      env
    );
  }

  const body = await readJsonObject(request);
  if (!body) {
    return jsonResponse({ error: "Invalid request body" }, 400, origin, env);
  }

  const message = stringField(body, "message");
  const email = stringField(body, "email").toLowerCase();
  const turnstileToken = stringField(body, "cf-turnstile-response");

  if (!message) {
    return jsonResponse({ error: "Message is required" }, 400, origin, env);
  }

  if (message.length > 5000) {
    return jsonResponse({ error: "Message is too long (max 5000 characters)" }, 400, origin, env);
  }

  if (email && !EMAIL_RE.test(email)) {
    return jsonResponse({ error: "Please enter a valid email address" }, 400, origin, env);
  }

  const turnstileError = await turnstileGate(turnstileToken, request, env, origin);
  if (turnstileError) return turnstileError;

  try {
    await env.DB.prepare(
      "INSERT INTO feedback (message, email) VALUES (?, ?)"
    ).bind(message, email || null).run();
  } catch (err) {
    console.error("D1 insert error:", err);
    return jsonResponse({ error: "Failed to save feedback. Please try again." }, 500, origin, env);
  }

  return jsonResponse({ success: true, message: "Feedback saved. Thanks!" }, 200, origin, env);
}

// ---------------------------------------------------------------------------
// Handler: POST /event — bump an aggregate feature-usage counter in D1
//
// No Turnstile here (unlike signup/feedback): there is no user content to
// protect against spam, just a counter, so IP rate limiting alone is enough
// to bound abuse. Nothing identifying is ever read from the request or
// stored — not even the IP is written to D1, it only keys the in-memory-ish
// KV rate limit window.
// ---------------------------------------------------------------------------

// en-CA formats as YYYY-MM-DD, so this needs no further reassembly; the
// timeZone conversion (not just a fixed UTC+10/+11 offset) keeps the daily
// bucket aligned with Sydney's wall-clock date across the DST transition.
function sydneyDay(date = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Australia/Sydney" }).format(date);
}

async function handleEvent(request, env, origin) {
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const withinLimit = await checkRateLimit(env, `event:${ip}`, 60, 600);
  if (!withinLimit) {
    return jsonResponse({ error: "Too many requests" }, 429, origin, env);
  }

  const body = await readJsonObject(request);
  if (!body) {
    return jsonResponse({ error: "Invalid request body" }, 400, origin, env);
  }

  const type = stringField(body, "type");
  if (!isAllowedEventType(type)) {
    return jsonResponse({ error: "Unknown event type" }, 400, origin, env);
  }

  const day = sydneyDay();

  try {
    await env.DB.prepare(
      `INSERT INTO feature_events (event_type, day, count) VALUES (?, ?, 1)
       ON CONFLICT (event_type, day) DO UPDATE SET count = count + 1`
    ).bind(type, day).run();
  } catch (err) {
    console.error("D1 event upsert error:", err);
    return jsonResponse({ error: "Failed to record event" }, 500, origin, env);
  }

  return jsonResponse({ success: true }, 200, origin, env);
}

// ---------------------------------------------------------------------------
// Main handler
// ---------------------------------------------------------------------------

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";

    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(origin, env),
      });
    }

    const path = new URL(request.url).pathname;

    if (path === "/confirm") {
      if (request.method === "GET") return handleConfirmPage(request, env);
      if (request.method === "POST") return handleConfirm(request, env);
    }

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405, origin, env);
    }

    if (path === "/app-signup") {
      return handleAppSignup(request, env, origin);
    }

    if (path === "/feedback") {
      return handleFeedback(request, env, origin);
    }

    if (path === "/event") {
      return handleEvent(request, env, origin);
    }

    return handleSubscribe(request, env, origin);
  },
};

// For the tests.
export { signConfirmation, verifyConfirmation, CONFIRM_DAILY_CAP };
