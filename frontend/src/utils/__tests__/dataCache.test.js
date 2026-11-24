import { afterEach, describe, expect, it, vi } from 'vitest';
import { dataCache } from '../dataCache';

// The cache is module-level, so each test must clean up after itself to
// avoid leaking state into the next test.
afterEach(() => {
  dataCache.clear();
  vi.restoreAllMocks();
});

function okResponse(json, headers = {}) {
  const lower = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), v]));
  return {
    ok: true,
    status: 200,
    headers: { get: (name) => lower[name.toLowerCase()] ?? null },
    json: vi.fn(() => Promise.resolve(json)),
  };
}

describe('dataCache', () => {
  describe('set + get', () => {
    it('returns the value previously stored under a key', () => {
      dataCache.set('foo', { a: 1 });
      expect(dataCache.get('foo')).toEqual({ a: 1 });
    });

    it('returns undefined for a missing key', () => {
      expect(dataCache.get('missing')).toBeUndefined();
    });

    it('preserves reference identity (does not clone)', () => {
      const value = { nested: {} };
      dataCache.set('ref', value);
      expect(dataCache.get('ref')).toBe(value);
    });

    it('overwrites an existing key', () => {
      dataCache.set('k', 'first');
      dataCache.set('k', 'second');
      expect(dataCache.get('k')).toBe('second');
    });

    it('supports Map values (used by searchIndex)', () => {
      const m = new Map([['a', 1]]);
      dataCache.set('map', m);
      expect(dataCache.get('map')).toBe(m);
    });
  });

  describe('has', () => {
    it('returns true after set', () => {
      dataCache.set('x', 1);
      expect(dataCache.has('x')).toBe(true);
    });

    it('returns false for unknown key', () => {
      expect(dataCache.has('nope')).toBe(false);
    });

    it('distinguishes a stored `undefined` value from a missing key', () => {
      dataCache.set('present', undefined);
      expect(dataCache.has('present')).toBe(true);
      expect(dataCache.get('present')).toBeUndefined();
    });
  });

  describe('clear', () => {
    it('clears a single key when a key is supplied', () => {
      dataCache.set('a', 1);
      dataCache.set('b', 2);
      dataCache.clear('a');
      expect(dataCache.has('a')).toBe(false);
      expect(dataCache.has('b')).toBe(true);
      expect(dataCache.get('b')).toBe(2);
    });

    it('clears every entry when no key is supplied', () => {
      dataCache.set('a', 1);
      dataCache.set('b', 2);
      dataCache.clear();
      expect(dataCache.has('a')).toBe(false);
      expect(dataCache.has('b')).toBe(false);
    });

    it('is a no-op when clearing a key that is not present', () => {
      dataCache.set('a', 1);
      expect(() => dataCache.clear('nonexistent')).not.toThrow();
      expect(dataCache.get('a')).toBe(1);
    });
  });

  describe('fetchedAt', () => {
    it('is null before a key is ever set', () => {
      expect(dataCache.fetchedAt('never')).toBeNull();
    });

    it('reflects the time of the most recent set', () => {
      const before = Date.now();
      dataCache.set('k', 1);
      const after = Date.now();
      const fetchedAt = dataCache.fetchedAt('k');
      expect(fetchedAt).toBeGreaterThanOrEqual(before);
      expect(fetchedAt).toBeLessThanOrEqual(after);
    });
  });

  describe('registerActive / activeEntries', () => {
    it('tracks a registered key/url pair', () => {
      const unregister = dataCache.registerActive('k', '/data/k.json');
      expect(dataCache.activeEntries()).toEqual([['k', '/data/k.json']]);
      unregister();
    });

    it('drops the entry once the last consumer unregisters', () => {
      const unregisterA = dataCache.registerActive('k', '/data/k.json');
      const unregisterB = dataCache.registerActive('k', '/data/k.json');
      unregisterA();
      expect(dataCache.activeEntries()).toEqual([['k', '/data/k.json']]);
      unregisterB();
      expect(dataCache.activeEntries()).toEqual([]);
    });
  });

  describe('subscribe', () => {
    it('is not called by a plain set()', () => {
      const cb = vi.fn();
      dataCache.subscribe('k', cb);
      dataCache.set('k', { a: 1 });
      expect(cb).not.toHaveBeenCalled();
    });

    it('stops receiving updates after unsubscribing', async () => {
      const cb = vi.fn();
      const unsubscribe = dataCache.subscribe('k', cb);
      unsubscribe();
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(okResponse({ a: 2 }));
      await dataCache.revalidate('k', '/data/k.json');
      expect(cb).not.toHaveBeenCalled();
    });
  });

  describe('revalidate', () => {
    it('stores the response and notifies subscribers when the data changed', async () => {
      dataCache.set('k', { a: 1 });
      const cb = vi.fn();
      dataCache.subscribe('k', cb);
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(okResponse({ a: 2 }));

      await dataCache.revalidate('k', '/data/k.json');

      expect(dataCache.get('k')).toEqual({ a: 2 });
      expect(cb).toHaveBeenCalledWith({ a: 2 });
      // no-cache, not no-store: the browser revalidates its copy with the
      // server, so an unchanged file comes back as a 304.
      expect(globalThis.fetch).toHaveBeenCalledWith('/data/k.json', { cache: 'no-cache' });
    });

    it('does not notify subscribers when the data is unchanged', async () => {
      dataCache.set('k', { a: 1 });
      const cb = vi.fn();
      dataCache.subscribe('k', cb);
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(okResponse({ a: 1 }));

      await dataCache.revalidate('k', '/data/k.json');

      expect(cb).not.toHaveBeenCalled();
    });

    it('still updates fetchedAt when the data is unchanged', async () => {
      dataCache.set('k', { a: 1 });
      const firstFetchedAt = dataCache.fetchedAt('k');
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(okResponse({ a: 1 }));

      await new Promise((r) => setTimeout(r, 5));
      await dataCache.revalidate('k', '/data/k.json');

      expect(dataCache.fetchedAt('k')).toBeGreaterThan(firstFetchedAt);
    });

    it('leaves the cache untouched on a network error', async () => {
      dataCache.set('k', { a: 1 });
      const cb = vi.fn();
      dataCache.subscribe('k', cb);
      vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

      await expect(dataCache.revalidate('k', '/data/k.json')).resolves.toBeUndefined();

      expect(dataCache.get('k')).toEqual({ a: 1 });
      expect(cb).not.toHaveBeenCalled();
    });

    it('skips the body when the validator is unchanged', async () => {
      dataCache.set('k', { a: 1 }, '"v1"');
      const firstFetchedAt = dataCache.fetchedAt('k');
      const cb = vi.fn();
      dataCache.subscribe('k', cb);
      const res = okResponse({ a: 2 }, { ETag: '"v1"' });
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(res);

      await new Promise((r) => setTimeout(r, 5));
      await dataCache.revalidate('k', '/data/k.json');

      expect(res.json).not.toHaveBeenCalled();
      expect(cb).not.toHaveBeenCalled();
      expect(dataCache.get('k')).toEqual({ a: 1 });
      expect(dataCache.fetchedAt('k')).toBeGreaterThan(firstFetchedAt);
    });

    it('stores the new validator and notifies when the validator changed', async () => {
      dataCache.set('k', { a: 1 }, '"v1"');
      const cb = vi.fn();
      dataCache.subscribe('k', cb);
      vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(okResponse({ a: 2 }, { ETag: '"v2"' }))
        .mockResolvedValueOnce(okResponse({ a: 3 }, { ETag: '"v2"' }));

      await dataCache.revalidate('k', '/data/k.json');
      expect(cb).toHaveBeenCalledWith({ a: 2 });

      // The next check sends the same validator back: nothing to read.
      await dataCache.revalidate('k', '/data/k.json');
      expect(dataCache.get('k')).toEqual({ a: 2 });
      expect(cb).toHaveBeenCalledTimes(1);
    });

    it('falls back to Last-Modified when there is no ETag', async () => {
      dataCache.set('k', { a: 1 }, 'Tue, 24 Nov 2026 00:00:00 GMT');
      const res = okResponse({ a: 2 }, { 'Last-Modified': 'Tue, 24 Nov 2026 00:00:00 GMT' });
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(res);

      await dataCache.revalidate('k', '/data/k.json');

      expect(res.json).not.toHaveBeenCalled();
      expect(dataCache.get('k')).toEqual({ a: 1 });
    });

    it('keeps the cached object when a new validator carries the same data', async () => {
      const original = { a: 1 };
      dataCache.set('k', original, '"v1"');
      const cb = vi.fn();
      dataCache.subscribe('k', cb);
      vi.spyOn(globalThis, 'fetch').mockResolvedValue(okResponse({ a: 1 }, { ETag: '"v2"' }));

      await dataCache.revalidate('k', '/data/k.json');

      expect(cb).not.toHaveBeenCalled();
      expect(dataCache.get('k')).toBe(original);
    });

    it('uses the validator load() stored', async () => {
      vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce(okResponse({ a: 1 }, { ETag: '"v1"' }))
        .mockResolvedValueOnce(okResponse({ a: 1 }, { ETag: '"v1"' }));

      await dataCache.load('k', '/data/k.json');
      await dataCache.revalidate('k', '/data/k.json');

      const revalidation = await globalThis.fetch.mock.results[1].value;
      expect(revalidation.json).not.toHaveBeenCalled();
    });

    it('leaves the cache untouched on a non-ok response', async () => {
      dataCache.set('k', { a: 1 });
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 500 });

      await dataCache.revalidate('k', '/data/k.json');

      expect(dataCache.get('k')).toEqual({ a: 1 });
    });
  });
});
