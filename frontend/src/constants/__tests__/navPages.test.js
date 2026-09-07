/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { NAV_PAGES, SHORTCUT_PAGES, SHORTCUT_ROUTES } from '../navPages';

// The point of this table is that the navbar, the command palette, the `g`
// chords and the help overlay all read it instead of keeping their own copies.
// These tests guard the invariants that makes possible — a duplicate key would
// silently shadow a page, and a path with no route would send a reader to the
// 404.
describe('NAV_PAGES', () => {
  it('gives every page a unique path', () => {
    const paths = NAV_PAGES.map((page) => page.path);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('points every page at a route the app actually renders', () => {
    // vitest runs from the frontend root, as utils/__tests__/slug.test.js does.
    const app = readFileSync(resolve(process.cwd(), 'src/App.jsx'), 'utf8');
    const routed = new Set([...app.matchAll(/<Route path="([^"]+)"/g)].map((m) => m[1]));

    for (const { label, path } of NAV_PAGES) {
      expect(routed, `${label} (${path}) has no route in App.jsx`).toContain(path);
    }
  });
});

describe('keyboard shortcuts', () => {
  it('assigns each chord key to exactly one page', () => {
    const keys = SHORTCUT_PAGES.map((page) => page.shortcut);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it('uses single lowercase letters, so a chord cannot need a modifier', () => {
    for (const { label, shortcut } of SHORTCUT_PAGES) {
      expect(shortcut, `${label}'s shortcut`).toMatch(/^[a-z]$/);
    }
  });

  it('never binds "g" itself, which would swallow the prefix', () => {
    expect(SHORTCUT_ROUTES).not.toHaveProperty('g');
  });

  it('derives the lookup table from the same entries, with nothing dropped', () => {
    expect(Object.keys(SHORTCUT_ROUTES)).toHaveLength(SHORTCUT_PAGES.length);
    for (const { shortcut, path } of SHORTCUT_PAGES) {
      expect(SHORTCUT_ROUTES[shortcut]).toBe(path);
    }
  });
});
