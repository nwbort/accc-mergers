import { describe, it, expect } from 'vitest';
import { Interaction } from 'chart.js';
import { stepIndexAt } from '../../utils/durationEcdf';
import '../DurationEcdfChart';

describe('DurationEcdfChart hover', () => {
  const points = [{ x: 0 }, { x: 5 }, { x: 12 }, { x: 30 }];

  it('reads the step in force at the pointer, not the nearest point', () => {
    expect(stepIndexAt(points, 0)).toBe(0);
    expect(stepIndexAt(points, 11.9)).toBe(1);
    expect(stepIndexAt(points, 12)).toBe(2);
    expect(stepIndexAt(points, 29)).toBe(2);
    expect(stepIndexAt(points, 40)).toBe(3);
  });

  it('has nothing to read left of the origin', () => {
    expect(stepIndexAt(points, -1)).toBe(-1);
  });

  it('registers the interaction mode the chart asks for', () => {
    expect(typeof Interaction.modes.ecdfStep).toBe('function');
  });
});
