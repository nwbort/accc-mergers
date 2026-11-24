import { describe, it, expect } from 'vitest';

// The Pages Function serving /data/api/ (docs/api.md). Cloudflare only invokes
// onRequest, so these fake the pieces of the runtime it touches: the ASSETS
// binding, the API_DB D1 binding and context.waitUntil.
import {
  assetPath,
  KEY_CONTACT,
  keyRequired,
  onRequest,
  OPEN_LABEL,
  REJECTED_LABEL,
  sha256Hex,
} from '../../../../functions/data/api/[[path]].js';

const URL_ = 'https://mergers.fyi/data/api/v1/mergers';
const GOOD_KEY = 'mfyi_live_good';
const REVOKED_KEY = 'mfyi_live_revoked';
const BODY = '{"version":"v1","mergers":[]}\n';
const ETAG = '"abc123"';

// A tiny stand-in for D1: api_keys holds { hash: { label, revoked } }, and every
// api_usage upsert is recorded so tests can see what was counted.
async function makeDb() {
  const keys = {
    [await sha256Hex(GOOD_KEY)]: { label: 'smith-legal', revoked: false },
    [await sha256Hex(REVOKED_KEY)]: { label: 'old-client', revoked: true },
  };
  const usage = [];
  return {
    usage,
    prepare(sql) {
      return {
        bind(...args) {
          return {
            async first() {
              const key = keys[args[0]];
              return key && !key.revoked ? { label: key.label } : null;
            },
            async run() {
              if (sql.includes('api_usage')) usage.push({ label: args[0], day: args[1] });
              return { success: true };
            },
          };
        },
      };
    },
  };
}

function makeAssets() {
  return {
    seen: [],
    async fetch(request) {
      this.seen.push(request);
      const { pathname } = new URL(request.url);
      if (pathname !== '/data/api/v1/mergers.json') {
        return new Response('<!doctype html>', { headers: { 'Content-Type': 'text/html' } });
      }
      if (request.headers.get('If-None-Match') === ETAG) {
        return new Response(null, { status: 304, headers: { ETag: ETAG } });
      }
      return new Response(BODY, {
        headers: { 'Content-Type': 'application/json', ETag: ETAG },
      });
    },
  };
}

async function call({ url = URL_, key, method = 'GET', headers = {}, db, assets, requireKey = 'true' } = {}) {
  const env = {
    API_DB: db === undefined ? await makeDb() : db,
    ASSETS: assets || makeAssets(),
    API_REQUIRE_KEY: requireKey,
  };
  const waits = [];
  const h = new Headers(headers);
  if (key) h.set('Authorization', `Bearer ${key}`);
  const response = await onRequest({
    request: new Request(url, { method, headers: h }),
    env,
    waitUntil: (p) => waits.push(p),
  });
  await Promise.all(waits);
  return { response, env };
}

