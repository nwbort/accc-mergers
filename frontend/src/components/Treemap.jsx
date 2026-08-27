import { useLayoutEffect, useRef } from 'react';
import { Link } from 'react-router';
import { FaArrowRightLong } from 'react-icons/fa6';
import { tailCellsToHide } from '../utils/treemapTail';

// A treemap-style heatmap: cells packed by deal volume (flex-grow
// proportional to the merger count) and shaded by intensity. Acts as the
// visual overview at the top of a listing page, with a searchable
// table/list below carrying the full detail.
//
// On small screens the long tail of low-volume items would stack into a tall
// single-column scroll, so we cap how many cells show on mobile (`mobileLimit`)
// and reveal the rest from `sm` up. The complete list always lives below.

const DEFAULT_DESKTOP_LIMIT = 24;
const DEFAULT_MOBILE_LIMIT = 8;

// Map a 0..1 intensity to a primary-tinted step. Full class strings so
// Tailwind's scanner keeps them. The two white-text steps use solid primary
// shades rather than alpha tints: a /60 tint of primary is only 3.1:1 behind
// white label text, short of WCAG 1.4.3's 4.5:1.
function cellTone(intensity) {
  if (intensity > 0.66) return 'bg-primary text-white hover:bg-primary-dark';
  if (intensity > 0.33) return 'bg-primary-light text-white hover:bg-primary';
  if (intensity > 0.15) return 'bg-primary/25 text-primary-dark hover:bg-primary/35';
  return 'bg-primary/10 text-primary-dark hover:bg-primary/20';
}

function Treemap({
  items,
  getKey,
  getPath,
  desktopLimit = DEFAULT_DESKTOP_LIMIT,
  mobileLimit = DEFAULT_MOBILE_LIMIT,
}) {
  const containerRef = useRef(null);

  const cells = [...items]
    .sort((a, b) => b.merger_count - a.merger_count)
    .slice(0, desktopLimit);
  // Re-measure whenever the cells themselves change, not just their number.
  const cellSizes = cells.map((item) => item.merger_count).join(',');

  // Trimming happens in the DOM rather than in React state: the decision needs
  // the laid-out rows, and re-rendering the full set to re-measure would flash
  // the tail back in. Hiding a trailing row can't reflow the rows above it, so
  // one pass per width settles it.
  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let lastWidth = null;
    const trimTail = () => {
      const children = Array.from(container.children);
      for (const child of children) child.style.display = '';
      const gap = parseFloat(getComputedStyle(container).columnGap) || 0;
      // offsetParent is null for the cells the mobile cap has hidden.
      const measured = children
        .filter((child) => child.offsetParent !== null)
        .map((child) => ({
          el: child,
          top: child.offsetTop,
          basis: parseFloat(child.style.flexBasis) || child.getBoundingClientRect().width,
        }));
      lastWidth = container.clientWidth;
      const hidden = tailCellsToHide(measured, lastWidth, gap);
      for (const { el } of measured.slice(measured.length - hidden)) {
        el.style.display = 'none';
      }
    };

    trimTail();
    const observer = new ResizeObserver(() => {
      // Hiding the tail changes the container's height, which would otherwise
      // re-enter this callback and fight itself. Only width can change the answer.
      if (container.clientWidth !== lastWidth) trimTail();
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, [cellSizes, mobileLimit]);

  if (cells.length === 0) return null;

  const maxCount = Math.max(...cells.map((i) => i.merger_count), 1);

  return (
    <div>
      <div ref={containerRef} className="flex flex-wrap gap-2">
        {cells.map((item, i) => {
          const intensity = item.merger_count / maxCount;
          const hideOnMobile = i >= mobileLimit;
          return (
            <Link
              key={getKey(item)}
              to={getPath(item)}
              className={`group relative rounded-xl px-4 py-3 flex-col justify-between transition-colors ${cellTone(intensity)} ${
                hideOnMobile ? 'hidden sm:flex' : 'flex'
              }`}
              style={{
                flexGrow: item.merger_count,
                flexBasis: `${120 + item.merger_count * 4}px`,
                minHeight: '4.5rem',
              }}
              aria-label={`${item.name}: ${item.merger_count} merger reviews`}
            >
              <span className="text-[13px] font-semibold leading-tight line-clamp-2 pr-4">
                {item.name}
              </span>
              <span className="mt-1 text-2xl font-bold tabular-nums leading-none">
                {item.merger_count}
              </span>
              <FaArrowRightLong className="absolute top-3 right-3 h-3 w-3 opacity-0 group-hover:opacity-70 transition-opacity" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default Treemap;
