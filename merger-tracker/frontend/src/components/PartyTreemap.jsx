import { Link } from 'react-router-dom';
import { FaArrowRightLong } from 'react-icons/fa6';
import { partyPath } from '../utils/slug';

// A treemap-style heatmap of parties: cells packed by deal volume (flex-grow
// proportional to the merger count) and shaded by intensity. Acts as the visual
// overview at the top of the Parties page; the searchbox below finds the long
// tail that the treemap deliberately omits.
//
// Mirrors IndustryTreemap. On small screens the long tail of low-volume parties
// would stack into a tall single-column scroll, so we cap how many cells show on
// mobile (`mobileLimit`) and reveal the rest from `sm` up.

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

function PartyTreemap({
  parties,
  desktopLimit = DEFAULT_DESKTOP_LIMIT,
  mobileLimit = DEFAULT_MOBILE_LIMIT,
}) {
  const cells = [...parties]
    .sort((a, b) => b.merger_count - a.merger_count)
    .slice(0, desktopLimit);

  if (cells.length === 0) return null;

  const maxCount = Math.max(...cells.map((p) => p.merger_count), 1);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {cells.map((party, i) => {
          const intensity = party.merger_count / maxCount;
          const hideOnMobile = i >= mobileLimit;
          return (
            <Link
              key={party.id}
              to={partyPath(party.id, party.name)}
              className={`group relative rounded-xl px-4 py-3 flex-col justify-between transition-colors ${cellTone(intensity)} ${
                hideOnMobile ? 'hidden sm:flex' : 'flex'
              }`}
              style={{
                flexGrow: party.merger_count,
                flexBasis: `${120 + party.merger_count * 4}px`,
                minHeight: '4.5rem',
              }}
              aria-label={`${party.name}: ${party.merger_count} merger reviews`}
            >
              <span className="text-[13px] font-semibold leading-tight line-clamp-2 pr-4">
                {party.name}
              </span>
              <span className="mt-1 text-2xl font-bold tabular-nums leading-none">
                {party.merger_count}
              </span>
              <FaArrowRightLong className="absolute top-3 right-3 h-3 w-3 opacity-0 group-hover:opacity-70 transition-opacity" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}

export default PartyTreemap;
