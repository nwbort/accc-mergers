import { Link } from 'react-router-dom';
import { formatDate } from '../utils/dates';
import { isNewItem } from '../utils/lastVisit';
import NewBadge from './NewBadge';
import StatusBadge from './StatusBadge';
import WaiverBadge from './WaiverBadge';

function RecentDeterminationsTable({ determinations }) {
  if (!determinations || determinations.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Recent determinations
        </h2>
        <p className="text-gray-500 text-sm">No recent determinations.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
      <div className="px-5 sm:px-6 py-4 border-b border-gray-50">
        <h2 className="text-lg font-semibold text-gray-900">
          Recent determinations
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-100">
          <thead>
            <tr className="bg-gray-50/80">
              <th
                scope="col"
                className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Merger
              </th>
              <th
                scope="col"
                className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Determination
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {determinations.map((item) => (
              <tr
                key={`${item.merger_id}-${item.determination_date}-${item.determination_type}`}
                className="relative hover:bg-gray-100/70 transition-colors"
              >
                <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
                  <div className="flex items-start gap-2">
                    <Link
                      to={`/mergers/${item.merger_id}`}
                      className="text-primary hover:text-primary-dark transition-colors after:absolute after:inset-0"
                      aria-label={`View merger details for ${item.merger_name}`}
                    >
                      {item.merger_name}
                    </Link>
                    {isNewItem(item.merger_id) && (
                      <NewBadge />
                    )}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5 flex items-center gap-2">
                    <span>{item.merger_id}</span>
                    {item.is_waiver && <WaiverBadge />}
                  </div>
                </td>
                <td className="px-5 sm:px-6 py-4 whitespace-nowrap text-sm">
                  <StatusBadge determination={item.determination} />
                  <div className="text-xs text-gray-400 mt-1 pl-2.5">
                    {formatDate(item.determination_date)}
                  </div>
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
