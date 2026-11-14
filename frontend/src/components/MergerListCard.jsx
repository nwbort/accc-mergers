import { useNavigate } from 'react-router';
import BellIcon from './BellIcon';
import MergerCardFace from './MergerCardFace';
import MateriallyIncompletePending from './MateriallyIncompletePending';
import { formatDateMedium } from '../utils/dates';
import { getBusinessDayProgress } from '../utils/businessDayProgress';
import { getOutcomeCardTint } from '../constants/outcomeCard';
import { MERGER_STATUS } from '../constants/mergerStatus';
import { mergerPath } from '../utils/slug';

/**
 * One merger in the /mergers card view, after the Android app's MergerCard:
 * the card tinted with its outcome's colour around MergerCardFace, with the
 * Track button on its status line. It squishes a little when pressed, as the
 * app's does.
 */
function MergerListCard({ merger, index, selected, tracked, onToggleTracking }) {
  const navigate = useNavigate();
  const path = mergerPath(merger.merger_id, merger.merger_name);
  const statusInput = {
    status: merger.status,
    determination: merger.accc_determination,
    hasConditions: merger.has_conditions,
    appeal: merger.appeal,
  };
  const tint = getOutcomeCardTint(statusInput);
  const progress = getBusinessDayProgress(merger);
  const suspended = merger.status === MERGER_STATUS.ASSESSMENT_SUSPENDED;

  // The one line under the name: id, when it was filed, when it was (or is
  // due to be) decided, and how far through its clock a live matter is.
  const meta = [<span key="id">{merger.merger_id}</span>];
  if (merger.materially_incomplete) {
    meta.push(<MateriallyIncompletePending key="pending" />);
  } else if (merger.effective_notification_datetime) {
    meta.push(
      <span key="filed">
        {merger.is_waiver ? 'Applied' : 'Notified'} {formatDateMedium(merger.effective_notification_datetime)}
      </span>,
    );
  } else if (suspended) {
    meta.push(<span key="filed">No notification date – assessment suspended</span>);
  }
  if (merger.determination_publication_date) {
    meta.push(<span key="decided">Determined {formatDateMedium(merger.determination_publication_date)}</span>);
  } else if (merger.end_of_determination_period && !suspended && !merger.materially_incomplete) {
    meta.push(<span key="due">Due {formatDateMedium(merger.end_of_determination_period)}</span>);
  }
  if (progress) {
    meta.push(
      progress.overdue ? (
        <span key="day" className="font-semibold text-amber-800">Overdue</span>
      ) : (
        <span key="day">Business day {progress.elapsed} of {progress.total}</span>
      ),
    );
  }

  return (
    <div
      data-merger-index={index}
      role="link"
      tabIndex={0}
      aria-label={`View merger details for ${merger.merger_name}`}
      onClick={() => navigate(path)}
      onAuxClick={(e) => {
        if (e.button === 1) window.open(path, '_blank');
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          navigate(path);
        }
      }}
      className={`group relative h-full rounded-2xl px-4 py-3.5 cursor-pointer ${tint} transition-[transform,box-shadow] duration-300 ease-spring hover:shadow-card-hover active:scale-[0.97] ${
        selected ? 'ring-2 ring-primary ring-offset-2 ring-offset-surface-container-low' : ''
      }`}
    >
      <MergerCardFace
        {...statusInput}
        flags={{
          underAppeal: merger.under_appeal,
          underJudicialReview: merger.under_judicial_review,
          waiver: merger.is_waiver,
          refiled: merger.is_refiled,
          materiallyIncomplete: merger.materially_incomplete,
        }}
        name={merger.merger_name}
        meta={meta}
        trailing={
          // Tracking, as the detail page's Track button, folded to an icon
          // button. Filled on a white disc while tracked, as the app marks a
          // followed card.
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onToggleTracking(merger.merger_id);
            }}
            onKeyDown={(e) => e.stopPropagation()}
            aria-pressed={tracked}
            aria-label={tracked ? `Stop tracking ${merger.merger_name}` : `Track ${merger.merger_name} for updates`}
            title={tracked ? 'Tracking' : 'Track'}
            className={`press-morph -my-1.5 -mr-1.5 inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${
              tracked
                ? 'bg-white text-primary'
                : 'text-gray-600 hover:bg-gray-900/[0.08] hover:text-gray-900'
            }`}
          >
            <BellIcon filled={tracked} className="h-4 w-4" />
          </button>
        }
      />
    </div>
  );
}

export default MergerListCard;
