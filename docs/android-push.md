# Android push notifications

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

The topic names are shared between `scripts/push/fcm.py` and the app's
`notify/Push.kt`, and both test suites pin them: change both or neither.

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

To see what a run would send without sending it:

```bash
python -m scripts.push.fcm --state /tmp/push-state.json --dry-run
```

(The first dry run, with no state file, has nothing to compare with.)
