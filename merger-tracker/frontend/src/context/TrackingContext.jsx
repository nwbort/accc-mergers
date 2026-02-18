import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { API_ENDPOINTS } from '../config';

const TrackingContext = createContext(null);

const STORAGE_KEYS = {
  TRACKED_MERGERS: 'merger_tracker_tracked',
  SEEN_EVENTS: 'merger_tracker_seen_events',
};

// Generate a unique key for an event
// Use a consistent order and normalize the title field for stability
const getEventKey = (event) => {
  // Normalize title: prefer display_title, then title, then event_type_display, finally type
  const title = event.display_title || event.title || event.event_type_display || event.type || '';
  return `${event.merger_id}_${event.date}_${title}`;
};

// Deduplicate events by their event key
const dedupeEvents = (events) => {
  const seen = new Set();
  return events.filter((event) => {
    const key = getEventKey(event);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export function TrackingProvider({ children }) {
  const [trackedMergerIds, setTrackedMergerIds] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.TRACKED_MERGERS);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Use Set internally for O(1) lookups
  const [seenEventKeys, setSeenEventKeys] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.SEEN_EVENTS);
      if (!stored) return new Set();
      const keys = JSON.parse(stored);
      return new Set(keys);
    } catch {
      return new Set();
    }
  });

  // Create Sets for O(1) lookup performance
  const trackedMergerIdsSet = useMemo(() => new Set(trackedMergerIds), [trackedMergerIds]);

  // Timeline events for tracked mergers
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  // Track newly added merger IDs so we can mark their events as seen
  const [newlyTrackedIds, setNewlyTrackedIds] = useState([]);
  const newlyTrackedIdsSet = useMemo(() => new Set(newlyTrackedIds), [newlyTrackedIds]);

  // Fetch events on mount and when tracked mergers change
  useEffect(() => {
    const fetchEvents = async () => {
      if (trackedMergerIds.length === 0) {
        setTimelineEvents([]);
        setUpcomingEvents([]);
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        // Fetch individual merger files instead of full timeline for better performance
        // This is more efficient when tracking only a few mergers
        const mergerPromises = trackedMergerIds.map(id =>
          fetch(API_ENDPOINTS.mergerDetail(id))
            .then(res => res.ok ? res.json() : null)
            .catch(() => null)
        );

        const upcomingRes = fetch(API_ENDPOINTS.upcomingEvents);

        const [mergers, upcomingResponse] = await Promise.all([
          Promise.all(mergerPromises),
          upcomingRes
        ]);

        let allFetchedEvents = [];

        // Extract events from individual merger files
        const timelineEventsFromMergers = [];
        mergers.forEach(merger => {
          if (!merger) return;
          const events = merger.events || [];
          events.forEach(event => {
            timelineEventsFromMergers.push({
              date: event.date,
              title: event.title,
              display_title: event.display_title,
              url: event.url,
              url_gh: event.url_gh,
              status: event.status,
              merger_id: merger.merger_id,
              merger_name: merger.merger_name,
              phase: event.phase,
              is_waiver: merger.is_waiver
            });
          });
        });

        setTimelineEvents(timelineEventsFromMergers);
        allFetchedEvents = [...allFetchedEvents, ...timelineEventsFromMergers];

        // Fetch upcoming events
        if (upcomingResponse.ok) {
          const data = await upcomingResponse.json();
          // Filter to only tracked mergers (using Set for O(1) lookup)
          // Normalize event structure to match timeline events for consistent keys
          const filtered = data.events
            .filter((e) => trackedMergerIdsSet.has(e.merger_id))
            .map((event) => ({
              ...event,
              // Ensure display_title is set for consistent key generation
              display_title: event.display_title || event.event_type_display || event.title,
              // Preserve original fields too
              title: event.title || event.event_type_display,
            }));
          setUpcomingEvents(filtered);
          allFetchedEvents = [...allFetchedEvents, ...filtered];
        }

        // Mark all events for newly tracked mergers as seen
        if (newlyTrackedIds.length > 0) {
          const eventsToMarkSeen = allFetchedEvents.filter((e) =>
            newlyTrackedIdsSet.has(e.merger_id)
          );
          if (eventsToMarkSeen.length > 0) {
            const keys = eventsToMarkSeen.map(getEventKey);
            setSeenEventKeys((prev) => {
              const newSet = new Set(prev);
              let hasChanges = false;
              keys.forEach((k) => {
                if (!newSet.has(k)) {
                  newSet.add(k);
                  hasChanges = true;
                }
              });
              return hasChanges ? newSet : prev;
            });
          }
          setNewlyTrackedIds([]);
        }
      } catch (err) {
        console.error('Failed to fetch events:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchEvents();
  }, [trackedMergerIds, newlyTrackedIds, trackedMergerIdsSet, newlyTrackedIdsSet]);

  // Persist tracked mergers to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.TRACKED_MERGERS, JSON.stringify(trackedMergerIds));
    } catch (e) {
      console.error('Failed to save tracked mergers:', e);
    }
  }, [trackedMergerIds]);

  // Persist seen events to localStorage (convert Set to Array)
  useEffect(() => {
    try {
      const keysArray = Array.from(seenEventKeys);
      localStorage.setItem(STORAGE_KEYS.SEEN_EVENTS, JSON.stringify(keysArray));
    } catch (e) {
      console.error('Failed to save seen events:', e);
    }
  }, [seenEventKeys]);

  const trackMerger = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => {
      const prevSet = new Set(prev);
      if (prevSet.has(mergerId)) return prev;
      // Mark this as a newly tracked merger so we can auto-mark its events as seen
      setNewlyTrackedIds((ids) => [...ids, mergerId]);
      return [...prev, mergerId];
    });
  }, []);

  const untrackMerger = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => prev.filter((id) => id !== mergerId));
  }, []);

  const isTracked = useCallback((mergerId) => {
    return trackedMergerIdsSet.has(mergerId);
  }, [trackedMergerIdsSet]);

  const toggleTracking = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => {
      const prevSet = new Set(prev);
      if (prevSet.has(mergerId)) {
        return prev.filter((id) => id !== mergerId);
      }
      // Mark this as a newly tracked merger so we can auto-mark its events as seen
      setNewlyTrackedIds((ids) => [...ids, mergerId]);
      return [...prev, mergerId];
    });
  }, []);

  const markEventAsSeen = useCallback((event) => {
    const key = getEventKey(event);
    setSeenEventKeys((prev) => {
      if (prev.has(key)) return prev;
      const newSet = new Set(prev);
      newSet.add(key);
      return newSet;
    });
  }, []);

  const markEventsAsSeen = useCallback((events) => {
    const keys = events.map(getEventKey);
    setSeenEventKeys((prev) => {
      const newSet = new Set(prev);
      let hasChanges = false;
      keys.forEach((k) => {
        if (!newSet.has(k)) {
          newSet.add(k);
          hasChanges = true;
        }
      });
      return hasChanges ? newSet : prev;
    });
  }, []);

  const isEventSeen = useCallback((event) => {
    const key = getEventKey(event);
    return seenEventKeys.has(key);
  }, [seenEventKeys]);

  // All unique events for tracked mergers (for notification panel)
  const trackedEvents = useMemo(() => {
    const unique = dedupeEvents([...timelineEvents, ...upcomingEvents]);
    // Sort by date descending (most recent first)
    return unique.sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [timelineEvents, upcomingEvents]);

  // Get unseen events (subset of trackedEvents)
  const unseenEvents = useMemo(() => {
    return trackedEvents.filter((event) => !seenEventKeys.has(getEventKey(event)));
  }, [trackedEvents, seenEventKeys]);

  // Count of unseen events (for badge)
  const unseenCount = unseenEvents.length;

  const value = useMemo(() => ({
    trackedMergerIds,
    trackMerger,
    untrackMerger,
    isTracked,
    toggleTracking,
    markEventAsSeen,
    markEventsAsSeen,
    isEventSeen,
    unseenEvents,
    unseenCount,
    trackedEvents,
    loading,
    getEventKey,
  }), [
    trackedMergerIds,
    trackMerger,
    untrackMerger,
    isTracked,
    toggleTracking,
    markEventAsSeen,
    markEventsAsSeen,
    isEventSeen,
    unseenEvents,
    unseenCount,
    trackedEvents,
    loading,
  ]);

  return (
    <TrackingContext.Provider value={value}>
      {children}
    </TrackingContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTracking() {
  const context = useContext(TrackingContext);
  if (!context) {
    throw new Error('useTracking must be used within a TrackingProvider');
  }
  return context;
}

export default TrackingContext;
