import { useMemo } from 'react';
import { formatWeekday, formatDateRange, getCalendarDaysUntil } from '../utils/dates';
import {
  getRecentEventType,
  isRecentEventShown,
  recentEventRank,
} from '../constants/recentEventTypes';
import EventDayTimeline from './EventDayTimeline';

// The backward-looking twin of UpcomingEventsTimeline, drawn by the same
// EventDayTimeline: what has happened on the register over the last two weeks
// (recent-events.json), newest day first. The last week is broken out day by
// day; anything older is bundled into one trailing "Earlier" entry, as the
// upcoming timeline bundles its "Later". Which event types appear is set in
// constants/recentEventTypes.js.

const GROUP_COLLAPSE_THRESHOLD = 3;
const EARLIER_GROUP_COLLAPSE_THRESHOLD = 2;
const EARLIER_KEY = 'earlier';

// The last two days carry the primary node; older days fade, the way the
// upcoming timeline warms as a deadline nears.
const FRESH_URGENCY = { dot: 'bg-primary', text: 'text-gray-900' };
const OLDER_URGENCY = { dot: 'bg-gray-300', text: 'text-gray-900' };

function relativeLabel(daysAgo) {
  if (daysAgo <= 0) return 'Today';
  if (daysAgo === 1) return 'Yesterday';
  return `${daysAgo} days ago`;
}

// Within a day: most significant type first, then by matter so the order is
// stable.
function compareWithinDay(a, b) {
  const rankDelta = recentEventRank(a.type) - recentEventRank(b.type);
  if (rankDelta !== 0) return rankDelta;
  return a.merger_name.localeCompare(b.merger_name);
}

// After the chip: the matter, then on a line of its own the register's title
// for the event, which names the document or says what changed (its own line
// because it is often long enough to wrap anyway).
function renderDetail(event) {
  return (
    <>
      <span>{event.merger_id}</span>
      <span className="basis-full truncate">{event.title}</span>
    </>
  );
}

const eventKey = (event) => `${event.merger_id}-${event.date}-${event.type}-${event.title}`;

const groupLabel = (group, eventType) => `${group.events.length} ${eventType.plural}`;

function RecentEventsTimeline({ events }) {
  const days = useMemo(() => {
    const byDay = new Map();
    (events || [])
      .filter(isRecentEventShown)
      .map((event) => ({ ...event, day: event.date.slice(0, 10) }))
      .sort((a, b) => {
        const dayDelta = b.day.localeCompare(a.day);
        return dayDelta !== 0 ? dayDelta : compareWithinDay(a, b);
      })
      .forEach((event) => {
        const daysAgo = -(getCalendarDaysUntil(event.day) ?? 0);
        const isEarlier = daysAgo > 6;
        const key = isEarlier ? EARLIER_KEY : event.day;
        if (!byDay.has(key)) {
          byDay.set(
            key,
            isEarlier
              ? { key, earlier: true, events: [], rangeStart: event.day, rangeEnd: event.day }
              : { key, date: event.day, daysAgo, events: [] }
          );
        }
        const bucket = byDay.get(key);
        bucket.events.push(event);
        // Newest first, so each later event pushes the range's start back.
        if (isEarlier) bucket.rangeStart = event.day;
      });
    // The earlier bundle reads as one entry, so it is sorted by type alone.
    const earlier = byDay.get(EARLIER_KEY);
    if (earlier) earlier.events.sort(compareWithinDay);

    return [...byDay.values()].map((day) =>
      day.earlier
        ? {
            ...day,
            label: 'Earlier',
            sublabel: formatDateRange(day.rangeStart, day.rangeEnd),
            urgency: OLDER_URGENCY,
            collapseThreshold: EARLIER_GROUP_COLLAPSE_THRESHOLD,
          }
        : {
            ...day,
            label: relativeLabel(day.daysAgo),
            sublabel: formatWeekday(day.date),
            urgency: day.daysAgo <= 1 ? FRESH_URGENCY : OLDER_URGENCY,
            collapseThreshold: GROUP_COLLAPSE_THRESHOLD,
          }
    );
  }, [events]);

  if (days.length === 0) return null;

  return (
    <EventDayTimeline
      headingId="recent-events-heading"
      heading="Recent events"
      days={days}
      getEventType={getRecentEventType}
      groupLabel={groupLabel}
      renderDetail={renderDetail}
      eventKey={eventKey}
    />
  );
}

export default RecentEventsTimeline;
