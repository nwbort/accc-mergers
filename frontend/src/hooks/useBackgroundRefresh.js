import { useEffect } from 'react';
import { dataCache } from '../utils/dataCache';

// How stale a currently-displayed resource must be before a background
// refresh bothers re-fetching it. The pipeline updates a few times a day at
// most, so this just keeps rapid tab-switching from re-fetching everything.
const STALE_MS = 5 * 60 * 1000;

// Fallback poll interval, for a tab left open and focused for a long
// stretch without ever losing and regaining visibility.
const POLL_INTERVAL_MS = 15 * 60 * 1000;

/**
 * Periodically re-fetches whatever data is currently on screen, so a tab
 * left open picks up freshly published data without a full page reload.
 * Triggers on regaining visibility (a user tabbing back in — the common
 * case) and on a long-interval timer as a fallback for a tab that stays
 * focused for a long stretch. Only revalidates resources stale by more than
 * STALE_MS, and only ones useFetchData has registered as on screen (see
 * dataCache.registerActive) — components subscribed to those cache keys
 * re-render automatically if the fetched data actually changed.
 *
 * Mounted once, for the app's lifetime, from App.jsx.
 */
export function useBackgroundRefresh() {
  useEffect(() => {
    const revalidateStale = () => {
      const now = Date.now();
      for (const [key, url] of dataCache.activeEntries()) {
        const fetchedAt = dataCache.fetchedAt(key);
        // Never fetched yet — the mounting component's own fetch will
        // populate it; revalidating too would just duplicate that request.
        if (fetchedAt == null) continue;
        if (now - fetchedAt < STALE_MS) continue;
        dataCache.revalidate(key, url);
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') revalidateStale();
    };

    document.addEventListener('visibilitychange', handleVisibility);
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') revalidateStale();
    }, POLL_INTERVAL_MS);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      clearInterval(interval);
    };
  }, []);
}
