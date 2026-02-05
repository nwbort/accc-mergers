import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { API_ENDPOINTS } from '../config';

const TrackingContext = createContext(null);

const STORAGE_KEYS = {
  TRACKED_MERGERS: 'merger_tracker_tracked',
  SEEN_EVENTS: 'merger_tracker_seen_events',
};

// Generate a unique key for an event
const getEventKey = (event) => {
  return `${event.merger_id}_${event.date}_${event.title || event.display_title || event.type}`;
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

  const [seenEventKeys, setSeenEventKeys] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.SEEN_EVENTS);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  // Timeline events for tracked mergers
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
  const [loading, setLoading] = useState(true);

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
        const [timelineRes, upcomingRes] = await Promise.all([
          fetch(API_ENDPOINTS.timeline),
          fetch(API_ENDPOINTS.upcomingEvents),
        ]);

        if (timelineRes.ok) {
          const data = await timelineRes.json();
          // Filter to only tracked mergers
          const filtered = data.events.filter((e) => trackedMergerIds.includes(e.merger_id));
          setTimelineEvents(filtered);
        }

        if (upcomingRes.ok) {
          const data = await upcomingRes.json();
          // Filter to only tracked mergers
          const filtered = data.events.filter((e) => trackedMergerIds.includes(e.merger_id));
          setUpcomingEvents(filtered);
        }
      } catch (err) {
        console.error('Failed to fetch events:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchEvents();
  }, [trackedMergerIds]);

  // Persist tracked mergers to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.TRACKED_MERGERS, JSON.stringify(trackedMergerIds));
    } catch (e) {
      console.error('Failed to save tracked mergers:', e);
    }
  }, [trackedMergerIds]);

  // Persist seen events to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.SEEN_EVENTS, JSON.stringify(seenEventKeys));
    } catch (e) {
      console.error('Failed to save seen events:', e);
    }
  }, [seenEventKeys]);

  const trackMerger = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => {
      if (prev.includes(mergerId)) return prev;
      return [...prev, mergerId];
    });
  }, []);

  const untrackMerger = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => prev.filter((id) => id !== mergerId));
  }, []);

  const isTracked = useCallback((mergerId) => {
    return trackedMergerIds.includes(mergerId);
  }, [trackedMergerIds]);

  const toggleTracking = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => {
      if (prev.includes(mergerId)) {
        return prev.filter((id) => id !== mergerId);
      }
      return [...prev, mergerId];
    });
  }, []);

  const markEventAsSeen = useCallback((event) => {
    const key = getEventKey(event);
    setSeenEventKeys((prev) => {
      if (prev.includes(key)) return prev;
      return [...prev, key];
    });
  }, []);

  const markEventsAsSeen = useCallback((events) => {
    const keys = events.map(getEventKey);
    setSeenEventKeys((prev) => {
      const newKeys = keys.filter((k) => !prev.includes(k));
      if (newKeys.length === 0) return prev;
      return [...prev, ...newKeys];
    });
  }, []);

  const isEventSeen = useCallback((event) => {
    const key = getEventKey(event);
    return seenEventKeys.includes(key);
  }, [seenEventKeys]);

  // Get unseen events (combines timeline and upcoming, removes duplicates)
  const unseenEvents = useMemo(() => {
    const allEvents = [...timelineEvents, ...upcomingEvents];
    // Dedupe by event key
    const seen = new Set();
    const unique = allEvents.filter((event) => {
      const key = getEventKey(event);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    // Filter to unseen only
    return unique.filter((event) => !seenEventKeys.includes(getEventKey(event)));
  }, [timelineEvents, upcomingEvents, seenEventKeys]);

  // Count of unseen events (for badge)
  const unseenCount = unseenEvents.length;

  // All events for tracked mergers (for notification panel)
  const trackedEvents = useMemo(() => {
    const allEvents = [...timelineEvents, ...upcomingEvents];
    // Dedupe by event key
    const seen = new Set();
    const unique = allEvents.filter((event) => {
      const key = getEventKey(event);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    // Sort by date descending (most recent first)
    return unique.sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [timelineEvents, upcomingEvents]);

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

export function useTracking() {
  const context = useContext(TrackingContext);
  if (!context) {
    throw new Error('useTracking must be used within a TrackingProvider');
  }
  return context;
}

export default TrackingContext;
