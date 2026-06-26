import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import { MERGER_STATUS } from '../constants/mergerStatus';

const DETERMINATION_LABELS = {
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'Ceased',
};

// Solid-colour treatment per determination, in the spirit of the Industries
// treemap cells: a saturated block with text laid directly on top. Most use
// white text; the amber "referred to phase 2" block reads better with dark
// text. `sub` tints the secondary text and `chip` styles the inline badges so
// they sit on the coloured surface. Full class strings so Tailwind keeps them.
const CARD_STYLES = {
  [MERGER_STATUS.APPROVED]: {
    bg: 'bg-emerald-600 hover:bg-emerald-700',
    text: 'text-white',
    sub: 'text-emerald-50/80',
    chip: 'bg-white/20 text-white',
  },
  [MERGER_STATUS.DECLINED]: {
    bg: 'bg-red-600 hover:bg-red-700',
    text: 'text-white',
    sub: 'text-red-50/80',
    chip: 'bg-white/20 text-white',
  },
  [MERGER_STATUS.NOT_APPROVED]: {
    bg: 'bg-red-600 hover:bg-red-700',
    text: 'text-white',
    sub: 'text-red-50/80',
    chip: 'bg-white/20 text-white',
  },
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: {
    bg: 'bg-amber-400 hover:bg-amber-500',
    text: 'text-amber-950',
    sub: 'text-amber-900/70',
    chip: 'bg-black/10 text-amber-950',
  },
  [MERGER_STATUS.ASSESSMENT_CEASED]: {
    bg: 'bg-purple-600 hover:bg-purple-700',
    text: 'text-white',
    sub: 'text-purple-50/80',
    chip: 'bg-white/20 text-white',
  },
};

const DEFAULT_CARD_STYLE = {
  bg: 'bg-gray-500 hover:bg-gray-600',
  text: 'text-white',
  sub: 'text-gray-50/80',
  chip: 'bg-white/20 text-white',
};

function RecentDeterminationsCards({ determinations }) {
  if (!determinations || determinations.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Recent determinations
        </h2>
        <p className="text-gray-500 text-sm">No recent determinations.</p>
      </div>
    );
  }

  return (
    <section aria-labelledby="recent-determinations-heading">
      <h2
        id="recent-determinations-heading"
        className="text-lg font-semibold text-gray-900 mb-4"
      >
        Recent determinations
      </h2>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {determinations.map((item) => {
          const style = CARD_STYLES[item.determination] || DEFAULT_CARD_STYLE;
          const label = DETERMINATION_LABELS[item.determination] || item.determination;
          return (
            <li
              key={`${item.merger_id}-${item.determination_date}-${item.determination_type}`}
              className={`relative flex min-h-[7rem] flex-col justify-between rounded-xl p-4 transition-colors ${style.bg} ${style.text}`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide">
                  {label}
                </span>
                {isNewItem(item.merger_id) && (
                  <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${style.chip}`}>
                    New
                  </span>
                )}
              </div>
              <Link
                to={mergerPath(item.merger_id, item.merger_name)}
                className={`mt-2 text-sm font-semibold leading-snug hover:underline after:absolute after:inset-0 ${style.text}`}
                aria-label={`View merger details for ${item.merger_name}`}
              >
                {item.merger_name}
              </Link>
              <div className={`mt-2 flex flex-wrap items-center gap-2 text-xs ${style.sub}`}>
                <span>{item.merger_id}</span>
                <span aria-hidden="true">·</span>
                <span>{formatDate(item.determination_date)}</span>
                {item.is_waiver && (
                  <span className={`inline-flex items-center rounded-md px-2 py-0.5 font-medium ${style.chip}`}>
                    Waiver
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default RecentDeterminationsCards;
