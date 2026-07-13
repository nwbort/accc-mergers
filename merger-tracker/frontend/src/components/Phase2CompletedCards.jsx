import { calculateDuration } from '../utils/dates';
import { DETERMINATION_LABELS } from '../constants/mergerStatus';
import { getCardStyle } from '../constants/cardStyles';
import CardCollapseGrid from './CardCollapseGrid';
import MergerCardBody from './MergerCardBody';

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
          <MergerCardBody
            style={style}
            label={DETERMINATION_LABELS[item.determination] || item.determination}
            mergerId={item.merger_id}
            mergerName={item.merger_name}
          >
            <span>{item.merger_id}</span>
            {duration !== null && (
              <>
                <span aria-hidden="true">·</span>
                <span className="tabular-nums">{duration} days in Phase 2</span>
              </>
            )}
          </MergerCardBody>
        );
      }}
    />
  );
}

export default Phase2CompletedCards;
