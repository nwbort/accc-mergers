import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import { calculateDuration } from '../utils/dates';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { getCardStyle } from '../constants/cardStyles';
import CardCollapseGrid from './CardCollapseGrid';

// "Assessment ceased" is a mouthful for the compact card header; abbreviate it
// the same way the dashboard's recent-determination cards do.
const DETERMINATION_LABELS = {
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'Ceased',
};

// Solid, determination-coloured cards for completed Phase 2 matters — echoing
// the dashboard card grids. Each card surfaces just the outcome and the time
// the review took, laid over a colour that reflects the determination.
function Phase2CompletedCards({ matters }) {
  return (
    <CardCollapseGrid
      items={matters}
      getKey={(item) => item.merger_id}
      getStyle={(item) => getCardStyle({ determination: item.determination })}
      renderBody={(item, style) => {
        const duration = calculateDuration(item.referral_date, item.determination_date);
        return (
          <>
            <span className="text-xs font-semibold uppercase tracking-wide">
              {DETERMINATION_LABELS[item.determination] || item.determination}
            </span>
            <Link
              to={mergerPath(item.merger_id, item.merger_name)}
              className={`mt-2 text-sm font-semibold leading-snug hover:underline after:absolute after:inset-0 ${style.text}`}
              aria-label={`View merger details for ${item.merger_name}`}
            >
              {item.merger_name}
            </Link>
            <div className={`mt-2 flex flex-wrap items-center gap-2 text-xs ${style.sub}`}>
              <span>{item.merger_id}</span>
              {duration !== null && (
                <>
                  <span aria-hidden="true">·</span>
                  <span className="tabular-nums">{duration} days in Phase 2</span>
                </>
              )}
            </div>
          </>
        );
      }}
    />
  );
}

export default Phase2CompletedCards;
