// @vitest-environment node
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { buildTheme } from '../m3';

const JSON_PATH = fileURLToPath(new URL('../m3-theme.json', import.meta.url));

// `npm run theme` sets this to rewrite the JSON from buildTheme().
if (process.env.UPDATE_M3_THEME) {
  fs.writeFileSync(JSON_PATH, `${JSON.stringify(buildTheme(), null, 2)}\n`);
}

const theme = JSON.parse(fs.readFileSync(JSON_PATH, 'utf8'));

function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('m3-theme.json', () => {
  it('is what material-color-utilities builds (run `npm run theme`)', () => {
    expect(theme).toEqual(buildTheme());
  });

  it('keeps the brand green as primary', () => {
    expect(theme.colors.primary).toBe('#335145');
  });
});

describe('scheme contrast (WCAG 2.2 AA)', () => {
  const c = theme.colors;
  const surfaces = [
    'surface',
    'surface-container-lowest',
    'surface-container-low',
    'surface-container',
    'surface-container-high',
  ];

  it.each([
    ['on-primary', 'primary'],
    ['on-primary-container', 'primary-container'],
    ['on-secondary-container', 'secondary-container'],
    ['on-tertiary-container', 'tertiary-container'],
    ['on-error-container', 'error-container'],
  ])('%s text on %s clears 4.5:1', (fg, bg) => {
    expect(contrast(c[fg], c[bg])).toBeGreaterThanOrEqual(4.5);
  });

  it.each(surfaces)('muted text (gray-500), primary and on-surface-variant clear 4.5:1 on %s', (bg) => {
    expect(contrast(theme.gray[500], c[bg])).toBeGreaterThanOrEqual(4.5);
    expect(contrast(c.primary, c[bg])).toBeGreaterThanOrEqual(4.5);
    expect(contrast(c['on-surface-variant'], c[bg])).toBeGreaterThanOrEqual(4.5);
  });

  it.each(surfaces)('a field outline clears 3:1 on %s (WCAG 1.4.11)', (bg) => {
    expect(contrast(c.outline, c[bg])).toBeGreaterThanOrEqual(3);
  });

  it('keeps gray-600 and darker as body text on the darkest container', () => {
    for (const step of [600, 700, 800, 900]) {
      expect(contrast(theme.gray[step], c['surface-container-highest'])).toBeGreaterThanOrEqual(4.5);
    }
  });
});
