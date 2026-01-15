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
      <div className="px-4 sm:px-3 sm:px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">
          Upcoming events
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {/* Combined column - mobile only */}
              <th
                scope="col"
                className="sm:hidden px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                <div>Date</div>
                <div>Event</div>
              </th>
              {/* Separate columns - desktop only */}
              <th
                scope="col"
                className="hidden sm:table-cell px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Date
              </th>
              <th
                scope="col"
                className="hidden sm:table-cell px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Event
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
                Days remaining
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {events.map((event, idx) => {
              const daysRemaining = getDaysRemaining(event.date);
              const businessDaysRemaining = getBusinessDaysRemaining(event.date);
              const isUrgent = daysRemaining !== null && daysRemaining <= 7;

              return (
                <tr
                  key={idx}
                  className="relative hover:bg-gray-50"
                >
                  {/* Combined cell - mobile only */}
                  <td className="sm:hidden px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <div className="pl-2.5">{formatDate(event.date)}</div>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium mt-1 ${
                        event.type === 'consultation_due'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-purple-100 text-purple-800'
                      }`}
                      role="status"
                      aria-label={`Event type: ${event.event_type_display.replace(/ due$/, '')}`}
                    >
                      {event.event_type_display.replace(/ due$/, '')}
                    </span>
                  </td>
                  {/* Separate cells - desktop only */}
                  <td className="hidden sm:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatDate(event.date)}
                  </td>
                  <td className="hidden sm:table-cell px-3 sm:px-6 py-4 whitespace-nowrap text-sm">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        event.type === 'consultation_due'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-purple-100 text-purple-800'
                      }`}
                      role="status"
                      aria-label={`Event type: ${event.event_type_display}`}
                    >
                      {event.event_type_display}
                    </span>
                  </td>
                  <td className="px-3 sm:px-6 py-4 text-sm text-gray-900">
                    <Link
                      to={`/mergers/${event.merger_id}`}
                      className="text-primary after:absolute after:inset-0"
                      aria-label={`View merger details for ${event.merger_name}`}
                    >
                      {event.merger_name}
                    </Link>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {event.merger_id} • {event.stage}
                    </div>
                  </td>
                  <td className="px-3 sm:px-6 py-4 text-sm">
                    {daysRemaining !== null && businessDaysRemaining !== null && (
                      <div>
                        <span
                          className={`font-medium ${
                            isUrgent ? 'text-red-700' : 'text-gray-900'
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
