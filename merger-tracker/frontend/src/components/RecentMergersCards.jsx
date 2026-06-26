import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import { getCardStyle } from '../constants/cardStyles';
import CardCollapseGrid from './CardCollapseGrid';

function RecentMergersCards({ mergers }) {
  if (!mergers || mergers.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Recently notified mergers
        </h2>
        <p className="text-gray-500 text-sm">No recently notified mergers.</p>
      </div>
    );
  }

  return (
    <section aria-labelledby="recent-mergers-heading">
      <h2
        id="recent-mergers-heading"
        className="text-lg font-semibold text-gray-900 mb-4"
      >
        Recently notified mergers
      </h2>
      <CardCollapseGrid
        items={mergers}
        getKey={(merger) => merger.merger_id}
        getStyle={(merger) =>
          getCardStyle({
            determination: merger.accc_determination,
            status: merger.status,
          })
        }
        renderBody={(merger, style) => (
          <>
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-semibold uppercase tracking-wide">
                {merger.accc_determination || merger.status}
              </span>
              {isNewItem(merger.merger_id) && (
                <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${style.chip}`}>
                  New
                </span>
              )}
            </div>
            <Link
              to={mergerPath(merger.merger_id, merger.merger_name)}
              className={`mt-2 text-sm font-semibold leading-snug hover:underline after:absolute after:inset-0 ${style.text}`}
              aria-label={`View merger details for ${merger.merger_name}`}
            >
              {merger.merger_name}
            </Link>
            <div className={`mt-2 flex flex-wrap items-center gap-2 text-xs ${style.sub}`}>
              <span>{merger.merger_id}</span>
              <span aria-hidden="true">·</span>
              <span>
                {merger.is_waiver ? 'Applied' : 'Notified'}{' '}
                {formatDate(merger.effective_notification_datetime)}
              </span>
              {merger.is_waiver && (
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

export default RecentMergersCards;
