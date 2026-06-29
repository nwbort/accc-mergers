import { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { API_ENDPOINTS } from '../config';

const TrackingContext = createContext(null);

const STORAGE_KEYS = {
  TRACKED_MERGERS: 'merger_tracker_tracked',
  TRACKED_INDUSTRIES: 'merger_tracker_tracked_industries',
  SEEN_EVENTS: 'merger_tracker_seen_events',
};

// Relationship values (from the data pipeline, see scripts/static_data/loaders.py)
// where the *tracked* merger is the earlier matter and its related merger is the
// newer re-filed one. Tracking a merger auto-tracks its related merger only in
// this forward direction: tracking a declined waiver / suspended matter also
// tracks the notification it was re-filed as, but tracking the re-filed matter
// must NOT pull in the historical one it superseded.
const FORWARD_REFILE_RELATIONSHIPS = new Set([
  'refiled_as',
  'suspended_refiled_as',
]);

// Generate a unique key for an event
// Use a consistent order and normalize the title field for stability
const getEventKey = (event) => {
  // Normalize title: prefer display_title, then title, then event_type_display, finally type
  const title = event.display_title || event.title || event.event_type_display || event.type || '';
  // Industry-follow events are scoped to the industry they were surfaced from,
  // so the same merger filed under two followed industries stays distinct (and
  // distinct from the merger's own tracked timeline events).
  const prefix = event.industry_code ? `ind_${event.industry_code}_` : '';
  return `${prefix}${event.merger_id}_${event.date}_${title}`;
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
    } catch (err) {
      console.error('Failed to read tracked mergers from localStorage:', err);
      return [];
    }
  });

  // Followed industries store an entry per ANZSIC code with its display name so
  // the notification panel can label groups without an extra fetch.
  const [trackedIndustries, setTrackedIndustries] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.TRACKED_INDUSTRIES);
      return stored ? JSON.parse(stored) : [];
    } catch (err) {
      console.error('Failed to read tracked industries from localStorage:', err);
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
    } catch (err) {
      console.error('Failed to read seen events from localStorage:', err);
      return new Set();
    }
  });

  // Create Sets for O(1) lookup performance
  const trackedMergerIdsSet = useMemo(() => new Set(trackedMergerIds), [trackedMergerIds]);
  const trackedIndustryCodes = useMemo(
    () => trackedIndustries.map((i) => i.code),
    [trackedIndustries]
  );
  const trackedIndustryCodesSet = useMemo(
    () => new Set(trackedIndustryCodes),
    [trackedIndustryCodes]
  );
  // Stable key so the fetch effect only re-runs when the set of codes changes,
  // not when an industry's stored name is rewritten.
  const trackedIndustryCodesKey = useMemo(
    () => [...trackedIndustryCodes].sort().join(','),
    [trackedIndustryCodes]
  );

  // Industry-follow events (new filings + new determinations) for followed industries
  const [industryEvents, setIndustryEvents] = useState([]);
  // Track newly followed industry codes so their existing events are marked seen
  const [newlyTrackedIndustryCodes, setNewlyTrackedIndustryCodes] = useState([]);
  const newlyTrackedIndustryCodesSet = useMemo(
    () => new Set(newlyTrackedIndustryCodes),
    [newlyTrackedIndustryCodes]
  );

  // Timeline events for tracked mergers
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [upcomingEvents, setUpcomingEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  // Track newly added merger IDs so we can mark their events as seen
  const [newlyTrackedIds, setNewlyTrackedIds] = useState([]);
  const newlyTrackedIdsSet = useMemo(() => new Set(newlyTrackedIds), [newlyTrackedIds]);

  // Mirror the latest tracked IDs in a ref so the track callbacks can tell an
  // add from a remove without re-creating on every change (they keep empty deps).
  const trackedMergerIdsRef = useRef(trackedMergerIds);
  useEffect(() => {
    trackedMergerIdsRef.current = trackedMergerIds;
  }, [trackedMergerIds]);

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

        const mergers = await Promise.all(mergerPromises);

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

        // Synthesize upcoming events directly from individual merger data for tracked mergers.
        // These per-merger files are already fetched above, so we derive determination,
        // consultation, and competition-concerns due dates from them rather than fetching the
        // separate upcoming-events.json feed. This avoids an extra network request on every page
        // (TrackingProvider wraps the whole app) and is not subject to that feed's 60-day window,
        // so events whose deadline is months away (e.g. Phase 2 determinations) still surface.
        const now = new Date();
        const syntheticUpcomingEvents = [];
        mergers.forEach(merger => {
          if (!merger) return;
          // Skip if already determined, a waiver, or assessment is no longer active
          if (merger.determination_publication_date) return;
          if (merger.is_waiver) return;
          if (merger.status === 'Assessment suspended') return;
          if (merger.status === 'Assessment ceased') return;

          if (merger.end_of_determination_period) {
            const dueDate = new Date(merger.end_of_determination_period);
            if (dueDate > now) {
              syntheticUpcomingEvents.push({
                type: 'determination_due',
                event_type_display: 'Determination due',
                display_title: 'Determination due',
                title: 'Determination due',
                date: merger.end_of_determination_period,
                merger_id: merger.merger_id,
                merger_name: merger.merger_name,
                status: merger.status,
                stage: merger.stage,
                effective_notification_datetime: merger.effective_notification_datetime,
                is_waiver: merger.is_waiver,
              });
            }
          }

          if (merger.consultation_response_due_date) {
            const dueDate = new Date(merger.consultation_response_due_date);
            if (dueDate > now) {
              syntheticUpcomingEvents.push({
                type: 'consultation_due',
                event_type_display: 'Consultation responses due',
                display_title: 'Consultation responses due',
                title: 'Consultation responses due',
                date: merger.consultation_response_due_date,
                merger_id: merger.merger_id,
                merger_name: merger.merger_name,
                status: merger.status,
                stage: merger.stage,
                effective_notification_datetime: merger.effective_notification_datetime,
                is_waiver: merger.is_waiver,
              });
            }
          }

          if (merger.competition_concerns_notice_date) {
            const dueDate = new Date(merger.competition_concerns_notice_date);
            if (dueDate > now) {
              syntheticUpcomingEvents.push({
                type: 'notice_of_competition_concerns',
                event_type_display: 'Notice of competition concerns',
                display_title: 'Notice of competition concerns',
                title: 'Notice of competition concerns',
                date: merger.competition_concerns_notice_date,
                merger_id: merger.merger_id,
                merger_name: merger.merger_name,
                status: merger.status,
                stage: merger.stage,
                effective_notification_datetime: merger.effective_notification_datetime,
                is_waiver: merger.is_waiver,
              });
            }
          }
        });

        setUpcomingEvents(syntheticUpcomingEvents);
        allFetchedEvents = [...allFetchedEvents, ...syntheticUpcomingEvents];

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
  }, [trackedMergerIds, newlyTrackedIds, newlyTrackedIdsSet]);

  // Fetch industry-follow events whenever the set of followed industries changes.
  // Unlike merger tracking (which surfaces every timeline event), following an
  // industry only flags two things: a new merger filed in it, and a new
  // determination published for one of its mergers. These are derived from the
  // lightweight per-industry detail files (notification_date / determination_date
  // on each merger summary), so no per-merger fetch is needed.
  useEffect(() => {
    const fetchIndustryEvents = async () => {
      if (trackedIndustryCodes.length === 0) {
        setIndustryEvents([]);
        return;
      }

      try {
        const industryPromises = trackedIndustryCodes.map((code) =>
          fetch(API_ENDPOINTS.industryDetail(code))
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => ({ code, data }))
            .catch(() => ({ code, data: null }))
        );

        const results = await Promise.all(industryPromises);

        const derived = [];
        results.forEach(({ code, data }) => {
          if (!data) return;
          const industryName = data.name || code;
          (data.mergers || []).forEach((m) => {
            const base = {
              industry_code: code,
              industry_name: industryName,
              merger_id: m.merger_id,
              merger_name: m.merger_name,
              is_waiver: m.is_waiver,
              status: m.status,
            };
            if (m.notification_date) {
              derived.push({
                ...base,
                type: 'industry_new_merger',
                event_type_display: 'New merger filed',
                display_title: 'New merger filed',
                title: 'New merger filed',
                date: m.notification_date,
              });
            }
            if (m.determination_date) {
              derived.push({
                ...base,
                type: 'industry_determination',
                event_type_display: 'Determination published',
                display_title: 'Determination published',
                title: 'Determination published',
                date: m.determination_date,
              });
            }
          });
        });

        setIndustryEvents(derived);

        // Mark all events for newly followed industries as seen, so following an
        // industry doesn't immediately flag its entire back catalogue.
        if (newlyTrackedIndustryCodes.length > 0) {
          const eventsToMarkSeen = derived.filter((e) =>
            newlyTrackedIndustryCodesSet.has(e.industry_code)
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
          setNewlyTrackedIndustryCodes([]);
        }
      } catch (err) {
        console.error('Failed to fetch industry events:', err);
      }
    };

    fetchIndustryEvents();
    // trackedIndustryCodesKey collapses the code list to a stable primitive so
    // renaming a stored industry doesn't trigger a refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trackedIndustryCodesKey, newlyTrackedIndustryCodes, newlyTrackedIndustryCodesSet]);

  // Persist tracked mergers to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.TRACKED_MERGERS, JSON.stringify(trackedMergerIds));
    } catch (e) {
      console.error('Failed to save tracked mergers:', e);
    }
  }, [trackedMergerIds]);

  // Persist tracked industries to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.TRACKED_INDUSTRIES, JSON.stringify(trackedIndustries));
    } catch (e) {
      console.error('Failed to save tracked industries:', e);
    }
  }, [trackedIndustries]);

  // Persist seen events to localStorage (convert Set to Array)
  useEffect(() => {
    try {
      const keysArray = Array.from(seenEventKeys);
      localStorage.setItem(STORAGE_KEYS.SEEN_EVENTS, JSON.stringify(keysArray));
    } catch (e) {
      console.error('Failed to save seen events:', e);
    }
  }, [seenEventKeys]);

  // After a merger is tracked, follow its related-merger link forward and track
  // the re-filed matter(s) too — e.g. tracking a declined waiver also tracks the
  // notification it was re-filed as. Only the forward direction is followed, so
  // tracking the newer matter never auto-tracks the historical one. Chains
  // (A re-filed as B re-filed as C) are walked iteratively; a visited set guards
  // against the (shouldn't-happen) cycle. Newly added IDs are marked as newly
  // tracked so their existing events don't immediately flag as unseen.
  const autoTrackRelatedForward = useCallback(async (mergerId) => {
    const idsToAdd = [];
    const visited = new Set([mergerId]);
    let currentId = mergerId;

    while (currentId) {
      let merger;
      try {
        const res = await fetch(API_ENDPOINTS.mergerDetail(currentId));
        if (!res.ok) break;
        merger = await res.json();
      } catch (err) {
        console.error('Failed to resolve related merger for auto-tracking:', err);
        break;
      }

      const related = merger && merger.related_merger;
      if (!related || !FORWARD_REFILE_RELATIONSHIPS.has(related.relationship)) break;

      const relatedId = related.merger_id;
      if (!relatedId || visited.has(relatedId)) break;

      visited.add(relatedId);
      idsToAdd.push(relatedId);
      currentId = relatedId;
    }

    if (idsToAdd.length === 0) return;

    setTrackedMergerIds((prev) => {
      const prevSet = new Set(prev);
      const fresh = idsToAdd.filter((id) => !prevSet.has(id));
      if (fresh.length === 0) return prev;
      // Mark auto-tracked mergers as newly tracked so we mark their events as seen
      setNewlyTrackedIds((ids) => [...ids, ...fresh]);
      return [...prev, ...fresh];
    });
  }, []);

  const trackMerger = useCallback((mergerId) => {
    const wasTracked = trackedMergerIdsRef.current.includes(mergerId);
    setTrackedMergerIds((prev) => {
      const prevSet = new Set(prev);
      if (prevSet.has(mergerId)) return prev;
      // Mark this as a newly tracked merger so we can auto-mark its events as seen
      setNewlyTrackedIds((ids) => [...ids, mergerId]);
      return [...prev, mergerId];
    });
    if (!wasTracked) autoTrackRelatedForward(mergerId);
  }, [autoTrackRelatedForward]);

  const untrackMerger = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => prev.filter((id) => id !== mergerId));
  }, []);

  const isTracked = useCallback((mergerId) => {
    return trackedMergerIdsSet.has(mergerId);
  }, [trackedMergerIdsSet]);

  const toggleTracking = useCallback((mergerId) => {
    const wasTracked = trackedMergerIdsRef.current.includes(mergerId);
    setTrackedMergerIds((prev) => {
      const prevSet = new Set(prev);
      if (prevSet.has(mergerId)) {
        return prev.filter((id) => id !== mergerId);
      }
      // Mark this as a newly tracked merger so we can auto-mark its events as seen
      setNewlyTrackedIds((ids) => [...ids, mergerId]);
      return [...prev, mergerId];
    });
    // Only an add (not a remove) should pull in the re-filed matter.
    if (!wasTracked) autoTrackRelatedForward(mergerId);
  }, [autoTrackRelatedForward]);

  const isIndustryTracked = useCallback((code) => {
    return trackedIndustryCodesSet.has(code);
  }, [trackedIndustryCodesSet]);

  const trackIndustry = useCallback((code, name) => {
    setTrackedIndustries((prev) => {
      if (prev.some((i) => i.code === code)) return prev;
      setNewlyTrackedIndustryCodes((codes) => [...codes, code]);
      return [...prev, { code, name: name || code }];
    });
  }, []);

  const untrackIndustry = useCallback((code) => {
    setTrackedIndustries((prev) => prev.filter((i) => i.code !== code));
  }, []);

  const toggleIndustryTracking = useCallback((code, name) => {
    setTrackedIndustries((prev) => {
      if (prev.some((i) => i.code === code)) {
        return prev.filter((i) => i.code !== code);
      }
      setNewlyTrackedIndustryCodes((codes) => [...codes, code]);
      return [...prev, { code, name: name || code }];
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

  // Industry-follow events, deduped and sorted most-recent-first.
  const trackedIndustryEvents = useMemo(() => {
    const unique = dedupeEvents(industryEvents);
    return unique.sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [industryEvents]);

  const unseenIndustryEvents = useMemo(() => {
    return trackedIndustryEvents.filter((event) => !seenEventKeys.has(getEventKey(event)));
  }, [trackedIndustryEvents, seenEventKeys]);

  // Count of unseen events (for badge) — both tracked mergers and followed industries
  const unseenCount = unseenEvents.length + unseenIndustryEvents.length;

  const value = useMemo(() => ({
    trackedMergerIds,
    trackMerger,
    untrackMerger,
    isTracked,
    toggleTracking,
    trackedIndustries,
    trackedIndustryCodes,
    trackIndustry,
    untrackIndustry,
    isIndustryTracked,
    toggleIndustryTracking,
    trackedIndustryEvents,
    unseenIndustryEvents,
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
    trackedIndustries,
    trackedIndustryCodes,
    trackIndustry,
    untrackIndustry,
    isIndustryTracked,
    toggleIndustryTracking,
    trackedIndustryEvents,
    unseenIndustryEvents,
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
