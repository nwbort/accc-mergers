import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTracking } from './TrackingContext';
import { getEventKey } from '../utils/trackedEvents';
import { pushTopics } from '../push/topics';
import { updatePushState } from '../push/store';
import {
  disablePush,
  enablePush,
  needsHomeScreen,
  pushConfigured,
  pushEnabled,
  pushPermission,
  pushSupported,
  pushToken,
  syncTopics,
} from '../push/webPush';

// Browser notifications for what you follow. Optional on top of following:
// with them off, blocked or unsupported, everything works as before and the
// notification panel is still where news shows up.
//
// While they're on, this keeps two things in step with the follow list: the
// browser's Firebase topics (through the signup Worker), and the copy of the
// follow state the service worker reads (src/push/store.js), including every
// event key the panel has already shown, so a notification never repeats it.

const PushContext = createContext(null);

// How many already-shown event keys the service worker is handed.
const MAX_KNOWN = 5000;

/**
 * - unavailable: this build or this browser can't do it; nothing is shown
 * - home-screen: an iPhone/iPad in Safari, which needs the site installed
 * - blocked: the browser has notifications for this site switched off
 * - off / on
 */
function initialStatus() {
  if (!pushConfigured()) return 'unavailable';
  if (!pushSupported()) return needsHomeScreen() ? 'home-screen' : 'unavailable';
  if (pushPermission() === 'denied') return 'blocked';
  return pushEnabled() && pushPermission() === 'granted' ? 'on' : 'off';
}

export function PushProvider({ children }) {
  const {
    trackedMergerIds,
    trackedIndustries,
    trackedIndustryCodes,
    trackedEvents,
    trackedIndustryEvents,
    seenEventKeys,
    autoTrackPhase2,
    autoTrackLinks,
    autoTrackedPhase2Ids,
    loading,
    refreshEvents,
  } = useTracking();

  const [status, setStatus] = useState(initialStatus);
  const [token, setToken] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Coming back with notifications on: renew the token if it's due.
  useEffect(() => {
    if (status !== 'on' || token) return;
    let cancelled = false;
    pushToken()
      .then((t) => !cancelled && setToken(t))
      .catch((err) => console.error('Failed to renew the notification token:', err));
    return () => {
      cancelled = true;
    };
  }, [status, token]);

  const topicsKey = useMemo(
    () => pushTopics({ trackedMergerIds, trackedIndustryCodes, autoTrackPhase2 }).join(','),
    [trackedMergerIds, trackedIndustryCodes, autoTrackPhase2],
  );

  useEffect(() => {
    if (status !== 'on' || !token) return;
    const timer = setTimeout(() => {
      syncTopics(token, topicsKey ? topicsKey.split(',') : [])
        .catch((err) => console.error('Failed to update notification topics:', err));
    }, 1000);
    return () => clearTimeout(timer);
  }, [status, token, topicsKey]);

  // The service worker's copy of the follow state. Not while the panel is
  // still loading, or what it has shown would be missing from `known`.
  useEffect(() => {
    if (status !== 'on' || loading) return;
    const timer = setTimeout(() => {
      const shown = [...trackedEvents, ...trackedIndustryEvents].map(getEventKey);
      updatePushState((current) => ({
        enabled: true,
        trackedMergerIds,
        trackedIndustries,
        seen: [...seenEventKeys],
        known: [...new Set([...(current.known || []), ...shown])].slice(-MAX_KNOWN),
        autoTrackPhase2,
        autoTrackLinks: [...autoTrackLinks],
        autoTrackedPhase2Ids: [...autoTrackedPhase2Ids],
      })).catch((err) => console.error('Failed to save notification state:', err));
    }, 500);
    return () => clearTimeout(timer);
  }, [
    status,
    loading,
    trackedMergerIds,
    trackedIndustries,
    trackedEvents,
    trackedIndustryEvents,
    seenEventKeys,
    autoTrackPhase2,
    autoTrackLinks,
    autoTrackedPhase2Ids,
  ]);

  // A push while the site is in view: the service worker asks the page to
  // look again instead of showing a notification.
  useEffect(() => {
    if (status !== 'on' || !navigator.serviceWorker) return;
    const onMessage = (event) => {
      if (event.data && event.data.type === 'mergers-fyi-refresh') refreshEvents();
    };
    navigator.serviceWorker.addEventListener('message', onMessage);
    return () => navigator.serviceWorker.removeEventListener('message', onMessage);
  }, [status, refreshEvents]);

  const turnOn = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const t = await enablePush();
      if (t) {
        setToken(t);
        setStatus('on');
      } else {
        setStatus(pushPermission() === 'denied' ? 'blocked' : 'off');
      }
    } catch (err) {
      console.error('Failed to turn on notifications:', err);
      setError('Couldn’t turn notifications on. Please try again.');
    } finally {
      setBusy(false);
    }
  }, []);

  const turnOff = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await disablePush();
    } catch (err) {
      console.error('Failed to turn off notifications:', err);
    } finally {
      setToken(null);
      setStatus(pushPermission() === 'denied' ? 'blocked' : 'off');
      setBusy(false);
    }
  }, []);

  const value = useMemo(
    () => ({ status, busy, error, turnOn, turnOff }),
    [status, busy, error, turnOn, turnOff],
  );

  return <PushContext.Provider value={value}>{children}</PushContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePush() {
  return useContext(PushContext);
}
