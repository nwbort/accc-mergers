import { Link } from 'react-router';
import StatusBadge from './StatusBadge';
import WaiverBadge from './WaiverBadge';
import AppealBadge from './AppealBadge';
import JudicialReviewBadge from './JudicialReviewBadge';
import { mergerPath } from '../utils/slug';
import { groupMergersByPhase } from '../utils/industryGroups';
import { getOutcomeRail } from '../constants/outcomeRail';
import { formatDateMedium } from '../utils/dates';
import MergerCardFace from './MergerCardFace';
import { getOutcomeCardTint } from '../constants/outcomeCard';

// Per-phase accent styling. Literal class strings so Tailwind picks them up.
const GROUP_STYLES = {
  'Phase 2': { bar: 'bg-phase-2', pill: 'bg-phase-2-pale text-phase-2-dark', line: 'border-phase-2-light' },
  'Phase 1': { bar: 'bg-phase-1', pill: 'bg-phase-1-pale text-phase-1-dark', line: 'border-phase-1-light' },
  'Waiver': { bar: 'bg-waiver', pill: 'bg-waiver-pale text-waiver-dark', line: 'border-waiver-light' },
};

/**
 * Render an industry's mergers split into Phase 2 / Phase 1 / Waiver groups,
 * each under a colour-accented section header with a count. Empty groups are
 * skipped.
 *
 * `variant`:
 *   - "full"    the merger list's cards (industry and party detail pages)
 *   - "compact" smaller cards (expanded row on the industries list)
 */
function IndustryMergerGroups({ mergers, variant = 'full' }) {
  const groups = groupMergersByPhase(mergers);
  const compact = variant === 'compact';

  return (
    <div className={compact ? 'space-y-5' : 'space-y-7'}>
      {groups.map((group) => {
        const style = GROUP_STYLES[group.key] || GROUP_STYLES['Phase 1'];
        return (
          <section key={group.key}>
            <div className={`flex items-center gap-2.5 mb-3 pb-2 border-b border-gray-100${compact ? ' sticky top-0 bg-gray-100 z-10' : ''}`}>
              <span className={`h-4 w-1 rounded-full ${style.bar}`} aria-hidden="true" />
              <h3 className="text-sm font-semibold text-gray-900">{group.label}</h3>
              <span className={`inline-flex items-center justify-center min-w-[1.375rem] px-1.5 h-5 rounded-full text-[11px] font-semibold ${style.pill}`}>
                {group.mergers.length}
              </span>
            </div>
            <div className={compact ? `space-y-2 pl-3 border-l-2 ${style.line}` : 'grid gap-3 lg:grid-cols-2'}>
              {group.mergers.map((merger) => {
                // The compact rows (an expanded industry on /industries): a
                // solid outcome badge under the name, with a colour-matched
                // rail down the left edge.
                const railColor = getOutcomeRail({
                  status: merger.status,
                  determination: merger.determination,
                });

                if (compact) {
                  return (
                    <Link
                      key={merger.merger_id}
                      to={mergerPath(merger.merger_id, merger.merger_name)}
                      className="relative overflow-hidden block p-3 pl-4 bg-white rounded-xl border border-gray-100 hover:border-primary/30 hover:shadow-sm transition-all"
                      aria-label={`View merger details for ${merger.merger_name}`}
                    >
                      <span
                        className={`absolute inset-y-0 left-0 w-1 ${railColor}`}
                        aria-hidden="true"
                      />
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="text-sm font-medium text-gray-900 truncate">
                          {merger.merger_name}
                        </span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <StatusBadge
                          status={merger.status}
                          determination={merger.determination}
                          hasConditions={merger.has_conditions}
                          solid
                        />
                        {merger.is_waiver && <WaiverBadge solid />}
                        {merger.under_appeal && <AppealBadge solid />}
                        {merger.under_judicial_review && <JudicialReviewBadge solid />}
                      </div>
                    </Link>
                  );
                }

                // The merger list's card (MergerCardFace), tinted the same
                // way, without the Track button.
                const statusInput = {
                  status: merger.status,
                  determination: merger.determination,
                  hasConditions: merger.has_conditions,
                };
                return (
                  <Link
                    key={merger.merger_id}
                    to={mergerPath(merger.merger_id, merger.merger_name)}
                    className={`group block rounded-2xl px-4 py-3.5 ${getOutcomeCardTint(statusInput)} transition-[transform,box-shadow] duration-300 ease-spring hover:shadow-card-hover active:scale-[0.97]`}
                    aria-label={`View merger details for ${merger.merger_name}`}
                  >
                    <MergerCardFace
                      {...statusInput}
                      flags={{
                        waiver: merger.is_waiver,
                        underAppeal: merger.under_appeal,
                        underJudicialReview: merger.under_judicial_review,
                      }}
                      name={merger.merger_name}
                      Heading="h4"
                      meta={[
                        merger.merger_id,
                        merger.notification_date && `${merger.is_waiver ? 'Applied' : 'Notified'} ${formatDateMedium(merger.notification_date)}`,
                        merger.determination_date && `Determined ${formatDateMedium(merger.determination_date)}`,
                      ]}
                    />
                  </Link>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}

export default IndustryMergerGroups;
