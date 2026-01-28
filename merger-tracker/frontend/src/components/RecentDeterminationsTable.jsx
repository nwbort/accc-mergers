import { Link } from 'react-router-dom';
import { formatDate } from '../utils/dates';

function DeterminationBadge({ determination }) {
  const getStyle = () => {
    if (determination === 'Approved') {
      return 'bg-green-100 text-green-800';
    } else if (determination === 'Not approved') {
      return 'bg-red-100 text-red-800';
    } else if (determination === 'Referred to phase 2') {
      return 'bg-amber-100 text-amber-800';
    }
    return 'bg-gray-100 text-gray-800';
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStyle()}`}
      role="status"
      aria-label={`Determination: ${determination}`}
    >
      {determination}
    </span>
  );
}

function RecentDeterminationsTable({ determinations }) {
  if (!determinations || determinations.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Recent determinations
        </h2>
        <p className="text-gray-500 text-sm">No recent determinations.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-4 sm:px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">
          Recent determinations
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                scope="col"
                className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Date
              </th>
              <th
                scope="col"
                className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Merger
              </th>
              <th
                scope="col"
                className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Determination
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {determinations.map((item) => (
              <tr
                key={`${item.merger_id}-${item.determination_date}-${item.determination_type}`}
                className="relative hover:bg-gray-50"
              >
                <td className="px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                  {formatDate(item.determination_date)}
                </td>
                <td className="px-3 sm:px-6 py-4 text-sm text-gray-900">
                  <Link
                    to={`/mergers/${item.merger_id}`}
                    className="text-primary after:absolute after:inset-0"
                    aria-label={`View merger details for ${item.merger_name}`}
                  >
                    {item.merger_name}
                  </Link>
                  <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                    <span>{item.merger_id}</span>
                    {item.is_waiver && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                        Waiver
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-3 sm:px-6 py-4 whitespace-nowrap text-sm">
                  <DeterminationBadge determination={item.determination} />
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
