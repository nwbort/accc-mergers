import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { getCardStyle } from '../constants/cardStyles';
import CardCollapseGrid from './CardCollapseGrid';

const DETERMINATION_LABELS = {
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'Ceased',
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
      <CardCollapseGrid
        items={determinations}
        getKey={(item) =>
          `${item.merger_id}-${item.determination_date}-${item.determination_type}`
        }
        getStyle={(item) => getCardStyle({ determination: item.determination })}
        renderBody={(item, style) => (
          <>
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide">
                {DETERMINATION_LABELS[item.determination] || item.determination}
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
          </>
        )}
      />
    </section>
  );
}

export default RecentDeterminationsCards;
