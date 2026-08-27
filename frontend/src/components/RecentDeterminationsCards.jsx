import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import { DETERMINATION_LABELS, isConditionalApproval } from '../constants/mergerStatus';
import { getCardStyle, NEW_ITEM_BORDER } from '../constants/cardStyles';
import CardCollapseGrid from './CardCollapseGrid';
import MergerCardBody, { CHIP_BASE_CLASS } from './MergerCardBody';
import EmptyStateCard from './EmptyStateCard';

function getDeterminationCardStyle(item) {
  const base = getCardStyle({ determination: item.determination });
  // Highlight recent determinations the visitor hasn't seen yet (those that
  // also show a "New" badge) with a blue ring so they stand out.
  return isNewItem(item.merger_id) ? { ...base, border: NEW_ITEM_BORDER } : base;
}

function RecentDeterminationsCards({ determinations }) {
  if (!determinations || determinations.length === 0) {
    return (
      <EmptyStateCard heading="Recent determinations" message="No recent determinations." />
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
        getStyle={getDeterminationCardStyle}
        renderBody={(item, style) => (
          <MergerCardBody
            style={style}
            label={DETERMINATION_LABELS[item.determination] || item.determination}
            chip={isNewItem(item.merger_id) ? 'New' : null}
            mergerId={item.merger_id}
            mergerName={item.merger_name}
          >
            <span>{item.merger_id}</span>
            <span aria-hidden="true">·</span>
            <span>{formatDate(item.determination_date)}</span>
            {isConditionalApproval(item) && (
              <span className={`${CHIP_BASE_CLASS} font-medium ${style.chip}`}>
                With conditions
              </span>
            )}
            {item.is_waiver && (
              <span className={`${CHIP_BASE_CLASS} font-medium ${style.chip}`}>
                Waiver
              </span>
            )}
          </MergerCardBody>
        )}
      />
    </section>
  );
}

export default RecentDeterminationsCards;
