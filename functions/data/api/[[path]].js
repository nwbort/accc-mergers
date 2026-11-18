// The API: everything under /data/api/ (today just /data/api/v1/mergers).
// See docs/api.md.
//
// Endpoints have no extension. Each is a static file of the same name plus
// .json (written by scripts/generate/static_data/outputs/api.py), which this
// Function serves through env.ASSETS.fetch(). Pages runs a Function before the
// asset at the same path, so the .json files themselves are never reachable
// directly: a request for one is a 404, leaving one URL per endpoint.
//
// Whether a key is required is the API_REQUIRE_KEY variable in the root
// wrangler.toml. Anything but the string "false" (including leaving it unset)
// requires one, so the gate can't be dropped by accident. Keys are checked by
// their SHA-256 against the api_keys table in the shared mergers-feedback D1
// database (bound as API_DB), and issued and revoked with
// workers/feedback-admin/scripts/api-keys.mjs.
//
// Every request served adds one to a per-label, per-day counter in api_usage:
// the key's label when a valid key was sent, OPEN_LABEL when the API is open
// and none was. Requests refused for want of a valid key count under
// REJECTED_LABEL. No IP address, user agent or per-request record is kept.

export const REJECTED_LABEL = '(rejected)';
export const OPEN_LABEL = '(open)';

const BASE_HEADERS = {
  'Content-Type': 'application/json; charset=utf-8',
  // Never let an edge or shared cache hand a keyed response to someone else.
  'Cache-Control': 'private, no-cache',
};

function jsonError(status, error, extraHeaders = {}) {
  return new Response(JSON.stringify({ error }) + '\n', {
    status,
    headers: { ...BASE_HEADERS, ...extraHeaders },
  });
}

function unauthorised(message) {
  return jsonError(401, message, { 'WWW-Authenticate': 'Bearer realm="mergers.fyi"' });
}

export function keyRequired(env) {
  return String(env.API_REQUIRE_KEY ?? '').trim().toLowerCase() !== 'false';
}

// en-CA formats as YYYY-MM-DD; same day boundary as feature_events in the
// signup Worker, so the two sets of counters line up.
export function sydneyDay(date = new Date()) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Australia/Sydney' }).format(date);
}

export async function sha256Hex(text) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function bearerToken(request) {
  const header = request.headers.get('Authorization') || '';
  const match = /^Bearer\s+(\S+)\s*$/i.exec(header);
  return match ? match[1] : null;
}

/** The .json file an extensionless endpoint is served from, or null for anything else. */
export function assetPath(pathname) {
  const path = pathname.replace(/\/+$/, '');
  if (!path || /\.[A-Za-z0-9]+$/.test(path)) return null;
  return `${path}.json`;
}

function countRequest(context, label) {
  const db = context.env.API_DB;
  if (!db) return;
  const write = Promise.resolve()
    .then(() =>
      db
        .prepare(
          `INSERT INTO api_usage (label, day, count) VALUES (?, ?, 1)
           ON CONFLICT (label, day) DO UPDATE SET count = count + 1`,
        )
        .bind(label, sydneyDay())
        .run(),
    )
    // Counting is best-effort: a failed write must not fail the request.
    .catch((err) => console.error('api_usage write failed', err));
  context.waitUntil?.(write);
}

export async function onRequest(context) {
  const { request, env } = context;

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return jsonError(405, 'Method not allowed', { Allow: 'GET, HEAD' });
  }

  const url = new URL(request.url);
  const path = assetPath(url.pathname);
  if (!path) return jsonError(404, 'Not found');

  const required = keyRequired(env);

  // Fail closed: with keys required but no database, there is no way to tell
  // a good key from a bad one, so nothing is served.
  if (required && !env.API_DB) return jsonError(503, 'API not configured');

  const token = bearerToken(request);
  let label = null;
  if (token && env.API_DB) {
    try {
      const row = await env.API_DB.prepare(
        'SELECT label FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL',
      )
        .bind(await sha256Hex(token))
        .first();
      label = row?.label ?? null;
    } catch (err) {
      console.error('api_keys lookup failed', err);
      if (required) return jsonError(503, 'API temporarily unavailable');
    }
  }

  if (required && !label) {
    countRequest(context, REJECTED_LABEL);
    return unauthorised(
      token ? 'Invalid or revoked API key' : 'Missing API key: send it as "Authorization: Bearer <key>"',
    );
  }

  // Pass the conditional header through so an unchanged file comes back as a
  // bodiless 304 against the client's ETag. Never the Authorization header.
  const assetHeaders = new Headers();
  const ifNoneMatch = request.headers.get('If-None-Match');
  if (ifNoneMatch) assetHeaders.set('If-None-Match', ifNoneMatch);
  const asset = await env.ASSETS.fetch(
    new Request(new URL(path, url.origin), { method: request.method, headers: assetHeaders }),
  );

  const etag = asset.headers.get('ETag');
  if (asset.status === 304) {
    countRequest(context, label ?? OPEN_LABEL);
    return new Response(null, {
      status: 304,
      headers: { 'Cache-Control': BASE_HEADERS['Cache-Control'], ...(etag ? { ETag: etag } : {}) },
    });
  }

  // A path with no file behind it comes back from Pages as the SPA shell (HTML,
  // 200), not a 404, so anything that isn't JSON is a miss.
  const type = asset.headers.get('Content-Type') || '';
  if (!asset.ok || !type.includes('json')) {
    return jsonError(404, 'Not found');
  }

  countRequest(context, label ?? OPEN_LABEL);
  const headers = new Headers(BASE_HEADERS);
  if (etag) headers.set('ETag', etag);
  const lastModified = asset.headers.get('Last-Modified');
  if (lastModified) headers.set('Last-Modified', lastModified);
  return new Response(request.method === 'HEAD' ? null : asset.body, { status: 200, headers });
}
