import { describe, expect, it } from 'vitest';
import { computeEcdf, computeEcdfFromCounts } from '../durationEcdf';

// business days -> calendar days -> count. Five completed reviews at 10, 10,
// 20, 30 and 40 business days; the repeated 10 arrives as a count of 2 rather
// than as two entries.
const HISTOGRAM = {
  10: { 15: 2 },
  20: { 28: 1 },
  30: { 42: 1 },
  40: { 56: 1 },
};

describe('computeEcdf', () => {
  it('anchors the curve at the origin', () => {
    expect(computeEcdf(HISTOGRAM, false)[0]).toEqual({ x: 0, y: 0, n: 0, total: 5 });
  });

  it('sums each inner map when reading business days', () => {
    // The doubled 10 must move the curve twice while producing one point.
    expect(computeEcdf(HISTOGRAM, false).slice(1)).toEqual([
      { x: 10, y: 40, n: 2, total: 5 },
      { x: 20, y: 60, n: 3, total: 5 },
      { x: 30, y: 80, n: 4, total: 5 },
      { x: 40, y: 100, n: 5, total: 5 },
    ]);
  });

  it('folds the inner keys together when reading calendar days', () => {
    expect(computeEcdf(HISTOGRAM, true).slice(1)).toEqual([
      { x: 15, y: 40, n: 2, total: 5 },
      { x: 28, y: 60, n: 3, total: 5 },
      { x: 42, y: 80, n: 4, total: 5 },
      { x: 56, y: 100, n: 5, total: 5 },
    ]);
  });

  it('adds up counts that different pairs contribute to the same day', () => {
    // Two business-day buckets whose calendar days coincide at 20: reading
    // calendar days has to merge them into a single jump of 3.
    const points = computeEcdf({ 12: { 20: 2 }, 14: { 20: 1, 25: 1 } }, true);
    expect(points.slice(1)).toEqual([
      { x: 20, y: 75, n: 3, total: 4 },
      { x: 25, y: 100, n: 4, total: 4 },
    ]);
  });

  it('orders points numerically, not by the string form of the JSON keys', () => {
    // JSON object keys are strings, so a naive sort would put 100 before 9.
    expect(computeEcdf({ 9: { 9: 1 }, 100: { 100: 1 } }, false).map(p => p.x)).toEqual([0, 9, 100]);
  });

  it('returns no points for an empty histogram', () => {
    expect(computeEcdf({}, false)).toEqual([]);
  });

  it('returns no points when the histogram is absent', () => {
    // An analysis.json generated before these histograms existed; the page
    // reads this as "omit the chart" rather than throwing.
    expect(computeEcdf(undefined, false)).toEqual([]);
  });
});

describe('computeEcdfFromCounts', () => {
  // The flat shape current_status publishes per window: business days -> how
  // many matters were decided in exactly that many.
  const COUNTS = { 5: 2, 9: 1, 12: 1 };

  it('anchors the curve at the origin', () => {
    expect(computeEcdfFromCounts(COUNTS)[0]).toEqual({ x: 0, y: 0, n: 0, total: 4 });
  });

  it('steps the curve once per distinct duration, by its count', () => {
    expect(computeEcdfFromCounts(COUNTS).slice(1)).toEqual([
      { x: 5, y: 50, n: 2, total: 4 },
      { x: 9, y: 75, n: 3, total: 4 },
      { x: 12, y: 100, n: 4, total: 4 },
    ]);
  });

  it('orders points numerically, not by the string form of the JSON keys', () => {
    expect(computeEcdfFromCounts({ 9: 1, 100: 1 }).map(p => p.x)).toEqual([0, 9, 100]);
  });

  it('returns no points for an empty or absent map', () => {
    // A window with nothing decided in it, and a payload generated before the
    // per-window histograms existed. Both read as "omit the chart".
    expect(computeEcdfFromCounts({})).toEqual([]);
    expect(computeEcdfFromCounts(undefined)).toEqual([]);
  });
});
