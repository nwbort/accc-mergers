/* global process */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// The /merged deck's snap rule, read out of the stylesheet.
//
// jsdom has no scroll snapping and vitest is configured with `css: false`, so
// there is nothing to assert against but the text. It is asserted anyway
// because the rule is two properties that only work together, and relaxing
// either one looks harmless:
//
//   - Chromium ignores `scroll-snap-stop` entirely under `proximity`. The
//     property still computes as `always` and the flick still crosses four
//     cards, so softening the strictness throws the stop away with it and
//     nothing says so.
//   - `proximity` was originally here to stop mandatory snapping trapping a
//     card taller than the viewport. It does not: the spec gives a snap area
//     larger than the snapport every position that covers it, so a revealed
//     quiz card scrolls through freely.
//
// Measured in Chromium at 390x844: without the stop a thumb flick carried four
// cards; with it, one. See the comment in index.css.

// Vitest runs with the frontend project dir as cwd, as pageMeta.test.js assumes.
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');
const rule = css.slice(css.indexOf('.merged-snap'));

describe('the /merged snap rule', () => {
  it('snaps mandatorily, which is what makes the stop work at all', () => {
    expect(rule).toMatch(/scroll-snap-type:\s*y mandatory/);
  });

  it('stops at every card, so one flick moves one card', () => {
    expect(rule).toMatch(/\.merged-snap \[data-card\][^}]*scroll-snap-stop:\s*always/s);
  });

  it('clears the fixed navbar when it snaps', () => {
    expect(rule).toMatch(/scroll-padding-top:\s*4rem/);
  });
});
