import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  FaRegComments,
  FaGavel,
  FaTriangleExclamation,
  FaScaleBalanced,
  FaChevronDown,
} from 'react-icons/fa6';
import { mergerPath } from '../utils/slug';
import { formatWeekday, formatDateRange, getCalendarDaysUntil } from '../utils/dates';
import { PHASES } from '../constants/mergerStatus';
import { CARD } from '../utils/classNames';
import EmptyStateCard from './EmptyStateCard';

// A day with this many or more events of the same type collapses into a
// single "N Consultations due" summary row, expandable on click/tap, so a
// busy day doesn't push everything else off screen.
const GROUP_COLLAPSE_THRESHOLD = 3;

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
  tribunal_hearing: {
    label: 'Tribunal hearing',
    Icon: FaScaleBalanced,
    tile: 'bg-rose-50 text-rose-600',
    chip: 'bg-rose-50 text-rose-700 border-rose-200/60',
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
// first: a tribunal hearing outranks a determination, which ranks above
// concerns notices, which rank above consultations; Phase 2 outranks Phase 1;
// ties fall back to the merger name so the order is stable.
const EVENT_TYPE_ORDER = {
  tribunal_hearing: 0,
  determination_due: 1,
  notice_of_competition_concerns: 2,
  consultation_due: 3,
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

// Everything more than a week out is bundled into a single trailing "Later"
// entry rather than one row per day, so the timeline doesn't stretch across
// two weeks of individual days. It always reads as calm/far-off.
const LATER_URGENCY = { dot: 'bg-primary', text: 'text-gray-900' };
const LATER_KEY = 'later';

// Split a day's already-sorted events into runs of consecutive same-type
// events. compareWithinDay sorts by type first, so each type appears in at
// most one run per day.
function groupByType(events) {
  const groups = [];
  events.forEach((event) => {
    const current = groups[groups.length - 1];
    if (current && current.type === event.type) {
      current.events.push(event);
    } else {
      groups.push({ type: event.type, events: [event] });
    }
  });
  return groups;
}

function EventRow({ event }) {
  const eventType = getEventType(event.type);
  const { Icon } = eventType;
  return (
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
  );
}

function EventGroupSummary({ group, expanded, onToggle, panelId }) {
  const eventType = getEventType(group.type);
  const { Icon } = eventType;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={expanded}
      aria-controls={panelId}
      className="flex w-full items-center gap-3 rounded-xl -mx-2 px-2 py-2 text-left transition-colors hover:bg-gray-50"
    >
      <span
        className={`flex h-8 w-8 flex-none items-center justify-center rounded-lg ${eventType.tile}`}
        aria-hidden="true"
      >
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0 flex-1 text-sm font-semibold text-gray-900">
        {group.events.length} {eventType.label.toLowerCase()}s due
      </div>
      <FaChevronDown
        className={`h-3.5 w-3.5 flex-none text-gray-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
        aria-hidden="true"
      />
    </button>
  );
}

function UpcomingEventsTimeline({ events }) {
  const [expandedGroups, setExpandedGroups] = useState(() => new Set());

  const toggleGroup = (key) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  // Group events into one entry per calendar day for the coming week, ordered
  // earliest first (the date portion, YYYY-MM-DD, is a stable key because
  // every event is stamped at the same UTC noon time). Anything more than a
  // week out is bundled into a single trailing "later" entry instead of one
  // row per day.
  const days = useMemo(() => {
    if (!events) return [];
    const byDay = new Map();
    [...events]
      .sort((a, b) => {
        const dayDelta = a.date.slice(0, 10).localeCompare(b.date.slice(0, 10));
        return dayDelta !== 0 ? dayDelta : compareWithinDay(a, b);
      })
      .forEach((event) => {
        const daysRemaining = getCalendarDaysUntil(event.date);
        const isLater = daysRemaining !== null && daysRemaining > 7;
        const key = isLater ? LATER_KEY : event.date.slice(0, 10);
        if (!byDay.has(key)) {
          byDay.set(
            key,
            isLater
              ? { key, later: true, events: [], rangeStart: event.date, rangeEnd: event.date }
              : { key, date: event.date, events: [] }
          );
        }
        const bucket = byDay.get(key);
        bucket.events.push(event);
        // Events are still date-sorted at this point, so the running range
        // just tracks the first and most recent later event seen.
        if (isLater) bucket.rangeEnd = event.date;
      });
    // The later bucket's events were sorted chronologically above; re-sort by
    // type/phase/name only, since it's presented as one combined entry rather
    // than day-by-day.
    const later = byDay.get(LATER_KEY);
    if (later) later.events.sort(compareWithinDay);
    return [...byDay.values()];
  }, [events]);

  if (days.length === 0) {
    return <EmptyStateCard heading="Upcoming events" message="No upcoming events." />;
  }

  return (
    <section aria-labelledby="upcoming-events-heading">
      <h2
        id="upcoming-events-heading"
        className="text-lg font-semibold text-gray-900 mb-4"
      >
        Upcoming events
      </h2>
      <div className={`${CARD} overflow-hidden`}>
      <ol className="px-5 sm:px-6 py-5">
        {days.map((day, dayIndex) => {
          const daysRemaining = day.later ? null : getCalendarDaysUntil(day.date);
          const urgency = day.later ? LATER_URGENCY : getUrgency(daysRemaining);
          const isLast = dayIndex === days.length - 1;
          const dayKey = day.key;

          return (
            <li key={dayKey} className="relative flex gap-3 sm:gap-4">
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
                  <h3 className={`text-sm font-semibold ${urgency.text}`}>
                    {day.later ? 'Later' : relativeLabel(daysRemaining)}
                  </h3>
                  <span className="text-xs text-gray-500">
                    {day.later ? formatDateRange(day.rangeStart, day.rangeEnd) : formatWeekday(day.date)}
                  </span>
                </div>

                <ul className="mt-1.5 space-y-1">
                  {groupByType(day.events).flatMap((group) => {
                    // A handful of same-type events on one day collapse into
                    // a single summary row so a busy day doesn't crowd out
                    // everything else on the timeline.
                    if (group.events.length < GROUP_COLLAPSE_THRESHOLD) {
                      return group.events.map((event) => (
                        <li key={`${event.merger_id}-${event.date}-${event.type}`}>
                          <EventRow event={event} />
                        </li>
                      ));
                    }

                    const groupKey = `${dayKey}-${group.type}`;
                    const panelId = `events-${groupKey}`;
                    const expanded = expandedGroups.has(groupKey);
                    return [
                      <li key={groupKey}>
                        <EventGroupSummary
                          group={group}
                          expanded={expanded}
                          onToggle={() => toggleGroup(groupKey)}
                          panelId={panelId}
                        />
                      </li>,
                      ...(expanded
                        ? [
                            <li key={panelId}>
                              <ul id={panelId} className="space-y-1 pl-4">
                                {group.events.map((event) => (
                                  <li key={`${event.merger_id}-${event.date}-${event.type}`}>
                                    <EventRow event={event} />
                                  </li>
                                ))}
                              </ul>
                            </li>,
                          ]
                        : []),
                    ];
                  })}
                </ul>
              </div>
            </li>
          );
        })}
      </ol>
      </div>
    </section>
  );
}

export default UpcomingEventsTimeline;
