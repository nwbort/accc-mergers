import { Link } from 'react-router-dom';
import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import NewBadge from './NewBadge';
import WaiverBadge from './WaiverBadge';

const DETERMINATION_ICONS = {
  'Approved':           { symbol: '✓', classes: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
  'Not opposed':        { symbol: '✓', classes: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
  'Not approved':       { symbol: '✗', classes: 'text-red-700 bg-red-50 border-red-200' },
  'Declined':           { symbol: '✗', classes: 'text-red-700 bg-red-50 border-red-200' },
  'Referred to phase 2':{ symbol: '→', classes: 'text-amber-700 bg-amber-50 border-amber-200' },
};

function DeterminationIcon({ determination }) {
  const icon = DETERMINATION_ICONS[determination] ?? { symbol: '?', classes: 'text-gray-500 bg-gray-50 border-gray-200' };
  return (
    <span className="relative group/det inline-flex">
      <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full border text-xs font-bold ${icon.classes}`}>
        {icon.symbol}
      </span>
      <span className="absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 rounded-md bg-gray-900 text-white text-xs whitespace-nowrap opacity-0 group-hover/det:opacity-100 transition-opacity duration-150 pointer-events-none">
        {determination}
      </span>
    </span>
  );
}

function RecentDeterminationsTable({ determinations }) {
  if (!determinations || determinations.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
        <div className="px-5 sm:px-6 py-4 bg-primary">
          <h2 className="text-lg font-semibold text-white">Recent determinations</h2>
        </div>
        <p className="text-gray-500 text-sm p-6">No recent determinations.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
      <div className="px-5 sm:px-6 py-4 bg-primary">
        <h2 id="recent-determinations-heading" className="text-lg font-semibold text-white">
          Recent determinations
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200" aria-labelledby="recent-determinations-heading">
          <thead>
            <tr className="bg-gray-50/80">
              <th scope="col" className="px-5 sm:px-6 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Merger
              </th>
              <th scope="col" className="px-5 sm:px-6 py-2.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Determination
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {determinations.map((item) => (
              <tr
                key={`${item.merger_id}-${item.determination_date}-${item.determination_type}`}
                className="relative border-l-[3px] border-transparent hover:border-primary hover:bg-primary/[0.04] transition-all"
              >
                <td className="px-5 sm:px-6 py-3 text-sm text-gray-900">
                  <div className="flex items-center gap-2">
                    <Link
                      to={`/mergers/${item.merger_id}`}
                      className="text-primary hover:text-primary-dark transition-colors after:absolute after:inset-0"
                      aria-label={`View merger details for ${item.merger_name}`}
                    >
                      {item.merger_name}
                    </Link>
                    {isNewItem(item.merger_id) && <NewBadge />}
                    {item.is_waiver && <WaiverBadge compact />}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{formatDate(item.determination_date)}</div>
                </td>
                <td className="px-5 sm:px-6 py-3 whitespace-nowrap text-sm">
                  <DeterminationIcon determination={item.determination} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default RecentDeterminationsTable;
