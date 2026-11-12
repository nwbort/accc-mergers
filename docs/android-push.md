# Push notifications (Android app and browsers)

The Android app ([nwbort/accc-mergers-app](https://github.com/nwbort/accc-mergers-app))
used to learn about changes to what it follows only by checking mergers.fyi
every two hours. Now the site tells it, through Firebase Cloud Messaging (FCM),
within a few minutes of each deploy. Both FCM and the Actions minutes are free.

## How it works

- **Topics, not devices.** Each phone subscribes to one FCM topic per thing it
  follows: `merger-MN-01016`, `industry-G` (the `industries/G.json` file, so
  every followed industry under that division), `list` (new filings and
  Phase 2 changes, for the app's "every new filing" and "follow every Phase 2
  matter" options) and `all`. Google holds the topic lists. Nothing here knows
  who follows what, so the site still has no backend and no user data.
- **What changed.** `.github/workflows/android-push.yml` runs after the
  pipeline and the tribunal scrape (and every three hours as a catch-all). It
  waits for Cloudflare Pages to serve the checkout's data, then compares the
  live `data/manifest.json` with the one it saw last time (kept in the
  Actions cache) and sends one message to the topic of each changed file
  (`scripts/push/fcm.py`). A deploy that changes more than 100 of them sends
  one `all` message instead.
- **What a message says.** Only "check now". The app runs its usual check
  (`CheckWorker`, the one its schedule runs), which decides what's news, so the
  rules for that stay in one place. A change that isn't news costs a check that
  finds nothing.
- **Fallback.** The app keeps its schedule: every 12 hours once push has
  worked on the phone, every 2 hours until then, and on a phone without Google
  Play services.

The topic names are shared between `scripts/push/fcm.py`, the app's
`notify/Push.kt` and the site's `frontend/src/push/topics.js`, and all three
test suites pin them: change all of them or none.

## Browsers

The site offers the same thing to browsers, as an option on top of following,
and asks as little as it can: the browser's own permission prompt appears once,
on the next follow (from that click, since browsers only prompt in response to
one), and the notification panel shows an "Enable browser notifications"
button with an × until the × is pressed (remembered in localStorage). While
they're on, the panel says nothing about them. There's no "turn off" on the
site: blocking notifications in the browser's settings is how, and the next
visit after that deletes the browser's token, ending its topic subscriptions. Following doesn't depend on
it. With it off, blocked by the browser, or not supported (Safari on an iPhone
or iPad needs the site added to the Home Screen first), the follow list and
the panel work exactly as they always have.

- **Same topics, same message.** A browser that turns it on gets an FCM token
  (`frontend/src/push/webPush.js`, with Firebase's web SDK, loaded only then)
  and is subscribed to the topics for what it follows. The page keeps them in
  step as the follow list changes (`context/PushContext.jsx`). FCM's web SDK
  can't subscribe a token to a topic itself, so the signup Worker's
  `POST /push/topics` does it, passing each change to Google and keeping
  nothing (`workers/mergers-digest-signup/src/push.js`).
- **The check runs in a service worker.** `/sw.js` (`frontend/src/push/sw.js`,
  built on its own by `vite.config.js`) wakes on the message and runs the follow
  check (`push/news.js`) with the same event keys as the notification panel
  (`utils/trackedEvents.js`). The follow list lives in localStorage, which a
  service worker can't read, so the page mirrors what it needs into IndexedDB
  (`push/store.js`), including every event the panel has already shown, so a
  notification never repeats one. With the site open in view it shows nothing
  and has the page refresh its panel instead. It has no fetch handler and
  caches nothing.
- **A check that finds nothing shows nothing.** Browsers allow a few of those
  but not many: Safari may drop the subscription after a few, and Chrome may
  show a generic "updated in the background". Messages are per file, so this
  is mostly a deploy that rewrites every file, which sends `all`.

## Setup

Once, in the [Firebase console](https://console.firebase.google.com/) (the free
Spark plan is enough):

1. **Create a project.** Analytics isn't needed, so turn it off.
2. **Add an Android app** with package name `fyi.mergers.app`. Skip the SDK
   steps but download **`google-services.json`**. Its values aren't secret
   (they're built into every APK), so either:
   - commit it to the app repo as `app/google-services.json`, or
   - add its contents as the app repo's `GOOGLE_SERVICES_JSON` secret.

   Without it the app builds as before and just keeps checking every 2 hours.
3. **Make a sending key.** Project settings → Service accounts → *Generate new
   private key*. Add the JSON file's whole contents to **this** repo as the
   `FCM_SERVICE_ACCOUNT` secret. This one *is* secret: it can message every
   phone. Without it the workflow skips.

The first run after that only records the live manifest; messages start with
the next deploy. Phones subscribe the next time the app starts.

For browsers, in the same Firebase project:

4. **Add a Web app** (Project settings → General → Add app → Web). Copy
   `apiKey` and `appId` from the config it shows into `FIREBASE_WEB_CONFIG`
   in `frontend/src/config.js`. Not secret: every browser that loads the site
   gets them.
5. **Make a Web Push key pair** (Project settings → Cloud Messaging → Web
   Push certificates → Generate key pair) and put the public key in
   `FIREBASE_VAPID_KEY` in the same file.
6. **Give the signup Worker the sending key**:
   `cd workers/mergers-digest-signup && npx wrangler secret put FCM_SERVICE_ACCOUNT`,
   pasting the same service account JSON as step 3, then `npm run deploy`.

Until all of 4 and 5 are in, the site shows no switch at all. Without 6 the
switch can't subscribe anything and the site leaves notifications off.

To see what a run would send without sending it:

```bash
python -m scripts.push.fcm --state /tmp/push-state.json --dry-run
```

(The first dry run, with no state file, has nothing to compare with.)
