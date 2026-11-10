// Browser notifications, the page's side: turning them on and off, and keeping
// the browser's Firebase Cloud Messaging topics in step with the follow list.
//
// Strictly optional. Following, the notification panel and everything else
// work the same without it: a browser that can't do push, or where
// notifications are blocked, is just never subscribed.
//
// The Firebase SDK is only loaded once someone turns notifications on (or
// comes back with them on), so it costs nothing otherwise.

import { FIREBASE_VAPID_KEY, FIREBASE_WEB_CONFIG, PUSH_TOPICS_ENDPOINT } from '../config.js';
import { clearPushState } from './store.js';

const ENABLED_KEY = 'merger_tracker_push';
// The topics this browser's token was last subscribed to: {token, topics}.
const SYNCED_KEY = 'merger_tracker_push_topics';

// The Worker makes one call to Google per topic, and a Worker request may
// make only so many, so a long list goes over in several requests.
const TOPICS_PER_REQUEST = 40;

const read = (key) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};
const write = (key, value) => {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    // Private mode and the like: notifications just won't survive a reload.
  }
};

/** Whether this build has the Firebase web config it needs. */
export function pushConfigured(config = FIREBASE_WEB_CONFIG, vapidKey = FIREBASE_VAPID_KEY) {
  return Boolean(config && config.apiKey && config.appId && config.projectId && vapidKey);
}

/** Whether this browser can take push at all. */
export function pushSupported() {
  return typeof window !== 'undefined'
    && 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window
    && 'indexedDB' in window;
}

/**
 * An iPhone or iPad browsing in Safari: push is there, but only for a site
 * added to the Home Screen.
 */
export function needsHomeScreen() {
  if (typeof window === 'undefined') return false;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true;
  return ios && !standalone && !('PushManager' in window);
}

export const pushPermission = () => (pushSupported() ? Notification.permission : 'default');
export const pushEnabled = () => read(ENABLED_KEY) === 'true';

async function workerRegistration() {
  const registration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
  const worker = registration.installing || registration.waiting;
  if (!registration.active && worker) {
    await new Promise((resolve) => {
      worker.addEventListener('statechange', () => worker.state === 'activated' && resolve());
    });
  }
  return registration;
}

async function firebase() {
  const [{ getApps, initializeApp }, messagingSdk] = await Promise.all([
    import('firebase/app'),
    import('firebase/messaging'),
  ]);
  const app = getApps()[0] || initializeApp(FIREBASE_WEB_CONFIG);
  return { sdk: messagingSdk, messaging: messagingSdk.getMessaging(app) };
}

/** This browser's FCM token: registers the service worker, and renews the token when due. */
export async function pushToken() {
  const registration = await workerRegistration();
  const { sdk, messaging } = await firebase();
  return sdk.getToken(messaging, { vapidKey: FIREBASE_VAPID_KEY, serviceWorkerRegistration: registration });
}

/**
 * Ask for permission (call it from a click) and get a token. Resolves to the
 * token, or null when the browser said no.
 */
export async function enablePush() {
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') return null;
  const token = await pushToken();
  write(ENABLED_KEY, 'true');
  return token;
}

/** Turn notifications off: the token is deleted, which ends its topic subscriptions. */
export async function disablePush() {
  write(ENABLED_KEY, null);
  write(SYNCED_KEY, null);
  try {
    const { sdk, messaging } = await firebase();
    await sdk.deleteToken(messaging);
  } catch (err) {
    console.error('Failed to delete the notification token:', err);
  }
  await clearPushState().catch(() => {});
  const registration = await navigator.serviceWorker.getRegistration('/');
  if (registration) await registration.unregister();
}

/** What to add and remove to go from the topics last synced to *wanted*. */
export function topicChanges(synced, token, wanted) {
  const have = synced && synced.token === token ? synced.topics || [] : [];
  const want = new Set(wanted);
  const had = new Set(have);
  return {
    add: wanted.filter((topic) => !had.has(topic)),
    remove: have.filter((topic) => !want.has(topic)),
  };
}

/** Subscribe *token* to exactly the topics in *wanted*, through the Worker. */
export async function syncTopics(token, wanted, { post = fetch } = {}) {
  let synced = null;
  try {
    synced = JSON.parse(read(SYNCED_KEY) || 'null');
  } catch {
    synced = null;
  }
  const { add, remove } = topicChanges(synced, token, wanted);
  const changes = [...add.map((t) => ['add', t]), ...remove.map((t) => ['remove', t])];
  const done = new Set(synced && synced.token === token ? synced.topics : []);
  for (let i = 0; i < changes.length; i += TOPICS_PER_REQUEST) {
    const batch = changes.slice(i, i + TOPICS_PER_REQUEST);
    const body = {
      token,
      add: batch.filter(([op]) => op === 'add').map(([, t]) => t),
      remove: batch.filter(([op]) => op === 'remove').map(([, t]) => t),
    };
    const response = await post(PUSH_TOPICS_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`Topic sync failed: HTTP ${response.status}`);
    // Recorded batch by batch, so a failure part way only redoes the rest.
    body.add.forEach((t) => done.add(t));
    body.remove.forEach((t) => done.delete(t));
    write(SYNCED_KEY, JSON.stringify({ token, topics: [...done].sort() }));
  }
  if (!changes.length && (!synced || synced.token !== token)) {
    write(SYNCED_KEY, JSON.stringify({ token, topics: [] }));
  }
}
