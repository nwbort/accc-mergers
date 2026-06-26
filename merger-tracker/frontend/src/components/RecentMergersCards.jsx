import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import { getLightCardStyle } from '../constants/cardStyles';
import StatusBadge from './StatusBadge';
import NewBadge from './NewBadge';
import WaiverBadge from './WaiverBadge';
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
          getLightCardStyle({ determination: merger.accc_determination, status: merger.status })
        }
        renderBody={(merger, style) => (
          <>
            <div className="flex items-start justify-between gap-2">
              <StatusBadge
                status={merger.status}
                determination={merger.accc_determination}
              />
              {isNewItem(merger.merger_id) && <NewBadge />}
            </div>
            <Link
              to={mergerPath(merger.merger_id, merger.merger_name)}
              className={`mt-2 text-sm font-semibold leading-snug hover:text-primary after:absolute after:inset-0 ${style.text}`}
              aria-label={`View merger details for ${merger.merger_name}`}
            >
              {merger.merger_name}
            </Link>
            <div className={`mt-2 flex flex-wrap items-center gap-2 text-xs ${style.sub}`}>
              <span>
                {merger.is_waiver ? 'Applied' : 'Notified'}{' '}
                {formatDate(merger.effective_notification_datetime)}
              </span>
              {merger.is_waiver && <WaiverBadge />}
            </div>
          </>
        )}
      />
    </section>
  );
}

export default RecentMergersCards;
