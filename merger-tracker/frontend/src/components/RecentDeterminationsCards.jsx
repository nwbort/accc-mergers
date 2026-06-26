import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import NewBadge from './NewBadge';
import StatusBadge from './StatusBadge';
import WaiverBadge from './WaiverBadge';
import { MERGER_STATUS } from '../constants/mergerStatus';

const DETERMINATION_LABELS = {
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'Ceased',
};

// Card accent (left border + subtle background tint) keyed by determination.
// Full class names are required so Tailwind's scanner keeps them at build time.
const CARD_COLORS = {
  [MERGER_STATUS.APPROVED]: 'border-l-emerald-400 bg-emerald-50/30',
  [MERGER_STATUS.DECLINED]: 'border-l-red-400 bg-red-50/30',
  [MERGER_STATUS.NOT_APPROVED]: 'border-l-red-400 bg-red-50/30',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'border-l-amber-400 bg-amber-50/30',
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'border-l-purple-400 bg-purple-50/30',
};

const DEFAULT_CARD_COLOR = 'border-l-gray-300 bg-gray-50/30';

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
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {determinations.map((item) => (
          <li
            key={`${item.merger_id}-${item.determination_date}-${item.determination_type}`}
            className={`relative flex flex-col rounded-xl border border-gray-100 border-l-4 shadow-card p-4 transition-shadow hover:shadow-card-hover ${
              CARD_COLORS[item.determination] || DEFAULT_CARD_COLOR
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <StatusBadge
                determination={item.determination}
                label={DETERMINATION_LABELS[item.determination]}
              />
              {isNewItem(item.merger_id) && <NewBadge />}
            </div>
            <Link
              to={mergerPath(item.merger_id, item.merger_name)}
              className="mt-3 text-sm font-medium text-gray-900 hover:text-primary transition-colors after:absolute after:inset-0"
              aria-label={`View merger details for ${item.merger_name}`}
            >
              {item.merger_name}
            </Link>
            <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
              <span>{item.merger_id}</span>
              {item.is_waiver && <WaiverBadge />}
            </div>
            <div className="mt-2 text-xs text-gray-500">
              {formatDate(item.determination_date)}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default RecentDeterminationsCards;
