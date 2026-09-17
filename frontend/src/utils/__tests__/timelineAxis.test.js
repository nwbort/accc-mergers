import { describe, expect, it } from 'vitest';
import { ABOVE_LINE, BELOW_LINE, clampedLabelStyle, percentAlong } from '../timelineAxis';

const START = '2026-01-01';
const END = '2026-01-11'; // 10 calendar days later

describe('percentAlong', () => {
  it('places a date proportionally along the span', () => {
    expect(percentAlong('2026-01-06', START, END)).toBe(50);
    expect(percentAlong(START, START, END)).toBe(0);
    expect(percentAlong(END, START, END)).toBe(100);
  });

  it('clamps a date falling outside the span', () => {
    // Bad data or a clock restart must still render inside the bar.
    expect(percentAlong('2025-12-01', START, END)).toBe(0);
    expect(percentAlong('2026-03-01', START, END)).toBe(100);
  });

  it('returns null when any date is missing', () => {
    expect(percentAlong(null, START, END)).toBeNull();
    expect(percentAlong('2026-01-06', null, END)).toBeNull();
    expect(percentAlong('2026-01-06', START, undefined)).toBeNull();
    expect(percentAlong('2026-01-06', START, '')).toBeNull();
  });

  it('returns null when a date is unparseable', () => {
    expect(percentAlong('not-a-date', START, END)).toBeNull();
    expect(percentAlong('2026-01-06', 'not-a-date', END)).toBeNull();
  });

  it('returns null when the span has no positive length', () => {
    // A zero-length or inverted span would divide by zero or go negative.
    expect(percentAlong(START, START, START)).toBeNull();
    expect(percentAlong('2026-01-06', END, START)).toBeNull();
  });

  it('accepts full ISO datetimes, not just dates', () => {
    expect(percentAlong('2026-01-06T09:30:00Z', START, END)).toBe(50);
  });
});

describe('clampedLabelStyle', () => {
  it('centres the label on the percentage, clamped to the track', () => {
    expect(clampedLabelStyle(50, '2rem', 'translateX(-50%)')).toEqual({
      left: 'clamp(2rem, 50%, calc(100% - 2rem))',
      transform: 'translateX(-50%)',
    });
  });

  it('leaves the clamp to CSS so it survives a resize', () => {
    // The half-width is a CSS length, so the bound cannot be computed here.
    expect(clampedLabelStyle(0, '4.75rem', 'translate(-50%, -50%)').left)
      .toBe('clamp(4.75rem, 0%, calc(100% - 4.75rem))');
  });
});

describe('label offsets', () => {
  it('puts labels above and dates below the same line', () => {
    // The start/track/end columns share these so the three line up.
    expect(ABOVE_LINE).toContain('bottom-1/2');
    expect(BELOW_LINE).toContain('top-1/2');
  });
});
