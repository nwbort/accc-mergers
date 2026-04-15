/**
 * Cloudflare Worker — mergers.fyi digest email signup handler
 *
 * Accepts POST requests from the signup form on mergers.fyi,
 * validates the email address, verifies the Cloudflare Turnstile
 * CAPTCHA token, and adds the contact to the configured Resend audience.
 *
 * Required Worker secrets (set via `wrangler secret put`):
 *   RESEND_API_KEY        — Resend API key
 *   RESEND_AUDIENCE_ID    — Resend audience ID
 *   TURNSTILE_SECRET_KEY  — Cloudflare Turnstile secret key
 */

const RESEND_API_BASE = "https://api.resend.com";
const TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

// Allowed origin for CORS — update if you serve the form from a different domain
const ALLOWED_ORIGIN = "https://mergers.fyi";

// Simple but robust email regex
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// ---------------------------------------------------------------------------
// CORS helpers
// ---------------------------------------------------------------------------

function corsHeaders(origin, env = {}) {
  // Only allow localhost origins in development environments
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
// Main handler
// ---------------------------------------------------------------------------

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";

    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(origin, env),
      });
    }

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405, origin, env);
    }

    // Parse body
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

    // Verify Turnstile CAPTCHA token
    if (!turnstileToken) {
      return jsonResponse({ error: "CAPTCHA verification required" }, 400, origin, env);
    }

    let turnstileResp;
    try {
      turnstileResp = await fetch(TURNSTILE_VERIFY_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          secret: env.TURNSTILE_SECRET_KEY,
          response: turnstileToken,
          remoteip: request.headers.get("CF-Connecting-IP") || undefined,
        }),
      });
    } catch (err) {
      console.error("Network error verifying Turnstile token:", err);
      return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 503, origin, env);
    }

    const turnstileData = await turnstileResp.json().catch(() => ({}));
    if (!turnstileData.success) {
      // Log only the error codes array — never the full response, which can
      // include the user's IP or other request metadata.
      const codes = Array.isArray(turnstileData["error-codes"])
        ? turnstileData["error-codes"].join(",")
        : "unknown";
      console.error("Turnstile verification failed:", turnstileResp.status, codes);
      return jsonResponse({ error: "CAPTCHA verification failed. Please try again." }, 400, origin, env);
    }

    // Add contact to Resend audience
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
          body: JSON.stringify({
            email,
            unsubscribed: false,
          }),
        }
      );
    } catch (err) {
      console.error("Network error calling Resend:", err);
      return jsonResponse({ error: "Failed to subscribe. Please try again." }, 503, origin, env);
    }

    if (!resendResp.ok) {
      // Consume the body so the socket can be reused, but do not log it — Resend
      // error payloads echo the submitted email address, which would leak PII
      // into Cloudflare Logs. Log only the status and Resend's short "name" code.
      const errData = await resendResp.json().catch(() => ({}));
      const errName = typeof errData?.name === "string" ? errData.name : "unknown";
      console.error("Resend API error:", resendResp.status, errName);
      // 409 means contact already exists — that's fine, treat as success
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
  },
};
