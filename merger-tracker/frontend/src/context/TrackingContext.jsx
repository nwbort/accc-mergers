import { createContext, useContext, useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { API_ENDPOINTS } from '../config';

const TrackingContext = createContext(null);

const STORAGE_KEYS = {
  TRACKED_MERGERS: 'merger_tracker_tracked',
  TRACKED_INDUSTRIES: 'merger_tracker_tracked_industries',
  SEEN_EVENTS: 'merger_tracker_seen_events',
  // Forward re-file links ("sourceId->relatedId") we've already auto-tracked,
  // so each is acted on exactly once. See the auto-track logic in the fetch
  // effect for why this is persisted.
  AUTO_TRACK_LINKS: 'merger_tracker_auto_track_links',
  // Merger IDs from the Phase 2 feed we've already reconciled, so a merger that
  // becomes Phase 2 is auto-tracked exactly once. See the Phase 2 auto-track
  // effect for the "going forward" baseline semantics.
  PHASE_2_SEEN: 'merger_tracker_phase2_seen',
  // Marks that the Phase 2 baseline has been seeded at least once. Until this is
  // set, the very first feed load records the existing Phase 2 mergers as the
  // baseline WITHOUT tracking them — so auto-tracking only applies going forward.
  PHASE_2_INITIALIZED: 'merger_tracker_phase2_initialized',
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

  // Merger IDs from the Phase 2 feed we've already reconciled. A merger only
  // gets auto-tracked the first time it appears here as Phase 2; once recorded
  // it's never re-added, so a user who untracks an auto-tracked Phase 2 matter
  // keeps it untracked. Mirrored in a ref so the fetch effect can read the
  // latest set without depending on it.
  const [phase2SeenIds, setPhase2SeenIds] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEYS.PHASE_2_SEEN);
      return stored ? new Set(JSON.parse(stored)) : new Set();
    } catch (err) {
      console.error('Failed to read Phase 2 seen IDs from localStorage:', err);
      return new Set();
    }
  });
  const phase2SeenIdsRef = useRef(phase2SeenIds);
  useEffect(() => {
    phase2SeenIdsRef.current = phase2SeenIds;
  }, [phase2SeenIds]);

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
          const related = merger && merger.related_merger;
          if (!related || !FORWARD_REFILE_RELATIONSHIPS.has(related.relationship)) return;
          const relatedId = related.merger_id;
          if (!relatedId) return;
          const linkKey = `${merger.merger_id}->${relatedId}`;
          if (autoTrackLinksRef.current.has(linkKey)) return;
          linksToRecord.push(linkKey);
          if (!trackedMergerIdsSet.has(relatedId)) {
            idsToAutoTrack.push(relatedId);
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
  }, [trackedMergerIds, trackedMergerIdsSet, newlyTrackedIds, newlyTrackedIdsSet]);

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

  // Auto-track mergers that become Phase 2 — but only going forward. On mount we
  // fetch the lightweight Phase 2 feed (every notification referred to the
  // ACCC's detailed Phase 2 review) and diff it against phase2SeenIds.
  //
  // The first ever load seeds the baseline: existing Phase 2 mergers are recorded
  // as "seen" WITHOUT being tracked, so enabling this feature doesn't retroactively
  // pull a user's whole back catalogue into their tracked list. After that, any
  // merger appearing in the feed for the first time is auto-tracked, surfacing the
  // referral as a notification. Each ID is reconciled exactly once: a Phase 2
  // matter the user later untracks is not silently re-added.
  //
  // Runs once on mount — the feed is regenerated server-side, so a long-lived tab
  // picks up new referrals on its next load rather than via polling.
  useEffect(() => {
    let cancelled = false;

    const reconcilePhase2 = async () => {
      let feed;
      try {
        const res = await fetch(API_ENDPOINTS.phase2Mergers);
        if (!res.ok) return;
        feed = await res.json();
      } catch (err) {
        console.error('Failed to fetch Phase 2 mergers feed:', err);
        return;
      }
      if (cancelled) return;

      const feedIds = (feed?.mergers || [])
        .map((m) => m.merger_id)
        .filter(Boolean);

      const seen = phase2SeenIdsRef.current;
      const newIds = feedIds.filter((id) => !seen.has(id));

      const initialized = localStorage.getItem(STORAGE_KEYS.PHASE_2_INITIALIZED);
      if (!initialized) {
        // First run: the current feed (whatever it is, possibly empty) is the
        // baseline. Mark initialized and record the current IDs as seen WITHOUT
        // tracking them, so auto-tracking only fires for future referrals.
        localStorage.setItem(STORAGE_KEYS.PHASE_2_INITIALIZED, '1');
        if (newIds.length > 0) {
          setPhase2SeenIds((prev) => {
            const next = new Set(prev);
            newIds.forEach((id) => next.add(id));
            return next;
          });
        }
        return;
      }

      if (newIds.length === 0) return;

      // Record every newly-seen Phase 2 ID so each is reconciled exactly once.
      setPhase2SeenIds((prev) => {
        const next = new Set(prev);
        newIds.forEach((id) => next.add(id));
        return next;
      });

      // Track any merger that newly became Phase 2. Deliberately NOT added to
      // newlyTrackedIds: like an auto-tracked re-filing, the point is to ping the
      // user that the matter reached Phase 2, so its events stay unseen.
      setTrackedMergerIds((prev) => {
        const prevSet = new Set(prev);
        const fresh = newIds.filter((id) => !prevSet.has(id));
        return fresh.length ? [...prev, ...fresh] : prev;
      });
    };

    reconcilePhase2();
    return () => {
      cancelled = true;
    };
    // Mount-only: phase2SeenIds is read through a ref to avoid re-running.
  }, []);

  // Persist the set of reconciled Phase 2 merger IDs to localStorage.
  useEffect(() => {
    try {
      localStorage.setItem(
        STORAGE_KEYS.PHASE_2_SEEN,
        JSON.stringify(Array.from(phase2SeenIds))
      );
    } catch (e) {
      console.error('Failed to save Phase 2 seen IDs:', e);
    }
  }, [phase2SeenIds]);

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
