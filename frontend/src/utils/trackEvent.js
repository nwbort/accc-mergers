import { EVENT_ENDPOINT } from '../config';

// Privacy-preserving feature-usage ping (see workers/mergers-digest-signup's
// POST /event). Each call just increments a per-day aggregate counter
// server-side, keyed only on the event type — no cookies, no per-user or
// per-merger identifiers are ever sent or stored, so usage can never be
// tied back to an individual visitor.
//
// To track a new feature: add its name here and call pingFeatureEvent(...)
// at the point of use. It also has to be added to ALLOWED_EVENT_TYPES in
// workers/mergers-digest-signup/src/index.js, or the Worker rejects it.
export const FEATURE_EVENTS = {
  TRACK_MERGER: 'track_merger',
};

// Fire-and-forget: must never throw or block the caller, since this is
// incidental to whatever feature the user is actually using.
export function pingFeatureEvent(type) {
  try {
    fetch(EVENT_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    // ignore — a feature-usage ping must never break the feature it's pinging about
  }
}
