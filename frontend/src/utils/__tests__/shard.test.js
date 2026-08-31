/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

import { SHARD_COUNT, fnv1a32, partyShard, partyShardName, shardName } from '../shard.js';

// Golden fixture shared with scripts/tests/test_shard.py — the single source of
// truth pinning both shard implementations together. Read via node fs (Vitest
// runs with the frontend project dir as cwd, so the repo root is one level up)
// rather than an import, matching slug.test.js.
const repoRoot = resolve(process.cwd(), '..');
const fixture = JSON.parse(
  readFileSync(resolve(repoRoot, 'fixtures', 'shard-cases.json'), 'utf8'),
);
const cases = fixture.cases;

describe('partyShard', () => {
  it('has a non-empty golden fixture', () => {
    expect(Array.isArray(cases)).toBe(true);
    expect(cases.length).toBeGreaterThan(0);
  });

  // A fixture generated under a different SHARD_COUNT would pass every case by
  // luck while describing a different layout on disk.
  it('agrees with the fixture on SHARD_COUNT', () => {
    expect(fixture.shard_count).toBe(SHARD_COUNT);
  });

  it.each(cases)('matches the golden shard for "$id"', ({ id, shard, file }) => {
    expect(partyShard(id)).toBe(shard);
    expect(partyShardName(id)).toBe(file);
  });

  it('handles null/undefined without throwing', () => {
    expect(partyShard(undefined)).toBe(partyShard(''));
    expect(partyShard(null)).toBe(partyShard(''));
  });

  it('always lands in range', () => {
    for (const id of ['coles', '', 'a/b', 'x'.repeat(500), '日本たばこ産業']) {
      const s = partyShard(id);
      expect(s).toBeGreaterThanOrEqual(0);
      expect(s).toBeLessThan(SHARD_COUNT);
    }
  });
});

describe('fnv1a32', () => {
  // Published FNV-1a 32-bit vectors. Math.imul is easy to get subtly wrong in
  // a way that stays self-consistent within JS but diverges from Python.
  it('matches known vectors', () => {
    expect(fnv1a32('')).toBe(0x811c9dc5);
    expect(fnv1a32('a')).toBe(0xe40c292c);
    expect(fnv1a32('foobar')).toBe(0xbf9cf968);
  });

  it('stays an unsigned 32-bit integer', () => {
    // The multiply overflows into the sign bit constantly; a missing `>>> 0`
    // would surface here as a negative hash and a negative bucket index.
    for (let i = 0; i < 500; i += 1) {
      const h = fnv1a32(`party-${i}`);
      expect(h).toBeGreaterThanOrEqual(0);
      expect(h).toBeLessThanOrEqual(0xffffffff);
      expect(Number.isInteger(h)).toBe(true);
    }
  });

  it('hashes UTF-8 bytes, not code points', () => {
    let expected = 0x811c9dc5;
    for (const byte of [0xc3, 0xa9]) {
      expected ^= byte;
      expected = Math.imul(expected, 0x01000193) >>> 0;
    }
    expect(fnv1a32('é')).toBe(expected);
  });
});

describe('shardName', () => {
  it('is always two hex digits', () => {
    expect(shardName(0)).toBe('shard-00.json');
    expect(shardName(255)).toBe('shard-ff.json');
    expect(shardName(10)).toBe('shard-0a.json');
  });
});
