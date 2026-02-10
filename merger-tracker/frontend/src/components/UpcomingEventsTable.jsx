import { Link } from 'react-router-dom';
import { formatDate, getDaysRemaining } from '../utils/dates';

function UpcomingEventsTable({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Upcoming events
        </h2>
        <p className="text-gray-500 text-sm">No upcoming events in the next 60 days.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden">
      <div className="px-5 sm:px-6 py-4 border-b border-gray-50">
        <h2 className="text-lg font-semibold text-gray-900">
          Upcoming events
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-100">
          <thead>
            <tr className="bg-gray-50/80">
              {/* Combined column - mobile only */}
              <th
                scope="col"
                className="sm:hidden px-5 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                <div>Date</div>
                <div>Event</div>
              </th>
              {/* Separate columns - desktop only */}
              <th
                scope="col"
                className="hidden sm:table-cell px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Date
              </th>
              <th
                scope="col"
                className="hidden sm:table-cell px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Event
              </th>
              <th
                scope="col"
                className="px-5 sm:px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Merger
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {events.map((event, idx) => {
              const daysRemaining = getDaysRemaining(event.date);
              const isUrgent = daysRemaining !== null && daysRemaining <= 3;

              return (
                <tr
                  key={`${event.merger_id}-${event.date}-${event.type}`}
                  className="relative hover:bg-gray-100/70 transition-colors"
                >
                  {/* Combined cell - mobile only */}
                  <td className="sm:hidden px-5 py-4 whitespace-nowrap text-sm">
                    <div className="pl-2.5">
                      <div className={`font-medium ${isUrgent ? 'text-red-700' : 'text-gray-900'}`}>
                        {daysRemaining === 0
                          ? 'Today'
                          : daysRemaining === 1
                          ? '1 day'
                          : `${daysRemaining} days`}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">{formatDate(event.date)}</div>
                    </div>
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-lg text-xs font-semibold mt-1 border ${
                        event.type === 'consultation_due'
                          ? 'bg-blue-50 text-blue-700 border-blue-200/60'
                          : 'bg-purple-50 text-purple-700 border-purple-200/60'
                      }`}
                      role="status"
                      aria-label={`Event type: ${event.event_type_display.replace(/ due$/, '')}`}
                    >
                      {event.event_type_display.replace(/ due$/, '').replace(/^Consultation responses$/, 'Consultation')}
                    </span>
                  </td>
                  {/* Separate cells - desktop only */}
                  <td className="hidden sm:table-cell px-5 sm:px-6 py-4 whitespace-nowrap text-sm">
                    <div className={`font-medium ${isUrgent ? 'text-red-700' : 'text-gray-900'}`}>
                      {daysRemaining === 0
                        ? 'Today'
                        : daysRemaining === 1
                        ? '1 day'
                        : `${daysRemaining} days`}
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">{formatDate(event.date)}</div>
                  </td>
                  <td className="hidden sm:table-cell px-5 sm:px-6 py-4 whitespace-nowrap text-sm">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-lg text-xs font-semibold border ${
                        event.type === 'consultation_due'
                          ? 'bg-blue-50 text-blue-700 border-blue-200/60'
                          : 'bg-purple-50 text-purple-700 border-purple-200/60'
                      }`}
                      role="status"
                      aria-label={`Event type: ${event.event_type_display}`}
                    >
                      {event.event_type_display}
                    </span>
                  </td>
                  <td className="px-5 sm:px-6 py-4 text-sm text-gray-900">
                    <Link
                      to={`/mergers/${event.merger_id}`}
                      className="text-primary hover:text-primary-dark transition-colors after:absolute after:inset-0"
                      aria-label={`View merger details for ${event.merger_name}`}
                    >
                      {event.merger_name}
                    </Link>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {event.merger_id} · {event.stage}
                    </div>
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
