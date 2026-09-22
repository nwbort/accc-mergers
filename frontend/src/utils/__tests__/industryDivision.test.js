/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

import {
  DIVISION_SUBDIVISION_RANGES,
  ORPHAN_FILE_STEM,
  divisionFileName,
  divisionFileStem,
  divisionForCode,
  industryDivisionUrl,
} from '../industryDivision.js';

// Golden fixture shared with scripts/tests/test_industry_division.py — the
// single source of truth pinning both lookup implementations together. Read via
// node fs (Vitest runs with the frontend project dir as cwd, so the repo root is
// one level up) rather than an import, matching shard.test.js.
const repoRoot = resolve(process.cwd(), '..');
const fixture = JSON.parse(
  readFileSync(resolve(repoRoot, 'fixtures', 'industry-division-cases.json'), 'utf8'),
);
const cases = fixture.cases;

describe('divisionFileName', () => {
  it('has a non-empty golden fixture', () => {
    expect(Array.isArray(cases)).toBe(true);
    expect(cases.length).toBeGreaterThan(0);
  });

  it.each(cases)('matches the golden file for "$code"', ({ code, file }) => {
    expect(divisionFileName(code)).toBe(file);
  });
});

describe('divisionForCode', () => {
  it('reads a division letter as itself', () => {
    expect(divisionForCode('A')).toBe('A');
    expect(divisionForCode('S')).toBe('S');
  });

  it('maps every level of a numeric code to the same division', () => {
    // Subdivision 45 / group 452 / class 4520 all sit under Accommodation and
    // Food Services, which is the property that makes one file per division
    // enough for a page and its parent comparison.
    expect(['45', '452', '4520'].map(divisionForCode)).toEqual(['H', 'H', 'H']);
  });

  it.each([
    [''], [null], [undefined],
    ['T'],       // a division letter ANZSIC doesn't use
    ['61'],      // a subdivision number in one of the standard's gaps
    ['6100'],
    ['9999'],
    ['06/10'],   // the ACCC has published a slashed tag before
    ['abcd'],
    ['0'],
    ['12345'],
  ])('returns null for %s', (code) => {
    expect(divisionForCode(code)).toBeNull();
    expect(divisionFileStem(code)).toBe(ORPHAN_FILE_STEM);
  });

  it('tolerates surrounding whitespace', () => {
    // The code arrives off a URL path segment; a stray space shouldn't
    // silently route a real industry to the orphan file.
    expect(divisionForCode(' 4520 ')).toBe('H');
  });
});

describe('DIVISION_SUBDIVISION_RANGES', () => {
  it('is ordered and non-overlapping', () => {
    let previousHigh = 0;
    for (const [, low, high] of DIVISION_SUBDIVISION_RANGES) {
      expect(low).toBeLessThanOrEqual(high);
      expect(low).toBeGreaterThan(previousHigh);
      previousHigh = high;
    }
  });

  it('has one row per division letter', () => {
    const letters = DIVISION_SUBDIVISION_RANGES.map(([d]) => d);
    expect(new Set(letters).size).toBe(letters.length);
    expect(letters).toHaveLength(19);
  });
});

describe('industryDivisionUrl', () => {
  it('points at the division file under /data/industries', () => {
    expect(industryDivisionUrl('4520')).toBe('/data/industries/H.json');
    expect(industryDivisionUrl('nonsense')).toBe('/data/industries/_orphans.json');
  });
});
