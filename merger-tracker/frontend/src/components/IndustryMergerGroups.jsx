import { Link } from 'react-router-dom';
import { mergerPath } from '../utils/slug';
import WaiverBadge from './WaiverBadge';
import { groupMergersByPhase } from '../utils/industryGroups';

/**
 * Render an industry's mergers split into Phase 2 / Phase 1 / Waiver groups,
 * each with a subheading and count. Empty groups are skipped.
 *
 * `variant`:
 *   - "full"    larger cards (industry detail page)
 *   - "compact" smaller cards (expanded row on the industries list)
 */
function IndustryMergerGroups({ mergers, variant = 'full' }) {
  const groups = groupMergersByPhase(mergers);
  const compact = variant === 'compact';

  return (
    <div className={compact ? 'space-y-4' : 'space-y-6'}>
      {groups.map((group) => (
        <div key={group.key}>
          <div className="flex items-center gap-2 mb-2">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {group.label}
            </h3>
            <span className="inline-flex items-center justify-center min-w-[1.25rem] px-1.5 h-5 rounded-full text-[11px] font-semibold bg-gray-100 text-gray-600">
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
                <span className={`text-xs text-gray-500 block ${compact ? 'mt-1' : 'mt-1'}`}>
                  {merger.status}
                </span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default IndustryMergerGroups;
