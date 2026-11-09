import { useState } from 'react';
import { Link } from 'react-router';
import { FaChevronDown } from 'react-icons/fa6';
import { mergerPath } from '../utils/slug';
import { CARD } from '../utils/classNames';

// The day-by-day event timeline the dashboard draws twice: forwards for
// upcoming deadlines (UpcomingEventsTimeline) and backwards for what has
// just happened on the register (RecentEventsTimeline). Each caller sorts
// its events into days and says how a day and an event type read; the rail,
// rows and same-type collapsing live here so the two stay identical.
//
// `days`: [{ key, label, sublabel, urgency: { dot, text }, events,
//            collapseThreshold }] in display order, each day's events
//            already sorted.
// `getEventType(type)`: { label, Icon, tile, chip }.
// `groupLabel(group, eventType)`: the collapsed row's text, e.g.
//            "4 consultations due".
// `renderDetail(event)`: optional extra items for the row's meta line,
//            after the chip.
// `eventKey(event)`: a key unique within the timeline.

// Split a day's already-sorted events into runs of consecutive same-type
// events. Callers sort by type within a day, so a type can appear in more
// than one run on a day only when another type sits between them.
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

function EventRow({ event, eventType, detail }) {
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
          {detail}
        </div>
      </div>
    </Link>
  );
}

function EventGroupSummary({ label, eventType, expanded, onToggle, panelId }) {
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
      <div className="min-w-0 flex-1 text-sm font-semibold text-gray-900">{label}</div>
      <FaChevronDown
        className={`h-3.5 w-3.5 flex-none text-gray-500 transition-transform ${expanded ? 'rotate-180' : ''}`}
        aria-hidden="true"
      />
    </button>
  );
}

function EventDayTimeline({
  headingId,
  heading,
  days,
  getEventType,
  groupLabel,
  renderDetail,
  eventKey,
}) {
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

  const renderRow = (event) => (
    <li key={eventKey(event)}>
      <EventRow
        event={event}
        eventType={getEventType(event.type)}
        detail={renderDetail ? renderDetail(event) : null}
      />
    </li>
  );

  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="text-lg font-semibold text-gray-900 mb-4">
        {heading}
      </h2>
      <div className={`${CARD} overflow-hidden`}>
        <ol className="px-5 sm:px-6 py-5">
          {days.map((day, dayIndex) => {
            const isLast = dayIndex === days.length - 1;
            return (
              <li key={day.key} className="relative flex gap-3 sm:gap-4">
                {/* Timeline rail: a node per day, joined by a line that stops
                    at the final day. */}
                <div className="relative flex w-3 flex-none justify-center">
                  {!isLast && (
                    <span
                      className="absolute top-2 bottom-0 w-px bg-gray-200"
                      aria-hidden="true"
                    />
                  )}
                  <span
                    className={`relative z-10 mt-1 h-3 w-3 rounded-full ring-4 ring-white ${day.urgency.dot}`}
                    aria-hidden="true"
                  />
                </div>

                <div className={`min-w-0 flex-1 ${isLast ? '' : 'pb-6'}`}>
                  <div className="flex items-baseline gap-2">
                    <h3 className={`text-sm font-semibold ${day.urgency.text}`}>{day.label}</h3>
                    <span className="text-xs text-gray-500">{day.sublabel}</span>
                  </div>

                  <ul className="mt-1.5 space-y-1">
                    {groupByType(day.events).flatMap((group) => {
                      // A handful of same-type events on one day collapse
                      // into a single summary row so a busy day doesn't
                      // crowd out everything else on the timeline.
                      if (group.events.length < day.collapseThreshold) {
                        return group.events.map(renderRow);
                      }

                      const eventType = getEventType(group.type);
                      const groupKey = `${day.key}-${group.type}`;
                      const panelId = `${headingId}-${groupKey}`;
                      const expanded = expandedGroups.has(groupKey);
                      return [
                        <li key={groupKey}>
                          <EventGroupSummary
                            label={groupLabel(group, eventType)}
                            eventType={eventType}
                            expanded={expanded}
                            onToggle={() => toggleGroup(groupKey)}
                            panelId={panelId}
                          />
                        </li>,
                        ...(expanded
                          ? [
                              <li key={panelId}>
                                <ul id={panelId} className="space-y-1 pl-4">
                                  {group.events.map(renderRow)}
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

export default EventDayTimeline;
