import { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { API_ENDPOINTS } from '../config';
import { pingFeatureEvent, trackIndustryEvent, trackMergerEvent } from '../utils/trackEvent';
import { fetchIndustryNode, industryDivisionCacheKey } from '../utils/industryNode';
import { dataCache } from '../utils/dataCache';
import {
  dedupeEvents,
  forwardRefileLink,
  getEventKey,
  getLegacyEventKeys,
  industryEventsFromNode,
  timelineEventsFromMerger,
  upcomingEventsFromMerger,
} from '../utils/trackedEvents';

const TrackingContext = createContext(null);

const STORAGE_KEYS = {
  TRACKED_MERGERS: 'merger_tracker_tracked',
  TRACKED_INDUSTRIES: 'merger_tracker_tracked_industries',
  SEEN_EVENTS: 'merger_tracker_seen_events',
  // Forward re-file links ("sourceId->relatedId") we've already auto-tracked,
  // so each is acted on exactly once. See the auto-track logic in the fetch
  // effect for why this is persisted.
  AUTO_TRACK_LINKS: 'merger_tracker_auto_track_links',
  // User setting: automatically track any merger that reaches Phase 2.
  AUTO_TRACK_PHASE2: 'merger_tracker_auto_track_phase2',
  // Phase 2 merger IDs we've already auto-tracked, so each is acted on exactly
  // once (a matter the user later untracks is not silently re-added). Mirrors
  // AUTO_TRACK_LINKS. See the Phase 2 auto-track effect.
  AUTO_TRACK_PHASE2_IDS: 'merger_tracker_auto_tracked_phase2_ids',
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
  // Bumped by refreshEvents() to fetch everything again: the browser
  // notification service worker asks for that when a push arrives while the
  // site is open, rather than showing a notification over it.
  const [refreshCount, setRefreshCount] = useState(0);
  // Track newly added merger IDs so we can mark their events as seen
  const [newlyTrackedIds, setNewlyTrackedIds] = useState([]);
  const newlyTrackedIdsSet = useMemo(() => new Set(newlyTrackedIds), [newlyTrackedIds]);

  // Forward re-file links we've already auto-tracked, keyed "sourceId->relatedId".
  // Persisted so we act on each link exactly once: a re-filing recorded after the
  // source was tracked still gets picked up, but a re-filed matter the user later
  // untracks is never silently re-added. Mirrored in a ref so the fetch effect can
  // read the latest set without listing it as a dependency (which would re-run it).
  const [autoTrackLinks, setAutoTrackLinks] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.AUTO_TRACK_LINKS);
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch (err) {
      console.error('Failed to read auto-track links from localStorage:', err);
      return new Set();
    }
  });
  const autoTrackLinksRef = useRef(autoTrackLinks);
  useEffect(() => {
    autoTrackLinksRef.current = autoTrackLinks;
  }, [autoTrackLinks]);

  // User setting: when enabled, every matter that reaches Phase 2 is added to
  // tracked mergers.
  const [autoTrackPhase2, setAutoTrackPhase2] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEYS.AUTO_TRACK_PHASE2) === 'true';
    } catch (err) {
      console.error('Failed to read auto-track Phase 2 setting from localStorage:', err);
      return false;
    }
  });

  // Phase 2 merger IDs already acted on by the auto-track effect. Persisted so a
  // matter is auto-tracked exactly once: a matter the user later untracks is not
  // re-added, while a matter that reaches Phase 2 after the setting was enabled
  // is still picked up on the next load. Mirrored in a ref so the effect can read
  // the latest set without listing it as a dependency (which would re-run it).
  const [autoTrackedPhase2Ids, setAutoTrackedPhase2Ids] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.AUTO_TRACK_PHASE2_IDS);
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch (err) {
      console.error('Failed to read auto-tracked Phase 2 IDs from localStorage:', err);
      return new Set();
    }
  });
  const autoTrackedPhase2IdsRef = useRef(autoTrackedPhase2Ids);
  useEffect(() => {
    autoTrackedPhase2IdsRef.current = autoTrackedPhase2Ids;
  }, [autoTrackedPhase2Ids]);

  // Latest tracked IDs mirrored in a ref so the Phase 2 auto-track effect can
  // tell which matters are already tracked without depending on trackedMergerIds
  // (which would make it re-fetch phase2.json on every track/untrack).
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

        // Auto-track re-filed matters. If a tracked merger points forward to a
        // newer re-filed matter (a declined waiver → its notification, or a
        // suspended assessment → its refile) that we haven't acted on yet, track
        // it too. Doing this here — rather than only when the user clicks track —
        // means a re-filing recorded *after* the source was tracked is still
        // picked up on the next load. Each link is recorded in autoTrackLinks so
        // it fires once: an already-tracked target just marks the link done, and
        // a target the user later untracks is not re-added.
        const linksToRecord = [];
        const idsToAutoTrack = [];
        mergers.forEach((merger) => {
          const link = forwardRefileLink(merger);
          if (!link || autoTrackLinksRef.current.has(link.key)) return;
          linksToRecord.push(link.key);
          if (!trackedMergerIdsSet.has(link.relatedId)) {
            idsToAutoTrack.push(link.relatedId);
          }
        });
        if (linksToRecord.length > 0) {
          setAutoTrackLinks((prev) => {
            const next = new Set(prev);
            linksToRecord.forEach((k) => next.add(k));
            return next;
          });
        }
        if (idsToAutoTrack.length > 0) {
          // Add the re-filed matter(s) — which re-runs this effect to fetch their
          // own events and follow any further forward link in the chain.
          //
          // Deliberately NOT added to newlyTrackedIds: unlike a manual track
          // (which marks the merger's existing events seen to avoid a flood), an
          // auto-tracked re-filing must surface as a notification — the whole
          // point is to ping the user that the matter they were following was
          // re-filed. Leaving its events unseen produces that ping.
          setTrackedMergerIds((prev) => {
            const prevSet = new Set(prev);
            const fresh = idsToAutoTrack.filter((id) => !prevSet.has(id));
            return fresh.length ? [...prev, ...fresh] : prev;
          });
        }

        let allFetchedEvents = [];

        // Extract events from individual merger files
        const timelineEventsFromMergers = mergers.flatMap(timelineEventsFromMerger);

        setTimelineEvents(timelineEventsFromMergers);

        // Carry "seen" over to the link-based key for appeal documents already
        // seen under a title-based one, so the change of key doesn't re-announce them.
        setSeenEventKeys((prev) => {
          const migrated = timelineEventsFromMergers
            .filter((e) => !prev.has(getEventKey(e)))
            .filter((e) => getLegacyEventKeys(e).some((k) => prev.has(k)))
            .map(getEventKey);
          if (migrated.length === 0) return prev;
          const next = new Set(prev);
          migrated.forEach((k) => next.add(k));
          return next;
        });
        allFetchedEvents = [...allFetchedEvents, ...timelineEventsFromMergers];

        // Synthesize upcoming events directly from individual merger data for tracked mergers.
        // These per-merger files are already fetched above, so we derive determination,
        // consultation, and competition-concerns due dates from them rather than fetching the
        // separate upcoming-events.json feed. This avoids an extra network request on every page
        // (TrackingProvider wraps the whole app) and is not subject to that feed's 60-day window,
        // so events whose deadline is months away (e.g. Phase 2 determinations) still surface.
        const now = new Date();
        const syntheticUpcomingEvents = mergers.flatMap((merger) => upcomingEventsFromMerger(merger, now));

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
  }, [trackedMergerIds, trackedMergerIdsSet, newlyTrackedIds, newlyTrackedIdsSet, refreshCount]);

  // Fetch industry-follow events whenever the set of followed industries changes.
  // Unlike merger tracking (which surfaces every timeline event), following an
  // industry only flags two things: a new merger filed in it, and a new
  // determination published for one of its mergers. These are derived from the
  // lightweight merger summaries in the industry division files
  // (notification_date / determination_date on each), so no per-merger fetch
  // is needed.
  useEffect(() => {
    const fetchIndustryEvents = async () => {
      if (trackedIndustryCodes.length === 0) {
        setIndustryEvents([]);
        return;
      }

      try {
        // fetchIndustryNode reads through dataCache, so several followed
        // industries under the same ANZSIC division cost one request between
        // them rather than one each.
        const industryPromises = trackedIndustryCodes.map((code) =>
          fetchIndustryNode(code)
            .then((data) => ({ code, data }))
            .catch(() => ({ code, data: null }))
        );

        const results = await Promise.all(industryPromises);

        const derived = results.flatMap(({ code, data }) => industryEventsFromNode(code, data));

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
  }, [trackedIndustryCodesKey, newlyTrackedIndustryCodes, newlyTrackedIndustryCodesSet, refreshCount]);

  // Auto-track matters that reach Phase 2 when the user has opted in. Fetches the
  // Phase 2 feed and tracks every current matter not yet acted on. Mirrors the
  // forward re-file auto-tracking: each matter is recorded in autoTrackedPhase2Ids
  // so it is added exactly once — a matter the user later untracks stays untracked,
  // while a matter that reaches Phase 2 after the setting was enabled is picked up
  // on the next load. Their existing events are marked seen (like a manual track)
  // so enabling the setting doesn't flood the notification panel with historical
  // milestones; future milestones (NOCC, determination) still surface.
  useEffect(() => {
    if (!autoTrackPhase2) return;
    let cancelled = false;

    const run = async () => {
      try {
        const res = await fetch(API_ENDPOINTS.phase2);
        if (!res.ok || cancelled) return;
        const data = await res.json();
        if (cancelled) return;

        const current = (data && data.current) || [];
        const currentlyTracked = new Set(trackedMergerIdsRef.current);
        const idsToRecord = [];
        const idsToTrack = [];
        current.forEach((matter) => {
          const id = matter && matter.merger_id;
          if (!id || autoTrackedPhase2IdsRef.current.has(id)) return;
          idsToRecord.push(id);
          if (!currentlyTracked.has(id)) idsToTrack.push(id);
        });

        if (idsToRecord.length > 0) {
          setAutoTrackedPhase2Ids((prev) => {
            const next = new Set(prev);
            idsToRecord.forEach((id) => next.add(id));
            return next;
          });
        }
        if (idsToTrack.length > 0) {
          setNewlyTrackedIds((ids) => [...ids, ...idsToTrack]);
          setTrackedMergerIds((prev) => {
            const prevSet = new Set(prev);
            const fresh = idsToTrack.filter((id) => !prevSet.has(id));
            return fresh.length ? [...prev, ...fresh] : prev;
          });
        }
      } catch (err) {
        console.error('Failed to auto-track Phase 2 matters:', err);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [autoTrackPhase2, refreshCount]);

  // Persist the Phase 2 auto-track setting to localStorage.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEYS.AUTO_TRACK_PHASE2, autoTrackPhase2 ? 'true' : 'false');
    } catch (e) {
      console.error('Failed to save auto-track Phase 2 setting:', e);
    }
  }, [autoTrackPhase2]);

  // Persist the set of auto-tracked Phase 2 IDs to localStorage.
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEYS.AUTO_TRACK_PHASE2_IDS,
        JSON.stringify(Array.from(autoTrackedPhase2Ids))
      );
    } catch (e) {
      console.error('Failed to save auto-tracked Phase 2 IDs:', e);
    }
  }, [autoTrackedPhase2Ids]);

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

  // Persist the set of auto-tracked re-file links to localStorage.
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEYS.AUTO_TRACK_LINKS,
        JSON.stringify(Array.from(autoTrackLinks))
      );
    } catch (e) {
      console.error('Failed to save auto-track links:', e);
    }
  }, [autoTrackLinks]);

  const trackMerger = useCallback((mergerId) => {
    setTrackedMergerIds((prev) => {
      const prevSet = new Set(prev);
      if (prevSet.has(mergerId)) return prev;
      // Mark this as a newly tracked merger so we can auto-mark its events as seen
      setNewlyTrackedIds((ids) => [...ids, mergerId]);
      pingFeatureEvent(trackMergerEvent(mergerId));
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
      pingFeatureEvent(trackMergerEvent(mergerId));
      return [...prev, mergerId];
    });
  }, []);

  const isIndustryTracked = useCallback((code) => {
    return trackedIndustryCodesSet.has(code);
  }, [trackedIndustryCodesSet]);

  const trackIndustry = useCallback((code, name) => {
    setTrackedIndustries((prev) => {
      if (prev.some((i) => i.code === code)) return prev;
      setNewlyTrackedIndustryCodes((codes) => [...codes, code]);
      pingFeatureEvent(trackIndustryEvent(code));
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
      pingFeatureEvent(trackIndustryEvent(code));
      return [...prev, { code, name: name || code }];
    });
  }, []);

  const toggleAutoTrackPhase2 = useCallback(() => {
    setAutoTrackPhase2((prev) => !prev);
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

  // Fetch every followed file again. Industry division files are held in
  // dataCache for the life of the page, so theirs are dropped first.
  const refreshEvents = useCallback(() => {
    trackedIndustryCodes.forEach((code) => dataCache.clear(industryDivisionCacheKey(code)));
    setRefreshCount((n) => n + 1);
  }, [trackedIndustryCodes]);

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

  // Industry-follow events, deduped and sorted most-recent-first. A merger the
  // reader tracks individually is left out: its own timeline already carries
  // the filing and the determination, and announcing them a second time under
  // the industry is a double notification. The individual merger wins.
  const trackedIndustryEvents = useMemo(() => {
    const unique = dedupeEvents(industryEvents)
      .filter((event) => !trackedMergerIdsSet.has(event.merger_id));
    return unique.sort((a, b) => new Date(b.date) - new Date(a.date));
  }, [industryEvents, trackedMergerIdsSet]);

  // Mark the industry events left out above as seen, so untracking the merger
  // later doesn't resurface news the reader already had through tracking it.
  useEffect(() => {
    const shadowed = industryEvents.filter((event) => trackedMergerIdsSet.has(event.merger_id));
    if (shadowed.length > 0) markEventsAsSeen(shadowed);
  }, [industryEvents, trackedMergerIdsSet, markEventsAsSeen]);

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
    autoTrackPhase2,
    toggleAutoTrackPhase2,
    markEventAsSeen,
    markEventsAsSeen,
    isEventSeen,
    unseenEvents,
    unseenCount,
    trackedEvents,
    loading,
    getEventKey,
    // For browser notifications (push/PushSync.jsx), which hands the service
    // worker what it needs to tell news from what the panel already shows.
    seenEventKeys,
    autoTrackLinks,
    autoTrackedPhase2Ids,
    refreshEvents,
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
    autoTrackPhase2,
    toggleAutoTrackPhase2,
    markEventAsSeen,
    markEventsAsSeen,
    isEventSeen,
    unseenEvents,
    unseenCount,
    trackedEvents,
    loading,
    seenEventKeys,
    autoTrackLinks,
    autoTrackedPhase2Ids,
    refreshEvents,
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
