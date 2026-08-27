import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { getCardStyle, NEW_ITEM_BORDER } from '../constants/cardStyles';
import CardCollapseGrid from './CardCollapseGrid';
import MergerCardBody, { CHIP_BASE_CLASS } from './MergerCardBody';
import EmptyStateCard from './EmptyStateCard';

// Mergers still under assessment stay calm: a white card with a green
// (primary) border, the inline chips tinted green to sit on the white
// surface. Anything with a determination (e.g. approved) falls through to
// getCardStyle so it renders identically to the recent determinations cards.
const UNDER_ASSESSMENT_STYLE = {
  bg: 'bg-white border border-primary/40 hover:border-primary',
  text: 'text-gray-900',
  sub: 'text-gray-500',
  chip: 'bg-primary/5 text-primary border border-primary/20',
};

// Tribunal appeal activity cards get their own indigo treatment (matching the
// "Under appeal" badge) so they read as a distinct kind of event among the
// recent notifications.
const APPEAL_CARD_STYLE = {
  bg: 'bg-indigo-700 hover:bg-indigo-800',
  text: 'text-white',
  sub: 'text-indigo-100',
  chip: 'bg-black/20 text-white',
};

function getMergerCardStyle(merger) {
  if (merger.is_appeal) return APPEAL_CARD_STYLE;
  const base =
    !merger.accc_determination && merger.status === MERGER_STATUS.UNDER_ASSESSMENT
      ? UNDER_ASSESSMENT_STYLE
      : getCardStyle({
          determination: merger.accc_determination,
          status: merger.status,
        });
  // Highlight recently notified mergers the visitor hasn't seen yet (those that
  // also show a "New" badge) with a blue ring so they stand out.
  return isNewItem(merger.merger_id) ? { ...base, border: NEW_ITEM_BORDER } : base;
}

// A merger and its appeal can both land in the list; the appeal card gets a
// distinct key so the two never collide.
const cardKey = (item) => (item.is_appeal ? `${item.merger_id}-appeal` : item.merger_id);

function RecentMergersCards({ mergers }) {
  if (!mergers || mergers.length === 0) {
    return (
      <EmptyStateCard
        heading="Recently notified mergers"
        message="No recently notified mergers."
      />
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
        getKey={cardKey}
        getStyle={getMergerCardStyle}
        renderBody={(merger, style) =>
          merger.is_appeal ? (
            <MergerCardBody
              style={style}
              label={merger.under_appeal ? 'Under appeal' : 'Appeal concluded'}
              mergerId={merger.merger_id}
              mergerName={merger.merger_name}
            >
              <span>{merger.merger_id}</span>
              <span aria-hidden="true">·</span>
              <span>Appeal filed {formatDate(merger.appeal_date)}</span>
              <span className={`${CHIP_BASE_CLASS} font-medium ${style.chip}`}>
                {merger.tribunal_number || 'Tribunal'}
              </span>
            </MergerCardBody>
          ) : (
            <MergerCardBody
              style={style}
              label={merger.accc_determination || merger.status}
              chip={isNewItem(merger.merger_id) ? 'New' : null}
              mergerId={merger.merger_id}
              mergerName={merger.merger_name}
            >
              <span>{merger.merger_id}</span>
              <span aria-hidden="true">·</span>
              <span>
                {merger.is_waiver ? 'Applied' : 'Notified'}{' '}
                {formatDate(merger.effective_notification_datetime)}
              </span>
              {merger.is_waiver && (
                <span className={`${CHIP_BASE_CLASS} font-medium ${style.chip}`}>
                  Waiver
                </span>
              )}
              {merger.is_refiled && (
                <span className={`${CHIP_BASE_CLASS} font-medium ${style.chip}`}>
                  Refiled
                </span>
              )}
            </MergerCardBody>
          )
        }
      />
    </section>
  );
}

export default RecentMergersCards;
