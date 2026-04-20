/**
 * Cloudflare Worker — mergers.fyi signup + feedback handler
 *
 * Routes:
 *   POST /          — digest email signup (adds contact to Resend audience)
 *   POST /feedback  — stores feedback in Cloudflare D1
 *
 * Required Worker secrets (set via `wrangler secret put`):
 *   RESEND_API_KEY        — Resend API key
 *   RESEND_AUDIENCE_ID    — Resend audience ID (signup only)
 *   TURNSTILE_SECRET_KEY  — Cloudflare Turnstile secret key
 *
 * Required D1 binding (wrangler.toml):
 *   DB  — mergers-feedback D1 database
 *
 * To view feedback: Cloudflare Dashboard → D1 → mergers-feedback → Console
 *   SELECT * FROM feedback ORDER BY created_at DESC;
 */

const RESEND_API_BASE = "https://api.resend.com";
const TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

const ALLOWED_ORIGIN = "https://mergers.fyi";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

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

// ---------------------------------------------------------------------------
// Handler: POST / — digest email signup
// ---------------------------------------------------------------------------

async function handleSubscribe(request, env, origin) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid request body" }, 400, origin, env);
  }

  const email = (body.email || "").trim().toLowerCase();
  const turnstileToken = body["cf-turnstile-response"] || "";

  if (!email) {
    return jsonResponse({ error: "Email address is required" }, 400, origin, env);
  }

  if (!EMAIL_RE.test(email)) {
    return jsonResponse({ error: "Please enter a valid email address" }, 400, origin, env);
  }

  if (!turnstileToken) {
    return jsonResponse({ error: "CAPTCHA verification required" }, 400, origin, env);
  }

  let turnstileResult;
  try {
    turnstileResult = await verifyTurnstile(
      turnstileToken,
      request.headers.get("CF-Connecting-IP"),
      env
    );
  } catch (err) {
    console.error("Network error verifying Turnstile token:", err);
    return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 503, origin, env);
  }

  if (!turnstileResult.ok) {
    const codes = Array.isArray(turnstileResult.errorCodes)
      ? turnstileResult.errorCodes.join(",")
      : "unknown";
    console.error("Turnstile verification failed:", turnstileResult.status, codes);
    return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 400, origin, env);
  }

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
    return jsonResponse({ error: "Failed to subscribe. Please try again." }, 503, origin, env);
  }

  if (!resendResp.ok) {
    const errData = await resendResp.json().catch(() => ({}));
    const errName = typeof errData?.name === "string" ? errData.name : "unknown";
    console.error("Resend API error:", resendResp.status, errName);
    if (resendResp.status !== 409) {
      return jsonResponse({ error: "Failed to subscribe. Please try again." }, 500, origin, env);
    }
  }

  return jsonResponse(
    { success: true, message: "Subscribed! You\u2019ll get the weekly digest every Monday." },
    200,
    origin,
    env
  );
}

// ---------------------------------------------------------------------------
// Handler: POST /feedback — store feedback in D1
// ---------------------------------------------------------------------------

async function handleFeedback(request, env, origin) {
  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid request body" }, 400, origin, env);
  }

  const message = (body.message || "").trim();
  const email = (body.email || "").trim().toLowerCase();
  const turnstileToken = body["cf-turnstile-response"] || "";

  if (!message) {
    return jsonResponse({ error: "Message is required" }, 400, origin, env);
  }

  if (message.length > 5000) {
    return jsonResponse({ error: "Message is too long (max 5000 characters)" }, 400, origin, env);
  }

  if (email && !EMAIL_RE.test(email)) {
    return jsonResponse({ error: "Please enter a valid email address" }, 400, origin, env);
  }

  if (!turnstileToken) {
    return jsonResponse({ error: "CAPTCHA verification required" }, 400, origin, env);
  }

  let turnstileResult;
  try {
    turnstileResult = await verifyTurnstile(
      turnstileToken,
      request.headers.get("CF-Connecting-IP"),
      env
    );
  } catch (err) {
    console.error("Network error verifying Turnstile token:", err);
    return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 503, origin, env);
  }

  if (!turnstileResult.ok) {
    const codes = Array.isArray(turnstileResult.errorCodes)
      ? turnstileResult.errorCodes.join(",")
      : "unknown";
    console.error("Turnstile verification failed:", turnstileResult.status, codes);
    return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 400, origin, env);
  }

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

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405, origin, env);
    }

    const path = new URL(request.url).pathname;

    if (path === "/feedback") {
      return handleFeedback(request, env, origin);
    }

    return handleSubscribe(request, env, origin);
  },
};
