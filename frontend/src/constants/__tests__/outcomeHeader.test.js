import { describe, expect, it } from 'vitest';
import {
  APPEAL_FADE_COLOR,
  DEFAULT_OUTCOME_HEADER_STYLE,
  OUTCOME_HEADER_STYLES,
  getAppealFadeAccent,
  getAppealFadeStyle,
  getOutcomeHeaderStyle,
} from '../outcomeHeader';

// sRGB relative luminance, per WCAG 2.x.
function luminance([r, g, b]) {
  const channel = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

const contrastWithWhite = (rgb) => 1.05 / (luminance(rgb) + 0.05);

// The browser interpolates the gradient in sRGB, so a plain per-channel lerp
// reproduces exactly what lands on screen at a given point along the ramp.
const lerp = (from, to, t) => from.map((c, i) => c + (to[i] - from[i]) * t);

const allStyles = [...Object.values(OUTCOME_HEADER_STYLES), DEFAULT_OUTCOME_HEADER_STYLE];

describe('getAppealFadeStyle', () => {
  it('fades the outcome colour out to the appeal indigo, left to right', () => {
    const style = getAppealFadeStyle(getOutcomeHeaderStyle('Not approved'));
    expect(style.backgroundColor).toBe('#b91c1c');
    expect(style.backgroundImage).toBe(
      'linear-gradient(90deg, #b91c1c 0%, #b91c1c 35%, #4338ca 100%)'
    );
  });

  it('leaves a settled matter alone, so the fade only ever means "under appeal"', () => {
    expect(getAppealFadeStyle(null)).toBeNull();
    expect(getAppealFadeAccent(null)).toBeNull();
  });

  it('runs the same fade along the card top rule', () => {
    expect(getAppealFadeAccent(getOutcomeHeaderStyle('Approved'))).toBe(
      'linear-gradient(90deg, #047857 0%, #047857 35%, #4338ca 100%)'
    );
  });

  it('keeps white text legible at every point of every ramp (WCAG 1.4.3)', () => {
    // Endpoints are not enough: interpolating between two dark colours can
    // pass through a lighter one, and the title sits across the whole width.
    const indigo = hexToRgb(APPEAL_FADE_COLOR);
    for (const style of allStyles) {
      const base = hexToRgb(style.accent);
      let worst = Infinity;
      for (let step = 0; step <= 100; step += 1) {
        worst = Math.min(worst, contrastWithWhite(lerp(base, indigo, step / 100)));
      }
      expect(worst).toBeGreaterThanOrEqual(4.5);
    }
  });
});
