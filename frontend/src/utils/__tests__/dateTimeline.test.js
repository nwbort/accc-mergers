import { describe, expect, it } from 'vitest';
import { buildTimeline, isIsoDate, monthsBetween, quickRanges } from '../dateTimeline';

describe('monthsBetween', () => {
  it('lists every month with its first and last day, across a year end', () => {
    const months = monthsBetween('2025-11-17', '2026-02-03');
    expect(months.map((m) => [m.from, m.to])).toEqual([
      ['2025-11-01', '2025-11-30'],
      ['2025-12-01', '2025-12-31'],
      ['2026-01-01', '2026-01-31'],
      ['2026-02-01', '2026-02-28'],
    ]);
  });
});

describe('buildTimeline', () => {
  it('draws Monday-to-Sunday weeks from the first date to today', () => {
    // 8 Aug 2025 was a Friday.
    const { unit, bars } = buildTimeline('2025-08-08', '2026-10-22');
    expect(unit).toBe('week');
    expect(bars[0]).toEqual({ from: '2025-08-04', to: '2025-08-10' });
    expect(bars.at(-1).from <= '2026-10-22').toBe(true);
    expect(bars.at(-1).to >= '2026-10-22').toBe(true);
  });

  it('puts every bar under exactly one month button', () => {
    const { bars, months } = buildTimeline('2025-08-08', '2026-10-22');
    const covered = months.flatMap((m) => Array.from({ length: m.lastBar - m.firstBar + 1 }, (_, i) => m.firstBar + i));
    expect(covered).toEqual(bars.map((_, i) => i));
  });

  it('names every month, with the year under the first and each January', () => {
    const { months } = buildTimeline('2025-08-08', '2026-10-22');
    expect(months.every((m) => m.showsName)).toBe(true);
    expect(months.filter((m) => m.showsYear).map((m) => m.key)).toEqual(['2025-08', '2026-01']);
  });

  it('switches to monthly bars, labelling only the year marks, once the span is long', () => {
    const { unit, bars, months } = buildTimeline('2025-08-08', '2027-12-01');
    expect(unit).toBe('month');
    expect(bars).toHaveLength(months.length);
    expect(months.filter((m) => m.showsName).map((m) => m.key)).toEqual(['2025-08', '2026-01', '2027-01']);
  });
});

describe('quickRanges', () => {
  it('ends every range today and offers last year only when the data reaches it', () => {
    const ranges = quickRanges('2025-08-08', '2026-10-22');
    expect(ranges.map((r) => [r.key, r.from, r.to])).toEqual([
      ['30d', '2026-09-23', '2026-10-22'],
      ['90d', '2026-07-25', '2026-10-22'],
      ['this-year', '2026-01-01', '2026-10-22'],
      ['last-year', '2025-01-01', '2025-12-31'],
    ]);
    expect(quickRanges('2026-02-01', '2026-10-22').map((r) => r.key)).not.toContain('last-year');
  });
});

describe('isIsoDate', () => {
  it('accepts real calendar days only', () => {
    expect(isIsoDate('2026-02-28')).toBe(true);
    expect(isIsoDate('2026-02-30')).toBe(false);
    expect(isIsoDate('2026-2-28')).toBe(false);
    expect(isIsoDate('soon')).toBe(false);
    expect(isIsoDate(null)).toBe(false);
  });
});
