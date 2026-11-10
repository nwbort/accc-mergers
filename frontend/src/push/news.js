// What a browser notification announces: the service worker's half of the
// follow check, run when a push says "check now" (see sw.js).
//
// The page decides what's news for the notification panel (TrackingContext);
// this reaches the same answer from the same files, with the same event keys
// (utils/trackedEvents.js), so the two can't disagree. Anything the panel has
// already shown, whether or not it was marked seen, is not announced: the
// page mirrors those keys as `known`. What this has announced it remembers as
// `notified`.

import { industryDivisionUrl } from '../utils/industryDivision.js';
import { readIndustryNode } from '../utils/industryNode.js';
import {
  dedupeEvents,
  forwardRefileLink,
  getEventKey,
  getLegacyEventKeys,
  industryEventsFromNode,
  timelineEventsFromMerger,
  upcomingEventsFromMerger,
} from '../utils/trackedEvents.js';

// How many announced keys to remember. They only need to outlive the page's
// next visit, which folds them into `known`.
export const MAX_NOTIFIED = 2000;

/** Fetch a data file past the HTTP cache, or null. */
export async function fetchJson(url) {
  try {
    const response = await fetch(url, { cache: 'no-cache' });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    // A missing file is the SPA's index.html with a 200, so a parse failure
    // is a 404 too.
    return null;
  }
}

/**
 * The news in *state* (the record in store.js), and the keys to remember
 * without announcing.
 *
 * Something followed whose every event is unknown here was followed since
 * the page last mirrored the state, and the page marks a new follow's history
 * seen rather than announcing it, so this does the same: `quiet` holds its
 * keys. (An auto-tracked re-filing is the exception the page makes, and is
 * announced here as the re-filing itself.)
 *
 * @returns {Promise<{news: object[], quiet: string[]}>}
 */
export async function findNews(state, { fetch: get = fetchJson, now = new Date() } = {}) {
  const trackedIds = state.trackedMergerIds || [];
  const tracked = new Set(trackedIds);
  const seen = new Set(state.seen || []);
  const skip = new Set([...seen, ...(state.known || []), ...(state.notified || [])]);
  const autoTrackLinks = new Set(state.autoTrackLinks || []);
  const isOld = (event) => skip.has(getEventKey(event)) || getLegacyEventKeys(event).some((k) => seen.has(k));

  const news = [];
  const quiet = [];
  // An item's events: announced, unless none of them is known yet.
  const consider = (events, toItem) => {
    const unique = dedupeEvents(events);
    if (unique.length && !unique.some(isOld)) {
      quiet.push(...unique.map(getEventKey));
      return;
    }
    unique.filter((e) => !isOld(e)).forEach((e) => news.push({ key: getEventKey(e), date: e.date, ...toItem(e) }));
  };

  const mergers = await Promise.all(trackedIds.map((id) => get(`/data/mergers/${id}.json`)));
  mergers.forEach((merger) => {
    if (!merger) return;
    const name = merger.merger_name || merger.merger_id;
    consider(
      [...timelineEventsFromMerger(merger), ...upcomingEventsFromMerger(merger, now)],
      (e) => ({ name, line: e.display_title || e.title, url: `/mergers/${merger.merger_id}` }),
    );
    const link = forwardRefileLink(merger);
    const key = link && `refile_${link.key}`;
    if (link && !autoTrackLinks.has(link.key) && !tracked.has(link.relatedId) && !skip.has(key)) {
      news.push({ key, name, line: `Re-filed as ${link.relatedId}`, url: `/mergers/${link.relatedId}` });
    }
  });

  // One fetch per division file, however many followed codes share it.
  const divisions = new Map();
  const division = (code) => {
    const url = industryDivisionUrl(code);
    if (!divisions.has(url)) divisions.set(url, get(url));
    return divisions.get(url);
  };
  const industries = state.trackedIndustries || [];
  const nodes = await Promise.all(industries.map(({ code }) => division(code).then((p) => readIndustryNode(p, code))));
  industries.forEach(({ code }, i) => {
    // A merger followed in its own right is announced from its own timeline,
    // as the panel does (TrackingContext's trackedIndustryEvents), not twice.
    const events = industryEventsFromNode(code, nodes[i]).filter((e) => !tracked.has(e.merger_id));
    consider(events, (e) => ({
      name: e.industry_name,
      line: `${e.display_title}: ${e.merger_name || e.merger_id}`,
      url: `/mergers/${e.merger_id}`,
    }));
  });

  // "Follow every Phase 2 matter": the page tracks a new one on its next
  // visit (marking its history seen), so the move itself is the news.
  if (state.autoTrackPhase2) {
    const done = new Set(state.autoTrackedPhase2Ids || []);
    const phase2 = await get('/data/phase2.json');
    ((phase2 && phase2.current) || []).forEach((matter) => {
      const id = matter && matter.merger_id;
      const key = `phase2_${id}`;
      if (!id || done.has(id) || tracked.has(id) || skip.has(key)) return;
      // Nothing recorded yet: the setting was only just turned on, and the
      // page hasn't been back to take in the matters already there.
      if (!done.size) {
        quiet.push(key);
        return;
      }
      news.push({ key, name: matter.merger_name || id, line: 'Moved to Phase 2', url: `/mergers/${id}` });
    });
  }

  const unique = [...new Map(news.map((item) => [item.key, item])).values()];
  unique.sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')));
  return { news: unique, quiet };
}

const MAX_LINES = 4;

/**
 * The notification for *news*: one item says itself, several about one thing
 * are listed under its name, otherwise a count over the first few. Opens the
 * page they share, or the dashboard.
 */
export function describeNews(news) {
  const names = new Set(news.map((item) => item.name));
  const urls = new Set(news.map((item) => item.url));
  const url = urls.size === 1 ? news[0].url : '/';
  const oneName = names.size === 1;
  const lines = news.slice(0, MAX_LINES).map((item) => (oneName ? item.line : `${item.name}: ${item.line}`));
  if (news.length > MAX_LINES) lines.push(`and ${news.length - MAX_LINES} more`);
  const title = oneName ? news[0].name : `${news.length} updates on what you follow`;
  return { title, body: lines.join('\n'), url };
}
