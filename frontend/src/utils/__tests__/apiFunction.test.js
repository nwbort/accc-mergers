import { describe, it, expect } from 'vitest';

// The Pages Function gating /data/api/ (docs/api.md). Cloudflare only invokes
// onRequest, so these fake the pieces of the runtime it touches: the ASSETS
// binding, the API_DB D1 binding and context.waitUntil.
import {
  onRequest,
  REJECTED_LABEL,
  sha256Hex,
} from '../../../../functions/data/api/[[path]].js';

const URL_ = 'https://mergers.fyi/data/api/v1/mergers.json';
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

async function call({ url = URL_, key, method = 'GET', headers = {}, db, assets } = {}) {
  const env = { API_DB: db === undefined ? await makeDb() : db, ASSETS: assets || makeAssets() };
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

describe('API gate', () => {
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

  it('turns the SPA fallback for a missing file into a JSON 404', async () => {
    const { response } = await call({ key: GOOD_KEY, url: 'https://mergers.fyi/data/api/v2/nope.json' });
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
