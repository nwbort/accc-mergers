import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { FaRegComments, FaGavel, FaTriangleExclamation } from 'react-icons/fa6';
import { mergerPath } from '../utils/slug';
import { formatWeekday, getCalendarDaysUntil } from '../utils/dates';
import { PHASES } from '../constants/mergerStatus';

// Each event type carries its own accent (icon tile + chip) so the kind of
// deadline is recognisable at a glance, independent of the urgency colouring
// that drives the day markers. Full class strings keep Tailwind's scanner happy.
const EVENT_TYPES = {
  consultation_due: {
    label: 'Consultation',
    Icon: FaRegComments,
    tile: 'bg-blue-50 text-blue-600',
    chip: 'bg-blue-50 text-blue-700 border-blue-200/60',
  },
  notice_of_competition_concerns: {
    label: 'Concerns notice',
    Icon: FaTriangleExclamation,
    tile: 'bg-amber-50 text-amber-600',
    chip: 'bg-amber-50 text-amber-700 border-amber-200/60',
  },
  determination_due: {
    label: 'Determination',
    Icon: FaGavel,
    tile: 'bg-purple-50 text-purple-600',
    chip: 'bg-purple-50 text-purple-700 border-purple-200/60',
  },
};

const DEFAULT_EVENT_TYPE = {
  label: 'Event',
  Icon: FaGavel,
  tile: 'bg-gray-100 text-gray-600',
  chip: 'bg-gray-50 text-gray-700 border-gray-200/60',
};

const getEventType = (type) => EVENT_TYPES[type] || DEFAULT_EVENT_TYPE;

// Within a single calendar day, surface the most consequential deadlines
// first: determinations rank above concerns notices, which rank above
// consultations; Phase 2 outranks Phase 1; ties fall back to the merger name
// so the order is stable.
const EVENT_TYPE_ORDER = {
  determination_due: 0,
  notice_of_competition_concerns: 1,
  consultation_due: 2,
};

const phaseRank = (stage) => (stage && stage.includes(PHASES.PHASE_2) ? 0 : 1);

function compareWithinDay(a, b) {
  const typeDelta =
    (EVENT_TYPE_ORDER[a.type] ?? 99) - (EVENT_TYPE_ORDER[b.type] ?? 99);
  if (typeDelta !== 0) return typeDelta;

  const phaseDelta = phaseRank(a.stage) - phaseRank(b.stage);
  if (phaseDelta !== 0) return phaseDelta;

  return a.merger_name.localeCompare(b.merger_name);
}

// Urgency drives the day marker: due today reads red, the next few days amber,
// anything further out sits in the calm primary green.
function getUrgency(daysRemaining) {
  if (daysRemaining === null || daysRemaining <= 0) {
    return { dot: 'bg-red-500', ring: 'ring-red-100', text: 'text-red-600' };
  }
  if (daysRemaining <= 3) {
    return { dot: 'bg-amber-500', ring: 'ring-amber-100', text: 'text-amber-600' };
  }
  return { dot: 'bg-primary', ring: 'ring-primary/10', text: 'text-gray-900' };
}

function relativeLabel(daysRemaining) {
  if (daysRemaining === null || daysRemaining <= 0) return 'Today';
  if (daysRemaining === 1) return 'Tomorrow';
  return `In ${daysRemaining} days`;
}

function EmptyCard() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Upcoming events</h2>
      <p className="text-gray-500 text-sm">No upcoming events.</p>
    </div>
  );
}

function UpcomingEventsTimeline({ events }) {
  // Group events into one entry per calendar day, ordered earliest first. The
  // date portion (YYYY-MM-DD) is a stable key because every event is stamped at
  // the same UTC noon time.
  const days = useMemo(() => {
    if (!events) return [];
    const byDay = new Map();
    [...events]
      .sort((a, b) => {
        const dayDelta = a.date.slice(0, 10).localeCompare(b.date.slice(0, 10));
        return dayDelta !== 0 ? dayDelta : compareWithinDay(a, b);
      })
      .forEach((event) => {
        const key = event.date.slice(0, 10);
        if (!byDay.has(key)) byDay.set(key, { date: event.date, events: [] });
        byDay.get(key).events.push(event);
      });
    return [...byDay.values()];
  }, [events]);

  if (days.length === 0) return <EmptyCard />;

  return (
    <section
      aria-labelledby="upcoming-events-heading"
      className="bg-white rounded-2xl border border-gray-100 shadow-card overflow-hidden"
    >
      <div className="px-5 sm:px-6 py-4 border-b border-gray-50">
        <h2 id="upcoming-events-heading" className="text-lg font-semibold text-gray-900">
          Upcoming events
        </h2>
      </div>

      <ol className="px-5 sm:px-6 py-5">
        {days.map((day, dayIndex) => {
          const daysRemaining = getCalendarDaysUntil(day.date);
          const urgency = getUrgency(daysRemaining);
          const isLast = dayIndex === days.length - 1;

          return (
            <li key={day.date.slice(0, 10)} className="relative flex gap-3 sm:gap-4">
              {/* Timeline rail: a node per day, joined by a line that stops at
                  the final day. */}
              <div className="relative flex w-3 flex-none justify-center">
                {!isLast && (
                  <span
                    className="absolute top-2 bottom-0 w-px bg-gray-200"
                    aria-hidden="true"
                  />
                )}
                <span
                  className={`relative z-10 mt-1 h-3 w-3 rounded-full ring-4 ring-white ${urgency.dot}`}
                  aria-hidden="true"
                />
              </div>

              {/* Day content */}
              <div className={`min-w-0 flex-1 ${isLast ? '' : 'pb-6'}`}>
                <div className="flex items-baseline gap-2">
                  <span className={`text-sm font-semibold ${urgency.text}`}>
                    {relativeLabel(daysRemaining)}
                  </span>
                  <span className="text-xs text-gray-400">{formatWeekday(day.date)}</span>
                </div>

                <ul className="mt-1.5 space-y-1">
                  {day.events.map((event) => {
                    const eventType = getEventType(event.type);
                    const { Icon } = eventType;
                    return (
                      <li key={`${event.merger_id}-${event.date}-${event.type}`}>
                        <Link
                          to={mergerPath(event.merger_id, event.merger_name)}
                          className="group relative flex items-center gap-3 rounded-xl -mx-2 px-2 py-2 transition-colors hover:bg-gray-50"
                          aria-label={`${eventType.label} for ${event.merger_name}`}
                        >
                          <span
                            className={`flex h-8 w-8 flex-none items-center justify-center rounded-lg ${eventType.tile}`}
                            aria-hidden="true"
                          >
                            <Icon className="h-3.5 w-3.5" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="truncate text-sm font-semibold text-gray-900 transition-colors group-hover:text-primary">
                              {event.merger_name}
                            </div>
                            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-500">
                              <span
                                className={`inline-flex items-center rounded-md border px-1.5 py-0.5 font-medium ${eventType.chip}`}
                              >
                                {eventType.label}
                              </span>
                              <span>{event.merger_id}</span>
                              <span aria-hidden="true">·</span>
                              <span className="truncate">{event.stage}</span>
                            </div>
                          </div>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

export default UpcomingEventsTimeline;
