import { Link } from 'react-router-dom';
import { formatDate, getDaysRemaining, getBusinessDaysRemaining } from '../utils/dates';

function UpcomingEventsTable({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Upcoming events
        </h2>
        <p className="text-gray-500 text-sm">No upcoming events in the next 60 days.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">
          Upcoming events
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Date
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Event Type
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Merger
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Days Remaining
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {events.map((event, idx) => {
              const daysRemaining = getDaysRemaining(event.date);
              const businessDaysRemaining = getBusinessDaysRemaining(event.date);
              const isUrgent = daysRemaining !== null && daysRemaining <= 7;

              return (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDate(event.date)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        event.type === 'consultation_due'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-purple-100 text-purple-800'
                      }`}
                    >
                      {event.event_type_display}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <Link
                      to={`/mergers/${event.merger_id}`}
                      className="text-primary hover:text-primary-dark"
                    >
                      {event.merger_name}
                    </Link>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {event.merger_id} • {event.stage}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {daysRemaining !== null && businessDaysRemaining !== null && (
                      <div>
                        <span
                          className={`font-medium ${
                            isUrgent ? 'text-red-600' : 'text-gray-900'
                          }`}
                        >
                          {daysRemaining === 0
                            ? 'Today'
                            : daysRemaining === 1
                            ? '1 day'
                            : `${daysRemaining} days`}
                        </span>
                        <div className="text-xs text-gray-500 mt-0.5">
                          {businessDaysRemaining === 0
                            ? 'Today'
                            : businessDaysRemaining === 1
                            ? '1 business day'
                            : `${businessDaysRemaining} business days`}
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default UpcomingEventsTable;
