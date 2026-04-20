const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "x-secret",
};

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    if (request.headers.get("x-secret") !== env.SECRET) {
      return new Response("Forbidden", { status: 403, headers: CORS });
    }

    const url = new URL(request.url);

    if (url.pathname === "/feedback" && request.method === "GET") {
      const { results } = await env.DB.prepare(
        "SELECT * FROM feedback ORDER BY created_at DESC"
      ).all();
      return Response.json(results, { headers: CORS });
    }

    return new Response("Not found", { status: 404, headers: CORS });
  },
};