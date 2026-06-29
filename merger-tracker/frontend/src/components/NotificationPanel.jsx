import { useRef, useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { mergerPath, industryPath } from '../utils/slug';
import { FaBell, FaCheckCircle } from 'react-icons/fa';
import { useTracking } from '../context/TrackingContext';
import { formatDate, getDaysRemaining, isDatePast } from '../utils/dates';

function PanelEmptyState({ iconBg, iconColor, Icon, title, subtitle }) {
  return (
    <div className="px-5 py-10 text-center">
      <div className={`w-12 h-12 rounded-2xl ${iconBg} flex items-center justify-center mx-auto mb-3`}>
        <Icon className={`h-6 w-6 ${iconColor}`} aria-hidden="true" />
      </div>
      <p className="text-sm font-medium text-gray-500 mb-1">{title}</p>
      {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
    </div>
  );
}

function MergerEventGroup({ group, onClose, wasUnseenOnOpen }) {
  const [showPastEvents, setShowPastEvents] = useState(false);

  // Separate past and future events
  const pastEvents = group.events.filter((e) => isDatePast(e.date));
  const futureEvents = group.events.filter((e) => !isDatePast(e.date));

  // Past events that were unseen when the panel opened are always shown
  // so notified events can't hide behind the collapse.
  const unseenPastEvents = pastEvents.filter((e) => wasUnseenOnOpen(e));
  const seenPastEvents = pastEvents.filter((e) => !wasUnseenOnOpen(e));

  // Sort all events by date descending (most recent/latest dates first)
  futureEvents.sort((a, b) => new Date(b.date) - new Date(a.date));
  unseenPastEvents.sort((a, b) => new Date(b.date) - new Date(a.date));
  seenPastEvents.sort((a, b) => new Date(b.date) - new Date(a.date));

  return (
    <div className="p-4">
      <Link
        to={mergerPath(group.merger_id, group.merger_name)}
        onClick={onClose}
        className="block hover:bg-gray-50/80 -mx-4 -mt-4 px-4 pt-4 pb-2 rounded-t-xl transition-colors"
      >
        <h3 className="text-sm font-medium text-gray-900 hover:text-primary transition-colors line-clamp-2">
          {group.merger_name}
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">{group.merger_id}</p>
      </Link>

      <ul className="mt-2 space-y-2">
        {/* Future/current events */}
        {futureEvents.map((event, idx) => {
          const daysRemaining = getDaysRemaining(event.date);
          const isUpcoming = event.type === 'consultation_due' || event.type === 'determination_due' || event.type === 'notice_of_competition_concerns';
          const isNew = wasUnseenOnOpen(event);

          return (
            <li
              key={`${event.merger_id}-${event.date}-future-${idx}`}
              className={`text-xs rounded-md ${
                isNew ? 'bg-emerald-50 ring-1 ring-emerald-200 px-2 py-1.5 -mx-1' : ''
              }`}
            >
              <div className="flex items-start gap-2">
                <span className={`mt-0.5 flex-shrink-0 w-2 h-2 rounded-full ${
                  isNew ? 'bg-emerald-500' : isUpcoming ? 'bg-amber-400' : 'bg-gray-300'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className={`truncate ${isNew ? 'text-gray-900 font-medium' : 'text-gray-700'}`}>
                    {event.display_title || event.event_type_display || event.title}
                    {isNew && (
                      <span className="ml-1.5 inline-block align-middle text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                        New
                      </span>
                    )}
                  </p>
                  <p className="text-gray-500">
                    {formatDate(event.date)}
                    {isUpcoming && daysRemaining > 0 && (
                      <span className="ml-1 text-amber-600 font-medium">
                        ({daysRemaining} day{daysRemaining !== 1 ? 's' : ''})
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </li>
          );
        })}

        {/* Unseen past events: always visible so notified events can't hide behind the collapse */}
        {unseenPastEvents.map((event, idx) => (
          <li
            key={`${event.merger_id}-${event.date}-past-new-${idx}`}
            className="text-xs rounded-md bg-emerald-50 ring-1 ring-emerald-200 px-2 py-1.5 -mx-1"
          >
            <div className="flex items-start gap-2">
              <span className="mt-0.5 flex-shrink-0 w-2 h-2 rounded-full bg-emerald-500" />
              <div className="flex-1 min-w-0">
                <p className="text-gray-900 font-medium truncate">
                  {event.display_title || event.event_type_display || event.title}
                  <span className="ml-1.5 inline-block align-middle text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                    New
                  </span>
                </p>
                <p className="text-gray-500">
                  {formatDate(event.date)}
                </p>
              </div>
            </div>
          </li>
        ))}

        {/* Seen past events collapsible */}
        {seenPastEvents.length > 0 && (
          <>
            <li className="text-xs">
              <button
                onClick={() => setShowPastEvents(!showPastEvents)}
                className="text-gray-500 hover:text-gray-700 hover:underline cursor-pointer pl-4 transition-colors"
              >
                {showPastEvents ? 'Hide' : 'Show'} {seenPastEvents.length} past event{seenPastEvents.length !== 1 ? 's' : ''}
              </button>
            </li>

            {showPastEvents && seenPastEvents.map((event, idx) => (
              <li
                key={`${event.merger_id}-${event.date}-past-${idx}`}
                className="text-xs"
              >
                <div className="flex items-start gap-2">
                  <span className="mt-0.5 flex-shrink-0 w-2 h-2 rounded-full bg-gray-300" />
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-500 truncate">
                      {event.display_title || event.event_type_display || event.title}
                    </p>
                    <p className="text-gray-500">
                      {formatDate(event.date)}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </>
        )}
      </ul>
    </div>
  );
}

function IndustryEventGroup({ group, onClose, wasUnseenOnOpen }) {
  const [showOlder, setShowOlder] = useState(false);

  // Industry-follow events are always dated when they happened (a filing or a
  // determination), so they're effectively all "past". Keep events that were
  // unseen when the panel opened pinned to the top; collapse the rest.
  const events = [...group.events].sort((a, b) => new Date(b.date) - new Date(a.date));
  const newEvents = events.filter((e) => wasUnseenOnOpen(e));
  const olderEvents = events.filter((e) => !wasUnseenOnOpen(e));

  const renderEvent = (event, idx, isNew) => (
    <li
      key={`${event.industry_code}-${event.merger_id}-${event.date}-${idx}`}
      className={`text-xs rounded-md ${
        isNew ? 'bg-emerald-50 ring-1 ring-emerald-200 px-2 py-1.5 -mx-1' : ''
      }`}
    >
      <Link
        to={mergerPath(event.merger_id, event.merger_name)}
        onClick={onClose}
        className="flex items-start gap-2 group/event"
      >
        <span className={`mt-0.5 flex-shrink-0 w-2 h-2 rounded-full ${
          isNew
            ? 'bg-emerald-500'
            : event.type === 'industry_new_merger' ? 'bg-primary/40' : 'bg-gray-300'
        }`} />
        <div className="flex-1 min-w-0">
          <p className={`truncate group-hover/event:text-primary transition-colors ${isNew ? 'text-gray-900 font-medium' : 'text-gray-700'}`}>
            {event.merger_name}
          </p>
          <p className="text-gray-500">
            {event.display_title} · {formatDate(event.date)}
            {isNew && (
              <span className="ml-1.5 inline-block align-middle text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                New
              </span>
            )}
          </p>
        </div>
      </Link>
    </li>
  );

  return (
    <div className="p-4">
      <Link
        to={industryPath(group.industry_code, group.industry_name)}
        onClick={onClose}
        className="block hover:bg-gray-50/80 -mx-4 -mt-4 px-4 pt-4 pb-2 rounded-t-xl transition-colors"
      >
        <h3 className="text-sm font-medium text-gray-900 hover:text-primary transition-colors line-clamp-2">
          {group.industry_name}
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">Industry · {group.industry_code}</p>
      </Link>

      <ul className="mt-2 space-y-2">
        {newEvents.map((event, idx) => renderEvent(event, idx, true))}

        {olderEvents.length > 0 && (
          <>
            <li className="text-xs">
              <button
                onClick={() => setShowOlder(!showOlder)}
                className="text-gray-500 hover:text-gray-700 hover:underline cursor-pointer pl-4 transition-colors"
              >
                {showOlder ? 'Hide' : 'Show'} {olderEvents.length} earlier update{olderEvents.length !== 1 ? 's' : ''}
              </button>
            </li>
            {showOlder && olderEvents.map((event, idx) => renderEvent(event, idx, false))}
          </>
        )}
      </ul>
    </div>
  );
}

function NotificationPanel({ isOpen, onClose }) {
  const panelRef = useRef(null);
  const previouslyFocusedRef = useRef(null);
  const {
    trackedEvents,
    trackedMergerIds,
    trackedIndustries,
    trackedIndustryEvents,
    markEventsAsSeen,
    isEventSeen,
    getEventKey,
    loading,
  } = useTracking();

  // Snapshot which events were unseen when the panel opened, so the "new"
  // highlight persists for this viewing even after markEventsAsSeen runs.
  const [unseenOnOpen, setUnseenOnOpen] = useState(() => new Set());
  const wasUnseenOnOpen = useCallback(
    (event) => unseenOnOpen.has(getEventKey(event)),
    [unseenOnOpen, getEventKey]
  );

  // Restore focus to the trigger element when the panel closes
  useEffect(() => {
    if (isOpen) {
      previouslyFocusedRef.current = document.activeElement;
    } else if (previouslyFocusedRef.current) {
      previouslyFocusedRef.current.focus?.();
      previouslyFocusedRef.current = null;
    }
  }, [isOpen]);

  // Close panel when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (panelRef.current && !panelRef.current.contains(event.target)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  // Close on escape key
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  // Mark all events as seen when panel is opened
  // Only mark when transitioning to open, not on every trackedEvents change
  useEffect(() => {
    if (isOpen) {
      const allEvents = [...trackedEvents, ...trackedIndustryEvents];
      if (allEvents.length > 0) {
        // Snapshot unseen keys before marking them as seen so we can keep
        // highlighting them for the duration of this panel view.
        const snapshot = new Set(
          allEvents.filter((e) => !isEventSeen(e)).map(getEventKey)
        );
        setUnseenOnOpen(snapshot);
        markEventsAsSeen(allEvents);
      }
    } else {
      setUnseenOnOpen(new Set());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]); // Only depend on isOpen to mark events when panel first opens

  if (!isOpen) return null;

  // Group events by merger for better display
  const eventsByMerger = trackedEvents.reduce((acc, event) => {
    if (!acc[event.merger_id]) {
      acc[event.merger_id] = {
        merger_id: event.merger_id,
        merger_name: event.merger_name,
        events: [],
      };
    }
    acc[event.merger_id].events.push(event);
    return acc;
  }, {});

  // Sort merger groups:
  // 1. Mergers with unseen events first (most recent unseen event at top)
  // 2. Then by soonest upcoming event
  const mergerGroups = Object.values(eventsByMerger).sort((a, b) => {
    // Check for events that were unseen when the panel opened
    const aUnseenEvents = a.events.filter((e) => wasUnseenOnOpen(e));
    const bUnseenEvents = b.events.filter((e) => wasUnseenOnOpen(e));
    const aHasUnseen = aUnseenEvents.length > 0;
    const bHasUnseen = bUnseenEvents.length > 0;

    // Mergers with unseen events come first
    if (aHasUnseen && !bHasUnseen) return -1;
    if (!aHasUnseen && bHasUnseen) return 1;

    // If both have unseen events, sort by most recent unseen event
    if (aHasUnseen && bHasUnseen) {
      const aMostRecent = Math.max(...aUnseenEvents.map((e) => new Date(e.date).getTime()));
      const bMostRecent = Math.max(...bUnseenEvents.map((e) => new Date(e.date).getTime()));
      return bMostRecent - aMostRecent; // Most recent first
    }

    // Neither has unseen events - sort by soonest upcoming event
    const now = new Date();
    const aFutureEvents = a.events.filter((e) => new Date(e.date) >= now);
    const bFutureEvents = b.events.filter((e) => new Date(e.date) >= now);

    const aSoonest = aFutureEvents.length > 0
      ? Math.min(...aFutureEvents.map((e) => new Date(e.date).getTime()))
      : Infinity;
    const bSoonest = bFutureEvents.length > 0
      ? Math.min(...bFutureEvents.map((e) => new Date(e.date).getTime()))
      : Infinity;

    return aSoonest - bSoonest; // Soonest first
  });

  // Group industry-follow events by industry for display.
  const eventsByIndustry = trackedIndustryEvents.reduce((acc, event) => {
    if (!acc[event.industry_code]) {
      acc[event.industry_code] = {
        industry_code: event.industry_code,
        industry_name: event.industry_name,
        events: [],
      };
    }
    acc[event.industry_code].events.push(event);
    return acc;
  }, {});

  // Surface followed industries even when they have no events yet, so the user
  // sees what they're following. Sort: industries with unseen updates first
  // (most recent first), then by most recent activity.
  const industryGroups = trackedIndustries
    .map((ind) => eventsByIndustry[ind.code] || {
      industry_code: ind.code,
      industry_name: ind.name,
      events: [],
    })
    .sort((a, b) => {
      const aUnseen = a.events.filter((e) => wasUnseenOnOpen(e));
      const bUnseen = b.events.filter((e) => wasUnseenOnOpen(e));
      if (aUnseen.length > 0 && bUnseen.length === 0) return -1;
      if (aUnseen.length === 0 && bUnseen.length > 0) return 1;
      const aLatest = a.events.length ? Math.max(...a.events.map((e) => new Date(e.date).getTime())) : -Infinity;
      const bLatest = b.events.length ? Math.max(...b.events.map((e) => new Date(e.date).getTime())) : -Infinity;
      return bLatest - aLatest;
    });

  const nothingTracked = trackedMergerIds.length === 0 && trackedIndustries.length === 0;
  const noRecentActivity = trackedEvents.length === 0 && trackedIndustryEvents.length === 0;

  return (
    <div
      ref={panelRef}
      className="fixed left-1/2 -translate-x-1/2 top-16 sm:absolute sm:left-auto sm:translate-x-0 sm:right-0 sm:top-full sm:mt-2 w-[calc(100vw-1rem)] sm:w-96 bg-white/95 backdrop-blur-lg rounded-2xl shadow-elevated border border-gray-100 z-50 max-h-[70vh] sm:max-h-[80vh] overflow-hidden flex flex-col"
      role="dialog"
      aria-label="Notifications panel"
    >
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-gray-100 bg-gray-50/80 flex-shrink-0">
        <h2 className="text-sm font-semibold text-gray-900">
          Notifications
        </h2>
      </div>

      {/* Content */}
      <div className="overflow-y-auto flex-1">
        {nothingTracked ? (
          <PanelEmptyState
            iconBg="bg-gray-50"
            iconColor="text-gray-300"
            Icon={FaBell}
            title="Nothing tracked yet"
            subtitle="Track a merger, or follow an industry to hear about new filings and determinations"
          />
        ) : loading ? (
          <div className="px-5 py-10 text-center">
            <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-3"></div>
            <p className="text-sm text-gray-500">Loading events...</p>
          </div>
        ) : noRecentActivity ? (
          <PanelEmptyState
            iconBg="bg-emerald-50"
            iconColor="text-emerald-400"
            Icon={FaCheckCircle}
            title="No recent events"
            subtitle="Events for your tracked mergers and industries will appear here"
          />
        ) : (
          <>
            {mergerGroups.length > 0 && (
              <>
                <div className="px-5 py-2 bg-gray-50/60 border-y border-gray-100">
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                    Tracked mergers
                  </h3>
                </div>
                <div className="divide-y divide-gray-50">
                  {mergerGroups.map((group) => (
                    <MergerEventGroup
                      key={group.merger_id}
                      group={group}
                      onClose={onClose}
                      wasUnseenOnOpen={wasUnseenOnOpen}
                    />
                  ))}
                </div>
              </>
            )}

            {industryGroups.length > 0 && (
              <>
                <div className="px-5 py-2 bg-gray-50/60 border-y border-gray-100">
                  <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                    Followed industries
                  </h3>
                </div>
                <div className="divide-y divide-gray-50">
                  {industryGroups.map((group) => (
                    <IndustryEventGroup
                      key={group.industry_code}
                      group={group}
                      onClose={onClose}
                      wasUnseenOnOpen={wasUnseenOnOpen}
                    />
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      {!nothingTracked && (
        <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/80 flex-shrink-0">
          <div className="flex items-center gap-1.5 text-xs font-medium">
            <Link
              to="/mergers?tracked=true"
              onClick={onClose}
              className="text-primary hover:text-primary-dark transition-colors"
            >
              View tracked
            </Link>
            <span className="text-gray-500">·</span>
            <Link
              to="/industries"
              onClick={onClose}
              className="text-primary hover:text-primary-dark transition-colors"
            >
              Browse industries
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default NotificationPanel;
