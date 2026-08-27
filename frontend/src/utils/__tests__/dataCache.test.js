import { afterEach, describe, expect, it } from 'vitest';
import { dataCache } from '../dataCache';

// The cache is module-level, so each test must clean up after itself to
// avoid leaking state into the next test.
afterEach(() => {
  dataCache.clear();
});

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
});
