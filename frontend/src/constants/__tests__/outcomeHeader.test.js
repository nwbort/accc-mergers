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
// Only the deep fills wash out to the appeal indigo, and only they carry white
// text over it.
const fadingStyles = allStyles.filter((style) => style.onDark);

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
    expect(fadingStyles.length).toBeGreaterThan(0);
    for (const style of fadingStyles) {
      const base = hexToRgb(style.accent);
      let worst = Infinity;
      for (let step = 0; step <= 100; step += 1) {
        worst = Math.min(worst, contrastWithWhite(lerp(base, indigo, step / 100)));
      }
      expect(worst).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('leaves a pale header unfaded, since its dark text could not survive one', () => {
    const live = getOutcomeHeaderStyle('Under assessment');
    expect(live.onDark).toBe(false);
    expect(getAppealFadeStyle(live)).toBeNull();
    expect(getAppealFadeAccent(live)).toBeNull();
  });
});

describe('the two registers', () => {
  it('gives a decided matter a deep fill and a live one a pale tint', () => {
    // Which register a matter lands in is what says whether it has finished,
    // so a status must never quietly borrow a determination's voice.
    for (const decided of ['Approved', 'Not approved', 'Declined', 'Assessment ceased']) {
      expect(getOutcomeHeaderStyle(decided).onDark).toBe(true);
    }
    for (const live of ['Under assessment', 'Assessment suspended', 'Referred to phase 2']) {
      expect(getOutcomeHeaderStyle(live).onDark).toBe(false);
    }
  });

  it('gives every style the full set of treatments, so the header reads the same either way', () => {
    for (const style of allStyles) {
      for (const key of ['bg', 'text', 'sub', 'link', 'accent']) {
        expect(style[key], `${style.bg} is missing ${key}`).toBeDefined();
      }
      expect(style.focus).toBeDefined();
      expect(style.heading).toBeDefined();
    }
  });
});
