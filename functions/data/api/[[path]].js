// The key-gated API: everything under /data/api/ (today just
// /data/api/v1/mergers.json, written by
// scripts/generate/static_data/outputs/api.py). See docs/api.md.
//
// The files are ordinary static assets, but Pages runs a Function before the
// asset at the same path, so nothing under /data/api/ reaches anyone without
// passing through here. env.ASSETS.fetch() then serves the file directly,
// without re-entering this Function.
//
// A key is checked by its SHA-256 against the api_keys table in the shared
// mergers-feedback D1 database (bound as API_DB in the root wrangler.toml), and
// every request adds one to a per-key, per-day counter in api_usage. Rejected
// requests are counted together under REJECTED_LABEL. No IP address, user
// agent or per-request record is kept. Keys are issued and revoked with
// workers/feedback-admin/scripts/api-keys.mjs.

export const REJECTED_LABEL = '(rejected)';

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

function countRequest(context, label) {
  const write = context.env.API_DB.prepare(
    `INSERT INTO api_usage (label, day, count) VALUES (?, ?, 1)
     ON CONFLICT (label, day) DO UPDATE SET count = count + 1`,
  )
    .bind(label, sydneyDay())
    .run()
    // Counting is best-effort: a failed write must not fail the request.
    .catch((err) => console.error('api_usage write failed', err));
  context.waitUntil?.(write);
}

export async function onRequest(context) {
  const { request, env } = context;

  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return jsonError(405, 'Method not allowed', { Allow: 'GET, HEAD' });
  }

  // Fail closed: without the database there is no way to tell a good key from
  // a bad one, so nothing is served.
  if (!env.API_DB) return jsonError(503, 'API not configured');

  const token = bearerToken(request);
  if (!token) {
    countRequest(context, REJECTED_LABEL);
    return unauthorised('Missing API key: send it as "Authorization: Bearer <key>"');
  }

  let row;
  try {
    row = await env.API_DB.prepare(
      'SELECT label FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL',
    )
      .bind(await sha256Hex(token))
      .first();
  } catch (err) {
    console.error('api_keys lookup failed', err);
    return jsonError(503, 'API temporarily unavailable');
  }

  if (!row) {
    countRequest(context, REJECTED_LABEL);
    return unauthorised('Invalid or revoked API key');
  }

  countRequest(context, row.label);

  // Pass the conditional header through so an unchanged file comes back as a
  // bodiless 304 against the client's ETag.
  const assetHeaders = new Headers();
  const ifNoneMatch = request.headers.get('If-None-Match');
  if (ifNoneMatch) assetHeaders.set('If-None-Match', ifNoneMatch);
  const asset = await env.ASSETS.fetch(
    new Request(request.url, { method: request.method, headers: assetHeaders }),
  );

  const etag = asset.headers.get('ETag');
  if (asset.status === 304) {
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

  const headers = new Headers(BASE_HEADERS);
  if (etag) headers.set('ETag', etag);
  const lastModified = asset.headers.get('Last-Modified');
  if (lastModified) headers.set('Last-Modified', lastModified);
  return new Response(request.method === 'HEAD' ? null : asset.body, { status: 200, headers });
}
