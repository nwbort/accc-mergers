import { useRef, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTracking } from '../context/TrackingContext';
import { formatDate, getDaysRemaining, isDatePast } from '../utils/dates';

function MergerEventGroup({ group, onClose, isEventSeen }) {
  const [showPastEvents, setShowPastEvents] = useState(false);

  // Separate past and future events
  const pastEvents = group.events.filter((e) => isDatePast(e.date));
  const futureEvents = group.events.filter((e) => !isDatePast(e.date));

  // Sort all events by date descending (most recent/latest dates first)
  futureEvents.sort((a, b) => new Date(b.date) - new Date(a.date));
  pastEvents.sort((a, b) => new Date(b.date) - new Date(a.date));

  return (
    <div className="p-4">
      <Link
        to={`/mergers/${group.merger_id}`}
        onClick={onClose}
        className="block hover:bg-gray-50 -mx-4 -mt-4 px-4 pt-4 pb-2 rounded-t"
      >
        <h3 className="text-sm font-medium text-gray-900 hover:text-primary line-clamp-2">
          {group.merger_name}
        </h3>
        <p className="text-xs text-gray-500 mt-0.5">{group.merger_id}</p>
      </Link>

      <ul className="mt-2 space-y-2">
        {/* Future/current events */}
        {futureEvents.map((event, idx) => {
          const daysRemaining = getDaysRemaining(event.date);
          const isUpcoming = event.type === 'consultation_due' || event.type === 'determination_due';
          const isNew = !isEventSeen(event);

          return (
            <li
              key={`${event.merger_id}-${event.date}-future-${idx}`}
              className="text-xs"
            >
              <div className="flex items-start gap-2">
                <span className={`mt-0.5 flex-shrink-0 w-2 h-2 rounded-full ${
                  isNew ? 'bg-green-500' : isUpcoming ? 'bg-amber-400' : 'bg-gray-300'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-gray-700 truncate">
                    {event.display_title || event.event_type_display || event.title}
                  </p>
                  <p className="text-gray-400">
                    {formatDate(event.date)}
                    {isUpcoming && daysRemaining > 0 && (
                      <span className="ml-1 text-amber-600">
                        ({daysRemaining} day{daysRemaining !== 1 ? 's' : ''})
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </li>
          );
        })}

        {/* Past events collapsible */}
        {pastEvents.length > 0 && (
          <>
            <li className="text-xs">
              <button
                onClick={() => setShowPastEvents(!showPastEvents)}
                className="text-gray-400 hover:text-gray-600 hover:underline cursor-pointer pl-4"
              >
                {showPastEvents ? 'Hide' : 'Show'} {pastEvents.length} past event{pastEvents.length !== 1 ? 's' : ''}
              </button>
            </li>

            {showPastEvents && pastEvents.map((event, idx) => {
              const isNew = !isEventSeen(event);

              return (
                <li
                  key={`${event.merger_id}-${event.date}-past-${idx}`}
                  className="text-xs"
                >
                  <div className="flex items-start gap-2">
                    <span className={`mt-0.5 flex-shrink-0 w-2 h-2 rounded-full ${
                      isNew ? 'bg-green-500' : 'bg-gray-300'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-500 truncate">
                        {event.display_title || event.event_type_display || event.title}
                      </p>
                      <p className="text-gray-400">
                        {formatDate(event.date)}
                      </p>
                    </div>
                  </div>
                </li>
              );
            })}
          </>
        )}
      </ul>
    </div>
  );
}

function NotificationPanel({ isOpen, onClose }) {
  const panelRef = useRef(null);
  const {
    trackedEvents,
    trackedMergerIds,
    markEventsAsSeen,
    isEventSeen,
    loading
  } = useTracking();

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
  useEffect(() => {
    if (isOpen && trackedEvents.length > 0) {
      markEventsAsSeen(trackedEvents);
    }
  }, [isOpen, trackedEvents, markEventsAsSeen]);

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
    // Check for unseen events
    const aUnseenEvents = a.events.filter((e) => !isEventSeen(e));
    const bUnseenEvents = b.events.filter((e) => !isEventSeen(e));
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

  return (
    <div
      ref={panelRef}
      className="fixed left-1/2 -translate-x-1/2 top-16 sm:absolute sm:left-auto sm:translate-x-0 sm:right-0 sm:top-full sm:mt-2 w-[calc(100vw-1rem)] sm:w-96 bg-white rounded-lg shadow-xl border border-gray-200 z-50 max-h-[70vh] sm:max-h-[80vh] overflow-hidden flex flex-col"
      role="dialog"
      aria-label="Notifications panel"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between flex-shrink-0">
        <h2 className="text-sm font-semibold text-gray-900">
          Tracked Mergers
          {trackedMergerIds.length > 0 && (
            <span className="ml-2 text-gray-500 font-normal">
              ({trackedMergerIds.length})
            </span>
          )}
        </h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 p-1"
          aria-label="Close notifications"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="overflow-y-auto flex-1">
        {trackedMergerIds.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <p className="text-sm text-gray-500 mb-2">No tracked mergers yet</p>
            <p className="text-xs text-gray-400">
              Visit a merger&apos;s page and click &quot;Track&quot; to receive updates
            </p>
          </div>
        ) : loading ? (
          <div className="px-4 py-8 text-center">
            <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto mb-3"></div>
            <p className="text-sm text-gray-500">Loading events...</p>
          </div>
        ) : trackedEvents.length === 0 ? (
          <div className="px-4 py-8 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-gray-500">No recent events</p>
            <p className="text-xs text-gray-400 mt-1">
              Events for your tracked mergers will appear here
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {mergerGroups.map((group) => (
              <MergerEventGroup
                key={group.merger_id}
                group={group}
                onClose={onClose}
                isEventSeen={isEventSeen}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      {trackedMergerIds.length > 0 && (
        <div className="px-4 py-3 border-t border-gray-200 bg-gray-50 flex-shrink-0">
          <Link
            to="/mergers"
            onClick={onClose}
            className="text-xs text-primary hover:text-primary-dark hover:underline"
          >
            View all mergers
          </Link>
        </div>
      )}
    </div>
  );
}

export default NotificationPanel;