describe('API with keys required', () => {
  it('serves the file to a valid key and counts it against that key', async () => {
    const { response, env } = await call({ key: GOOD_KEY });
    expect(response.status).toBe(200);
    expect(await response.text()).toBe(BODY);
    expect(response.headers.get('ETag')).toBe(ETAG);
    expect(response.headers.get('Cache-Control')).toContain('private');
    expect(env.API_DB.usage.map((u) => u.label)).toEqual(['smith-legal']);
    expect(env.API_DB.usage[0].day).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('rejects a request with no key, counting it as rejected', async () => {
    const { response, env } = await call();
    expect(response.status).toBe(401);
    expect(response.headers.get('WWW-Authenticate')).toMatch(/^Bearer/);
    expect(env.API_DB.usage.map((u) => u.label)).toEqual([REJECTED_LABEL]);
    expect(env.ASSETS.seen).toHaveLength(0);
  });

  it('tells a keyless client who to email for a key, and how to send it', async () => {
    const { response } = await call();
    const body = await response.json();
    expect(body.error).toContain(KEY_CONTACT);
    expect(body.error).toContain('?key=');
    expect(body.error).toContain('Authorization: Bearer');
    expect(body.request_a_key).toBe(`mailto:${KEY_CONTACT}`);
  });

  it('accepts the key as a ?key= query parameter', async () => {
    const { response, env } = await call({ url: `${URL_}?key=${GOOD_KEY}` });
    expect(response.status).toBe(200);
    expect(await response.text()).toBe(BODY);
    expect(env.API_DB.usage.map((u) => u.label)).toEqual(['smith-legal']);
  });

  it('never forwards a ?key= to the asset fetch', async () => {
    const { env } = await call({ url: `${URL_}?key=${GOOD_KEY}` });
    expect(new URL(env.ASSETS.seen[0].url).search).toBe('');
  });

  it('rejects an unknown ?key=, still naming the contact', async () => {
    const { response, env } = await call({ url: `${URL_}?key=mfyi_live_guess` });
    expect(response.status).toBe(401);
    expect((await response.json()).error).toMatch(/Invalid or revoked/);
    expect(env.ASSETS.seen).toHaveLength(0);
  });

  it('treats an empty ?key= as no key', async () => {
    const { response } = await call({ url: `${URL_}?key=` });
    expect(response.status).toBe(401);
    expect((await response.json()).error).toMatch(/is required/);
  });

  it('prefers the header when both are sent', async () => {
    const { response } = await call({ key: GOOD_KEY, url: `${URL_}?key=mfyi_live_guess` });
    expect(response.status).toBe(200);
  });

  it('rejects an unknown key', async () => {
    const { response, env } = await call({ key: 'mfyi_live_guess' });
    expect(response.status).toBe(401);
    expect(env.API_DB.usage.map((u) => u.label)).toEqual([REJECTED_LABEL]);
    expect(env.ASSETS.seen).toHaveLength(0);
  });

  it('rejects a revoked key', async () => {
    const { response } = await call({ key: REVOKED_KEY });
    expect(response.status).toBe(401);
  });

  it('fails closed when the database is not bound', async () => {
    const { response, env } = await call({ key: GOOD_KEY, db: null });
    expect(response.status).toBe(503);
    expect(env.ASSETS.seen).toHaveLength(0);
  });

  it('answers an unchanged file with a bodiless 304, still counted', async () => {
    const { response, env } = await call({ key: GOOD_KEY, headers: { 'If-None-Match': ETAG } });
    expect(response.status).toBe(304);
    expect(await response.text()).toBe('');
    expect(env.API_DB.usage.map((u) => u.label)).toEqual(['smith-legal']);
  });

  it('serves the endpoint from its .json file', async () => {
    const { env } = await call({ key: GOOD_KEY });
    expect(new URL(env.ASSETS.seen[0].url).pathname).toBe('/data/api/v1/mergers.json');
  });

  it('tolerates a trailing slash', async () => {
    const { response } = await call({ key: GOOD_KEY, url: `${URL_}/` });
    expect(response.status).toBe(200);
  });

  it('does not serve the .json file under its own name', async () => {
    const { response, env } = await call({ key: GOOD_KEY, url: `${URL_}.json` });
    expect(response.status).toBe(404);
    expect(env.ASSETS.seen).toHaveLength(0);
  });

  it('turns the SPA fallback for a missing file into a JSON 404', async () => {
    const { response } = await call({ key: GOOD_KEY, url: 'https://mergers.fyi/data/api/v2/nope' });
    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ error: 'Not found' });
  });

  it('never forwards the key to the asset fetch', async () => {
    const { env } = await call({ key: GOOD_KEY });
    expect(env.ASSETS.seen[0].headers.get('Authorization')).toBeNull();
  });

  it('refuses other methods', async () => {
    const { response } = await call({ key: GOOD_KEY, method: 'POST' });
    expect(response.status).toBe(405);
  });

  it('serves HEAD without a body', async () => {
    const { response } = await call({ key: GOOD_KEY, method: 'HEAD' });
    expect(response.status).toBe(200);
    expect(await response.text()).toBe('');
  });

  it('still serves the file when the usage write fails', async () => {
    const db = await makeDb();
    const prepare = db.prepare.bind(db);
    db.prepare = (sql) => {
      const stmt = prepare(sql);
      if (!sql.includes('api_usage')) return stmt;
      return { bind: () => ({ run: () => Promise.reject(new Error('D1 down')) }) };
    };
    const { response } = await call({ key: GOOD_KEY, db });
    expect(response.status).toBe(200);
  });
});

describe('API open (API_REQUIRE_KEY = "false")', () => {
  it('serves without a key, counted as open', async () => {
    const { response, env } = await call({ requireKey: 'false' });
    expect(response.status).toBe(200);
    expect(await response.text()).toBe(BODY);
    expect(env.API_DB.usage.map((u) => u.label)).toEqual([OPEN_LABEL]);
  });

  it('still credits a valid key to its client', async () => {
    const { env } = await call({ requireKey: 'false', key: GOOD_KEY });
    expect(env.API_DB.usage.map((u) => u.label)).toEqual(['smith-legal']);
  });

  it('serves an invalid or revoked key as open rather than refusing it', async () => {
    const { response, env } = await call({ requireKey: 'false', key: REVOKED_KEY });
    expect(response.status).toBe(200);
    expect(env.API_DB.usage.map((u) => u.label)).toEqual([OPEN_LABEL]);
  });

  it('credits a valid ?key= to its client', async () => {
    const { env } = await call({ requireKey: 'false', url: `${URL_}?key=${GOOD_KEY}` });
    expect(env.API_DB.usage.map((u) => u.label)).toEqual(['smith-legal']);
  });

  it('serves without the database bound', async () => {
    const { response } = await call({ requireKey: 'false', db: null });
    expect(response.status).toBe(200);
  });

  it('serves when the key lookup fails', async () => {
    const db = await makeDb();
    db.prepare = () => ({ bind: () => ({ first: () => Promise.reject(new Error('no such table')), run: () => Promise.reject(new Error('no such table')) }) });
    const { response } = await call({ requireKey: 'false', key: GOOD_KEY, db });
    expect(response.status).toBe(200);
  });
});

describe('keyRequired', () => {
  it('is open only for an explicit "false"', () => {
    expect(keyRequired({ API_REQUIRE_KEY: 'false' })).toBe(false);
    expect(keyRequired({ API_REQUIRE_KEY: ' FALSE ' })).toBe(false);
    expect(keyRequired({ API_REQUIRE_KEY: 'true' })).toBe(true);
    expect(keyRequired({ API_REQUIRE_KEY: '' })).toBe(true);
    expect(keyRequired({ API_REQUIRE_KEY: 'no' })).toBe(true);
    expect(keyRequired({})).toBe(true);
  });
});

describe('assetPath', () => {
  it('maps an extensionless endpoint to its .json file', () => {
    expect(assetPath('/data/api/v1/mergers')).toBe('/data/api/v1/mergers.json');
    expect(assetPath('/data/api/v1/mergers/')).toBe('/data/api/v1/mergers.json');
  });

  it('refuses paths with an extension', () => {
    expect(assetPath('/data/api/v1/mergers.json')).toBeNull();
    expect(assetPath('/data/api/v1/mergers.xml')).toBeNull();
  });
});
