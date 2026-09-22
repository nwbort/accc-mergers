import { afterEach, describe, expect, it, vi } from 'vitest';
import { dataCache } from '../dataCache';

// The cache is module-level, so each test must clean up after itself to
// avoid leaking state into the next test.
afterEach(() => {
  dataCache.clear();
  vi.restoreAllMocks();
});

function okResponse(json) {
  return { ok: true, status: 200, json: () => Promise.resolve(json) };
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
      expect(globalThis.fetch).toHaveBeenCalledWith('/data/k.json', { cache: 'no-store' });
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

    it('leaves the cache untouched on a non-ok response', async () => {
      dataCache.set('k', { a: 1 });
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: false, status: 500 });

      await dataCache.revalidate('k', '/data/k.json');

      expect(dataCache.get('k')).toEqual({ a: 1 });
    });
  });
});
