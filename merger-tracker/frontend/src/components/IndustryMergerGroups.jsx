import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import WaiverBadge from './WaiverBadge';
import { groupMergersByPhase } from '../utils/industryGroups';

// Per-phase accent styling. Literal class strings so Tailwind picks them up.
const GROUP_STYLES = {
  'Phase 2': { bar: 'bg-phase-2', pill: 'bg-phase-2-pale text-phase-2-dark' },
  'Phase 1': { bar: 'bg-phase-1', pill: 'bg-phase-1-pale text-phase-1-dark' },
  'Waiver': { bar: 'bg-amber-400', pill: 'bg-amber-50 text-amber-700' },
};

/**
 * Render an industry's mergers split into Phase 2 / Phase 1 / Waiver groups,
 * each under a colour-accented section header with a count. Empty groups are
 * skipped.
 *
 * `variant`:
 *   - "full"    larger cards (industry detail page)
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
            <div className="flex items-center gap-2.5 mb-3 pb-2 border-b border-gray-100">
              <span className={`h-4 w-1 rounded-full ${style.bar}`} aria-hidden="true" />
              <h3 className="text-sm font-semibold text-gray-900">{group.label}</h3>
              <span className={`inline-flex items-center justify-center min-w-[1.375rem] px-1.5 h-5 rounded-full text-[11px] font-semibold ${style.pill}`}>
                {group.mergers.length}
              </span>
            </div>
            <div className={compact ? 'space-y-2' : 'space-y-3'}>
              {group.mergers.map((merger) => (
                <Link
                  key={merger.merger_id}
                  to={mergerPath(merger.merger_id, merger.merger_name)}
                  className={
                    compact
                      ? 'block p-3 bg-white rounded-xl border border-gray-100 hover:border-primary/30 hover:shadow-sm transition-all'
                      : 'block bg-white rounded-2xl border border-gray-100 shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 p-5'
                  }
                  aria-label={`View merger details for ${merger.merger_name}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {compact ? (
                      <span className="text-sm font-medium text-gray-900 truncate">
                        {merger.merger_name}
                      </span>
                    ) : (
                      <h4 className="text-base font-semibold text-gray-900 truncate hover:text-primary transition-colors">
                        {merger.merger_name}
                      </h4>
                    )}
                    {merger.is_waiver && <WaiverBadge className="flex-shrink-0" />}
                  </div>
                  <span className="text-xs text-gray-500 mt-1 block">
                    {merger.status}
                  </span>
                </Link>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

export default IndustryMergerGroups;
