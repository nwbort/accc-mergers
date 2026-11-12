// The service worker behind browser notifications, served as /sw.js.
//
// It does one thing: when Firebase Cloud Messaging delivers a push (a bare
// "check now" from scripts/push/fcm.py, the same message the Android app
// gets), it runs the follow check and shows what's new. No fetch handler and
// no caching: the site works exactly as it does without it.
//
// Built on its own, as one classic script, by the serviceWorker() plugin in
// vite.config.js. It doesn't load the Firebase SDK: a push from FCM is an
// ordinary Web Push, its payload the message's data.

import { describeNews, findNews, MAX_NOTIFIED } from './news.js';
import { readPushState, updatePushState } from './store.js';

const ICON = '/android-chrome-192x192.png';
// One notification at a time: a newer one replaces it.
const TAG = 'mergers-fyi-follow';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

async function onPush() {
  const state = await readPushState();
  if (!state || !state.enabled) return;

  // The site is open and in view: its own panel picks the news up, so ask it
  // to look again rather than notify over it.
  const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  const visible = windows.filter((client) => client.visibilityState === 'visible');
  if (visible.length) {
    visible.forEach((client) => client.postMessage({ type: 'mergers-fyi-refresh' }));
    return;
  }

  const { news, quiet } = await findNews(state);
  const remember = [...quiet, ...news.map((item) => item.key)];
  if (remember.length) {
    await updatePushState((current) => ({
      notified: [...new Set([...(current.notified || []), ...remember])].slice(-MAX_NOTIFIED),
    }));
  }
  if (!news.length) return;

  const { title, body, url } = describeNews(news);
  await self.registration.showNotification(title, {
    body,
    icon: ICON,
    tag: TAG,
    renotify: true,
    data: { url },
  });
}

self.addEventListener('push', (event) => {
  event.waitUntil(onPush().catch((err) => console.error('Follow check failed:', err)));
});

async function openUrl(url) {
  const target = new URL(url, self.location.origin).href;
  const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
  const open = windows.find((client) => new URL(client.url).origin === self.location.origin);
  if (open) {
    await open.focus();
    return open.navigate(target).catch(() => self.clients.openWindow(target));
  }
  return self.clients.openWindow(target);
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(openUrl((event.notification.data && event.notification.data.url) || '/'));
});
