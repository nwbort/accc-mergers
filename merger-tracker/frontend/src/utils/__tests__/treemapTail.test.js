import { describe, it, expect } from 'vitest';
import { tailCellsToHide } from '../treemapTail';

// Cells as the layout effect measures them: `top` groups them into rows and
// `basis` is the width each asks for before flex-grow stretches the row.
const row = (top, ...bases) => bases.map((basis) => ({ top, basis }));

const GAP = 8;
const WIDTH = 1000;

describe('tailCellsToHide', () => {
  it('hides a lone trailing cell that would stretch across the whole row', () => {
    const cells = [
      ...row(0, 300, 260, 240, 180),
      ...row(100, 170, 160, 150, 140),
      ...row(200, 130),
    ];
    expect(tailCellsToHide(cells, WIDTH, GAP)).toBe(1);
  });

  it('hides a short trailing row of several cells', () => {
    const cells = [...row(0, 300, 260, 240, 180), ...row(100, 130, 130)];
    expect(tailCellsToHide(cells, WIDTH, GAP)).toBe(2);
  });

  it('keeps a trailing row that nearly fills the line', () => {
    const cells = [...row(0, 300, 260, 240, 180), ...row(100, 300, 260, 240)];
    expect(tailCellsToHide(cells, WIDTH, GAP)).toBe(0);
  });

  it('keeps everything when the cells fit on a single row', () => {
    expect(tailCellsToHide(row(0, 300, 260, 130), WIDTH, GAP)).toBe(0);
  });

  it('keeps the tail on narrow viewports where every row holds one cell', () => {
    const cells = [...row(0, 200), ...row(100, 160), ...row(200, 130)];
    expect(tailCellsToHide(cells, 360, GAP)).toBe(0);
  });

  it('does nothing before the container has been measured', () => {
    const cells = [...row(0, 300, 260, 240, 180), ...row(100, 130)];
    expect(tailCellsToHide(cells, 0, GAP)).toBe(0);
  });
});
