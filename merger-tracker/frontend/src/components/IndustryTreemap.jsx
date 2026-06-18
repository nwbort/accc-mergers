import { Link } from 'react-router-dom';
import { FaArrowRightLong } from 'react-icons/fa6';

// A treemap-style heatmap of industries: cells packed by deal volume (flex-grow
// proportional to the merger count) and shaded by intensity. Acts as the visual
// overview at the top of the Industries page; the searchable table below carries
// the full detail.
//
// On small screens the long tail of low-volume sectors would stack into a tall
// single-column scroll, so we cap how many cells show on mobile (`mobileLimit`)
// and reveal the rest from `sm` up. The complete list always lives in the table.

const DEFAULT_DESKTOP_LIMIT = 24;
const DEFAULT_MOBILE_LIMIT = 8;

// Map a 0..1 intensity to a primary-tinted step. Full class strings so
// Tailwind's scanner keeps them.
function cellTone(intensity) {
  if (intensity > 0.66) return 'bg-primary text-white hover:bg-primary-dark';
  if (intensity > 0.33) return 'bg-primary/60 text-white hover:bg-primary/70';
  if (intensity > 0.15) return 'bg-primary/25 text-primary-dark hover:bg-primary/35';
  return 'bg-primary/10 text-primary-dark hover:bg-primary/20';
}

function IndustryTreemap({
  industries,
  desktopLimit = DEFAULT_DESKTOP_LIMIT,
  mobileLimit = DEFAULT_MOBILE_LIMIT,
}) {
  const cells = [...industries]
    .sort((a, b) => b.merger_count - a.merger_count)
    .slice(0, desktopLimit);

  if (cells.length === 0) return null;

  const maxCount = Math.max(...cells.map((i) => i.merger_count), 1);
  const hiddenOnMobile = cells.length - mobileLimit;

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {cells.map((ind, i) => {
          const intensity = ind.merger_count / maxCount;
          const hideOnMobile = i >= mobileLimit;
          return (
            <Link
              key={ind.code}
              to={`/industries/${ind.code}`}
              className={`group relative rounded-xl px-4 py-3 flex-col justify-between transition-colors ${cellTone(intensity)} ${
                hideOnMobile ? 'hidden sm:flex' : 'flex'
              }`}
              style={{
                flexGrow: ind.merger_count,
                flexBasis: `${120 + ind.merger_count * 4}px`,
                minHeight: '4.5rem',
              }}
              aria-label={`${ind.name}: ${ind.merger_count} merger reviews`}
            >
              <span className="text-[13px] font-semibold leading-tight line-clamp-2 pr-4">
                {ind.name}
              </span>
              <span className="mt-1 text-2xl font-bold tabular-nums leading-none">
                {ind.merger_count}
              </span>
              <FaArrowRightLong className="absolute top-3 right-3 h-3 w-3 opacity-0 group-hover:opacity-70 transition-opacity" />
            </Link>
          );
        })}
      </div>

      {/* Legend + mobile hint */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-gray-400">
        <span>Fewer deals</span>
        <span className="flex gap-1" aria-hidden="true">
          <span className="h-3 w-6 rounded bg-primary/10" />
          <span className="h-3 w-6 rounded bg-primary/25" />
          <span className="h-3 w-6 rounded bg-primary/60" />
          <span className="h-3 w-6 rounded bg-primary" />
        </span>
        <span>More deals</span>
        {hiddenOnMobile > 0 && (
          <span className="sm:hidden ml-auto text-gray-400">
            +{hiddenOnMobile} more below
          </span>
        )}
      </div>
    </div>
  );
}

export default IndustryTreemap;
