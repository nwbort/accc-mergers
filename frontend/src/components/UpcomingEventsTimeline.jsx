import { useMemo } from 'react';
import {
  FaRegComments,
  FaGavel,
  FaTriangleExclamation,
  FaScaleBalanced,
} from 'react-icons/fa6';
import {
  formatWeekday,
  formatDateRange,
  getCalendarDaysUntil,
  isEventOngoing,
  australianToday,
  toDateString,
} from '../utils/dates';
import { PHASES, isPublicBenefitStage } from '../constants/mergerStatus';
import EmptyStateCard from './EmptyStateCard';
import EventDayTimeline from './EventDayTimeline';

// A day with this many or more events of the same type collapses into a
// single "N Consultations due" summary row, expandable on click/tap, so a
// busy day doesn't push everything else off screen. The combined "Later"
// entry already bundles a whole week, so it collapses a type as soon as
// there's more than one — otherwise it tends to be the longest, least
// scannable entry in the list.
const GROUP_COLLAPSE_THRESHOLD = 3;
const LATER_GROUP_COLLAPSE_THRESHOLD = 2;

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
    tile: 'bg-amber-50 text-amber-700',
    chip: 'bg-amber-50 text-amber-700 border-amber-200/60',
  },
  public_benefit_assessment: {
    label: 'Public benefit assessment',
    Icon: FaScaleBalanced,
    tile: 'bg-teal-50 text-teal-700',
    chip: 'bg-teal-50 text-teal-700 border-teal-200/60',
  },
  public_benefit_response_due: {
    label: 'Public benefit responses',
    Icon: FaRegComments,
    tile: 'bg-teal-50 text-teal-700',
    chip: 'bg-teal-50 text-teal-700 border-teal-200/60',
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
  // The other review of an ACCC decision, styled as its peer.
  federal_court_hearing: {
    label: 'Federal Court hearing',
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
// first: the later the phase the higher it ranks (public benefit, then Phase
// 2, then Phase 1); within a phase a tribunal or court hearing outranks a
// determination, which ranks above concerns notices, which rank above
// consultations; ties fall back to the merger name so the order is stable.
const EVENT_TYPE_ORDER = {
  tribunal_hearing: 0,
  federal_court_hearing: 0,
  determination_due: 1,
  public_benefit_assessment: 2,
  notice_of_competition_concerns: 2,
  public_benefit_response_due: 3,
  consultation_due: 3,
};

// The later the phase, the more is riding on it: a public benefit
// determination is the last word before the Tribunal.
const phaseRank = (stage) => {
  if (isPublicBenefitStage(stage)) return 0;
  return stage && stage.includes(PHASES.PHASE_2) ? 1 : 2;
};

function compareWithinDay(a, b) {
  const phaseDelta = phaseRank(a.stage) - phaseRank(b.stage);
  if (phaseDelta !== 0) return phaseDelta;

  const typeDelta =
    (EVENT_TYPE_ORDER[a.type] ?? 99) - (EVENT_TYPE_ORDER[b.type] ?? 99);
  if (typeDelta !== 0) return typeDelta;

  return a.merger_name.localeCompare(b.merger_name);
}

// Urgency drives the day marker: due today reads red, the next few days amber,
// anything further out sits in the calm primary green.
function getUrgency(daysRemaining) {
  if (daysRemaining === null || daysRemaining <= 0) {
    return { dot: 'bg-red-500', ring: 'ring-red-100', text: 'text-red-600' };
  }
  if (daysRemaining <= 3) {
    return { dot: 'bg-amber-500', ring: 'ring-amber-100', text: 'text-amber-700' };
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

// The calendar day (YYYY-MM-DD) an event is listed under. A multi-day event
// already under way (a Tribunal hearing part-way through its run) is listed
// under today, so it reads as happening now rather than slipping into the past
// after its first day.
function listedDay(event) {
  if (isEventOngoing(event)) return toDateString(australianToday());
  return event.date.slice(0, 10);
}

// How a multi-day event's span reads beside its chip: "Ongoing until 19 Nov"
// once it has begun, "9 Nov – 19 Nov" before then.
function spanLabel(event) {
  if (!event.end_date) return null;
  if (isEventOngoing(event)) {
    return `Ongoing until ${formatDateRange(event.end_date, event.end_date)}`;
  }
  return formatDateRange(event.date, event.end_date);
}

// The meta line after the chip: a multi-day event's span, then the matter.
function renderDetail(event) {
  const span = spanLabel(event);
  return (
    <>
      {span && <span className="font-medium text-gray-700">{span}</span>}
      <span>{event.merger_id}</span>
      <span aria-hidden="true">·</span>
      <span className="truncate">{event.stage}</span>
    </>
  );
}

const eventKey = (event) => `${event.merger_id}-${event.date}-${event.type}`;

const groupLabel = (group, eventType) =>
  `${group.events.length} ${eventType.label.toLowerCase()}s due`;

function UpcomingEventsTimeline({ events }) {
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
        const dayDelta = listedDay(a).localeCompare(listedDay(b));
        return dayDelta !== 0 ? dayDelta : compareWithinDay(a, b);
      })
      .forEach((event) => {
        const day = listedDay(event);
        const daysRemaining = getCalendarDaysUntil(day);
        const isLater = daysRemaining !== null && daysRemaining > 7;
        const key = isLater ? LATER_KEY : day;
        if (!byDay.has(key)) {
          byDay.set(
            key,
            isLater
              ? { key, later: true, events: [], rangeStart: day, rangeEnd: day }
              : { key, date: day, events: [] }
          );
        }
        const bucket = byDay.get(key);
        bucket.events.push(event);
        // Events are still date-sorted at this point, so the running range
        // just tracks the first and most recent later event seen.
        if (isLater) bucket.rangeEnd = day;
      });
    // The later bucket's events were sorted chronologically above; re-sort by
    // type/phase/name only, since it's presented as one combined entry rather
    // than day-by-day.
    const later = byDay.get(LATER_KEY);
    if (later) later.events.sort(compareWithinDay);
    return [...byDay.values()].map((day) => {
      if (day.later) {
        return {
          ...day,
          label: 'Later',
          sublabel: formatDateRange(day.rangeStart, day.rangeEnd),
          urgency: LATER_URGENCY,
          collapseThreshold: LATER_GROUP_COLLAPSE_THRESHOLD,
        };
      }
      const daysRemaining = getCalendarDaysUntil(day.date);
      return {
        ...day,
        label: relativeLabel(daysRemaining),
        sublabel: formatWeekday(day.date),
        urgency: getUrgency(daysRemaining),
        collapseThreshold: GROUP_COLLAPSE_THRESHOLD,
      };
    });
  }, [events]);

  if (days.length === 0) {
    return <EmptyStateCard heading="Upcoming events" message="No upcoming events." />;
  }

  return (
    <EventDayTimeline
      headingId="upcoming-events-heading"
      heading="Upcoming events"
      days={days}
      getEventType={getEventType}
      groupLabel={groupLabel}
      renderDetail={renderDetail}
      eventKey={eventKey}
    />
  );
}

export default UpcomingEventsTimeline;
