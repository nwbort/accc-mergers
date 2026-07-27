/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, it, expect } from 'vitest';

import { slugify, mergerPath, industryPath, partyPath } from '../slug.js';
// The inline copy the Pages Function ships to social/OG bots. It exports
// slugify/mergerPath solely so this test can prove it hasn't drifted from the
// SPA copy — see the note in that file.
import { slugify as fnSlugify, mergerPath as fnMergerPath } from '../../../../../functions/mergers/[matter]/[[path]].js';

// Golden fixture shared with scripts/tests/test_slug.py — the single source of
// truth that pins all three slugify implementations together. Read via node fs
// (Vitest runs with the frontend project dir as cwd, so the repo root is two
// levels up) rather than an import, so Vite's module-graph fs allowlist and
// JSON-import handling don't come into it.
const repoRoot = resolve(process.cwd(), '..', '..');
const fixture = JSON.parse(readFileSync(resolve(repoRoot, 'slug-cases.json'), 'utf8'));
const cases = fixture.cases;

describe('slugify (SPA)', () => {
  it('has a non-empty golden fixture', () => {
    expect(Array.isArray(cases)).toBe(true);
    expect(cases.length).toBeGreaterThan(0);
  });

  it.each(cases)('matches the golden slug for "$name"', ({ name, slug }) => {
    expect(slugify(name)).toBe(slug);
  });

  it('handles null/undefined without throwing', () => {
    expect(slugify(undefined)).toBe('');
    expect(slugify(null)).toBe('');
  });
});

// If this block fails, the Pages Function's inline slugify has drifted from the
// SPA's — which is exactly what silently breaks canonical URLs (the bug this
// suite guards against). Fix by copying src/utils/slug.js's algorithm back into
// functions/mergers/[matter]/[[path]].js.
describe('slugify (Pages Function inline copy) stays in sync with the SPA', () => {
  it.each(cases)('agrees on the golden slug for "$name"', ({ name, slug }) => {
    expect(fnSlugify(name)).toBe(slug);
  });

  it('agrees with the SPA slugify across every fixture name', () => {
    for (const { name } of cases) {
      expect(fnSlugify(name)).toBe(slugify(name));
    }
  });

  it('builds identical merger paths', () => {
    expect(fnMergerPath('WA-35022', 'Hexagon - Waygate Technologies')).toBe(
      mergerPath('WA-35022', 'Hexagon - Waygate Technologies'),
    );
    // Bare-id fallback when no slug can be derived.
    expect(fnMergerPath('MN-10007', '!!!')).toBe(mergerPath('MN-10007', '!!!'));
  });
});

describe('mergerPath / industryPath / partyPath', () => {
  it('appends the slug when one can be derived', () => {
    expect(mergerPath('WA-35022', 'Hexagon - Waygate Technologies')).toBe(
      '/mergers/WA-35022/hexagon-waygate-technologies',
    );
  });

  it('falls back to the bare id when the name yields no slug', () => {
    expect(mergerPath('MN-10007', '!!!')).toBe('/mergers/MN-10007');
    expect(mergerPath('MN-10007', '')).toBe('/mergers/MN-10007');
  });

  it('URL-encodes the code/id segment', () => {
    expect(industryPath('06/10', 'Coal Mining')).toBe('/industries/06%2F10/coal-mining');
    expect(partyPath('a/b', 'Some Party')).toBe('/parties/a%2Fb/some-party');
  });
});
