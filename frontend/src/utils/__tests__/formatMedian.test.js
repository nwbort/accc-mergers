import { describe, expect, it } from 'vitest';
import { formatMedian } from '../formatMedian';

describe('formatMedian', () => {
  it('shows whole numbers without a trailing .0', () => {
    expect(formatMedian(26)).toBe(26);
    expect(formatMedian(26.0)).toBe(26);
  });

  it('keeps a single decimal place for .5 medians', () => {
    expect(formatMedian(26.5)).toBe('26.5');
  });
});
