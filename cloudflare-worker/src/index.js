/**
 * Cloudflare Worker — mergers.fyi digest email signup handler
 *
 * Accepts POST requests from the signup form on mergers.fyi,
 * validates the email address, and adds it to the configured
 * Resend audience via the Resend Contacts API.
 *
 * Required Worker secrets (set via `wrangler secret put`):
 *   RESEND_API_KEY      — Resend API key
 *   RESEND_AUDIENCE_ID  — Resend audience ID
 */

const RESEND_API_BASE = "https://api.resend.com";

// Allowed origin for CORS — update if you serve the form from a different domain
const ALLOWED_ORIGIN = "https://mergers.fyi";

// Simple but robust email regex
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// ---------------------------------------------------------------------------
// CORS helpers
// ---------------------------------------------------------------------------

function corsHeaders(origin) {
  // Allow the production site and localhost for local development
  const allowedOrigins = [ALLOWED_ORIGIN, "http://localhost:5173", "http://localhost:4173"];
  const responseOrigin = allowedOrigins.includes(origin) ? origin : ALLOWED_ORIGIN;
  return {
    "Access-Control-Allow-Origin": responseOrigin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
  };
}

function jsonResponse(body, status, origin = "") {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders(origin),
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
        headers: corsHeaders(origin),
      });
    }

    if (request.method !== "POST") {
      return jsonResponse({ error: "Method not allowed" }, 405, origin);
    }

    // Parse body
    let body;
    try {
      body = await request.json();
    } catch {
      return jsonResponse({ error: "Invalid request body" }, 400, origin);
    }

    const email = (body.email || "").trim().toLowerCase();

    if (!email) {
      return jsonResponse({ error: "Email address is required" }, 400, origin);
    }

    if (!EMAIL_RE.test(email)) {
      return jsonResponse({ error: "Please enter a valid email address" }, 400, origin);
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
      return jsonResponse({ error: "Failed to subscribe. Please try again." }, 503, origin);
    }

    if (!resendResp.ok) {
      const errData = await resendResp.json().catch(() => ({}));
      console.error("Resend API error:", resendResp.status, JSON.stringify(errData));
      // 409 means contact already exists — that's fine, treat as success
      if (resendResp.status !== 409) {
        return jsonResponse({ error: "Failed to subscribe. Please try again." }, 500, origin);
      }
    }

    return jsonResponse(
      { success: true, message: "Subscribed! You\u2019ll get the weekly digest every Monday." },
      200,
      origin
    );
  },
};
