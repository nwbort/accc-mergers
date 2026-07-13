import { SECTION_HEADING } from '../utils/classNames';

/**
 * 2x4 stat-card grid used on industry/party detail pages. Distinct from
 * `StatCard` (the Dashboard's visually different treatment) — don't merge
 * the two.
 */
function DetailStatGrid({ statCards }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
      {statCards.map(({ label, value, subtitle }) => (
        <div key={label} className="bg-white p-5 rounded-2xl border border-gray-100 shadow-card">
          <p className={SECTION_HEADING}>{label}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight tabular-nums">
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export default DetailStatGrid;
