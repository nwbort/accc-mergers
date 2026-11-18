const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "x-secret",
};

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string") return false;
  const enc = new TextEncoder();
  const ab = enc.encode(a);
  const bb = enc.encode(b);
  if (ab.byteLength !== bb.byteLength) return false;
  return crypto.subtle.timingSafeEqual(ab, bb);
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    // Fail closed when SECRET is not configured: two empty strings would
    // otherwise compare equal and let a request with no header straight in.
    if (!env.SECRET || !timingSafeEqual(request.headers.get("x-secret") || "", env.SECRET)) {
      return new Response("Forbidden", { status: 403, headers: CORS });
    }

    const url = new URL(request.url);

    if (url.pathname === "/feedback" && request.method === "GET") {
      const { results } = await env.DB.prepare(
        "SELECT * FROM feedback ORDER BY created_at DESC"
      ).all();
      return Response.json(results, { headers: CORS });
    }

    if (url.pathname === "/events" && request.method === "GET") {
      const { results } = await env.DB.prepare(
        "SELECT event_type, day, count FROM feature_events ORDER BY day DESC, event_type ASC"
      ).all();
      return Response.json(results, { headers: CORS });
    }

    // The key-gated API's clients and their per-day request counts (see
    // docs/api.md). Never the key hashes: the hint is enough to tell keys apart.
    if (url.pathname === "/api-usage" && request.method === "GET") {
      const [keys, usage] = await env.DB.batch([
        env.DB.prepare(
          "SELECT label, key_hint, created_at, revoked_at FROM api_keys ORDER BY label, created_at"
        ),
        env.DB.prepare(
          "SELECT label, day, count FROM api_usage WHERE day >= date('now', '-90 days') ORDER BY day DESC, label ASC"
        ),
      ]);
      return Response.json({ keys: keys.results, usage: usage.results }, { headers: CORS });
    }

    return new Response("Not found", { status: 404, headers: CORS });
  },
};