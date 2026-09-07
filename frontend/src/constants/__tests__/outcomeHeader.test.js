import { describe, expect, it } from 'vitest';
import {
  DEFAULT_OUTCOME_HEADER_STYLE,
  OUTCOME_HEADER_STYLES,
  getAppealStripeAccent,
  getAppealStripeStyle,
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

// indigo-700 at the alpha the stripe uses, composited over an opaque fill.
const STRIPE_RGB = [67, 56, 202];
const STRIPE_ALPHA = 0.5;
const composite = (base) =>
  base.map((c, i) => c * (1 - STRIPE_ALPHA) + STRIPE_RGB[i] * STRIPE_ALPHA);

describe('getAppealStripeStyle', () => {
  it('stripes the outcome fill rather than replacing it', () => {
    const style = getAppealStripeStyle(getOutcomeHeaderStyle('Not approved'));
    expect(style.backgroundColor).toBe('#b91c1c');
    expect(style.backgroundImage).toContain('repeating-linear-gradient');
    expect(style.backgroundImage).toContain('rgba(67, 56, 202, 0.5)');
  });

  it('leaves a settled matter alone, so the stripe only ever means "under appeal"', () => {
    expect(getAppealStripeStyle(null)).toBeNull();
    expect(getAppealStripeAccent(null)).toBeNull();
  });

  it('carries the stripe onto the card top rule over the same base colour', () => {
    const accent = getAppealStripeAccent(getOutcomeHeaderStyle('Approved'));
    expect(accent).toMatch(/^repeating-linear-gradient\(.*\), #047857$/);
  });

  it('keeps white text legible on every band of every outcome (WCAG 1.4.3)', () => {
    // Text sits across both bands, so both have to clear the ratio — the fill
    // on its own, and the fill with the stripe composited over it.
    for (const style of [...Object.values(OUTCOME_HEADER_STYLES), DEFAULT_OUTCOME_HEADER_STYLE]) {
      const base = hexToRgb(style.accent);
      expect(contrastWithWhite(base)).toBeGreaterThanOrEqual(4.5);
      expect(contrastWithWhite(composite(base))).toBeGreaterThanOrEqual(4.5);
    }
  });
});
