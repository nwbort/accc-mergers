// Row measurement for the Treemap heatmap (src/components/Treemap.jsx).
//
// Flexbox grows the cells on the final row to fill the line, so a short tail —
// often a single low-volume item — is drawn as wide as the busiest cell on the
// page, reading as the exact opposite of what its number says. The component
// measures the wrapped rows after layout and asks here whether the last row is
// misleading enough to drop; the full ranking is always in the table below.
//
// A row is "full" up to the width of whichever cell forced the wrap, so genuine
// rows sit near 1. The tail has to be well under half a row, and well below the
// row above it, before we take it away.
const TAIL_MAX_FILL = 0.55;
const TAIL_MIN_DROP = 0.25;

// Cells share a row when their offsetTop matches (1px of slack for subpixel
// layout). `cells` arrive in DOM order, so rows come out in visual order.
function groupIntoRows(cells) {
  const rows = [];
  let rowTop = null;
  for (const cell of cells) {
    if (rowTop === null || Math.abs(cell.top - rowTop) > 1) {
      rows.push([]);
      rowTop = cell.top;
    }
    rows[rows.length - 1].push(cell);
  }
  return rows;
}

// How many trailing cells to hide: either the whole last row, or none. Each
// cell is `{ top, basis }` — the basis being the width the cell asks for before
// flex-grow stretches it.
export function tailCellsToHide(cells, containerWidth, gap) {
  if (!containerWidth) return 0;
  const rows = groupIntoRows(cells);
  if (rows.length < 2) return 0;

  const fill = (row) =>
    (row.reduce((sum, cell) => sum + cell.basis, 0) + gap * (row.length - 1)) / containerWidth;
  const tail = rows[rows.length - 1];
  const tailFill = fill(tail);
  const aboveFill = fill(rows[rows.length - 2]);

  // The second test keeps narrow viewports intact: there every row holds one
  // cell and is equally underfull, so the tail isn't misleading at all.
  if (tailFill >= TAIL_MAX_FILL || aboveFill - tailFill < TAIL_MIN_DROP) return 0;
  return tail.length;
}
