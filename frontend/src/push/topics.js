// The Firebase Cloud Messaging topics a browser subscribes to for what it
// follows. The same names as the Android app's notify/Push.kt and the site's
// scripts/push/fcm.py, which sends to them: change all three or none.
//
// A topic is per *file*: a merger's detail file, or an industry division file
// (every followed code under one division shares it). `list` covers new
// filings and which matters are in Phase 2, which only "follow every Phase 2
// matter" needs. `all` is what fcm.py sends in place of the rest when a deploy
// changes too much to list.

import { divisionFileStem } from '../utils/industryDivision.js';

export const ALL = 'all';
export const LIST = 'list';

export const mergerTopic = (id) => `merger-${id}`;
export const industryTopic = (code) => `industry-${divisionFileStem(code)}`;

/** The sorted topic names for a follow list; none when nothing is followed. */
export function pushTopics({ trackedMergerIds = [], trackedIndustryCodes = [], autoTrackPhase2 = false }) {
  if (!trackedMergerIds.length && !trackedIndustryCodes.length && !autoTrackPhase2) return [];
  const topics = new Set([ALL]);
  if (autoTrackPhase2) topics.add(LIST);
  trackedMergerIds.forEach((id) => topics.add(mergerTopic(id)));
  trackedIndustryCodes.forEach((code) => topics.add(industryTopic(code)));
  return [...topics].sort();
}
