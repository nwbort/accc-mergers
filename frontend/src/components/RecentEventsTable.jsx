import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import { mergerPath } from '../utils/slug';
import { formatWeekday, getCalendarDaysUntil } from '../utils/dates';
import { CARD } from '../utils/classNames';
import { getRecentEventType, isRecentEventShown } from '../constants/recentEventTypes';
import ShowMoreDivider from './ShowMoreDivider';

// Rows shown before "Show more". Two weeks of register activity runs to ~100
// events, so the table opens on the latest handful.
const COLLAPSED_ROWS = 10;

function dayLabel(date) {
  const days = getCalendarDaysUntil(date);
  if (days === 0) return 'Today';
  if (days === -1) return 'Yesterday';
  return formatWeekday(date);
}

function EventChip({ eventType }) {
  const { Icon } = eventType;
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border px-1.5 py-0.5 text-xs font-medium ${eventType.chip}`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {eventType.label}
    </span>
  );
}

function EventRow({ event }) {
  const eventType = getRecentEventType(event.type);
  return (
    <tr className="align-top">
      <td className="whitespace-nowrap py-3 pr-3 text-xs font-medium text-gray-700">
        {dayLabel(event.date)}
      </td>
      <td className="hidden py-3 pr-3 sm:table-cell">
        <EventChip eventType={eventType} />
      </td>
      <td className="min-w-0 py-3">
        {/* On a phone the Event column is dropped and its chip leads the
            matter cell, so the matter name keeps the width. */}
        <div className="mb-1 sm:hidden">
          <EventChip eventType={eventType} />
        </div>
        <Link
          to={mergerPath(event.merger_id, event.merger_name)}
          className="text-sm font-semibold text-gray-900 hover:text-primary"
        >
          {event.merger_name}
        </Link>
        <div className="mt-0.5 text-xs text-gray-500">
          <span>{event.merger_id}</span>
          <span aria-hidden="true"> · </span>
          {event.url_gh ? (
            <a
              href={event.url_gh}
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-gray-300 underline-offset-2 hover:text-primary"
            >
              {event.title}
            </a>
          ) : (
            <span>{event.title}</span>
          )}
        </div>
      </td>
    </tr>
  );
}

// The backward-looking twin of UpcomingEventsTimeline: what happened on the
// register over the last two weeks (recent-events.json), newest first. Which
// event types appear is set in constants/recentEventTypes.js.
function RecentEventsTable({ events }) {
  const [expanded, setExpanded] = useState(false);
  const shown = useMemo(() => (events || []).filter(isRecentEventShown), [events]);

  if (shown.length === 0) return null;

  const rows = expanded ? shown : shown.slice(0, COLLAPSED_ROWS);
  return (
    <section aria-labelledby="recent-events-heading">
      <h2 id="recent-events-heading" className="text-lg font-semibold text-gray-900 mb-4">
        Recent events
      </h2>
      <div className={`${CARD} overflow-x-auto`}>
        <table className="w-full">
          <caption className="sr-only">Register events from the last two weeks, newest first</caption>
          <thead>
            <tr className="border-b border-gray-100 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
              <th scope="col" className="py-3 pl-5 pr-3 sm:pl-6">Date</th>
              <th scope="col" className="hidden py-3 pr-3 sm:table-cell">Event</th>
              <th scope="col" className="py-3 pr-5 sm:pr-6">Matter</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 [&_td:first-child]:pl-5 sm:[&_td:first-child]:pl-6 [&_td:last-child]:pr-5 sm:[&_td:last-child]:pr-6">
            {rows.map((event) => (
              <EventRow
                key={`${event.merger_id}-${event.date}-${event.type}-${event.title}`}
                event={event}
              />
            ))}
          </tbody>
        </table>
      </div>
      {shown.length > COLLAPSED_ROWS && (
        <ShowMoreDivider expanded={expanded} onToggle={() => setExpanded((v) => !v)} />
      )}
    </section>
  );
}

export default RecentEventsTable;
