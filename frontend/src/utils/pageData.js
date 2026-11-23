// The fetch each page's first render waits on, as [cacheKey, url]: the pair
// the page passes to useFetchData, and that routes.js preloads into dataCache
// before the app mounts over a prerendered page. One definition per page, so
// the preload always fills the very entry the page then reads — a key that
// drifted would just mean a wasted fetch and the spinner back.
//
// Its own module rather than exported from the pages: routes.js must not
// import a page, or the page would be in the main bundle, not its own chunk.
import { API_ENDPOINTS } from '../config';
import { MERGERS_LIST_KEY } from './mergerList';
import { industryDivisionCacheKey } from './industryNode';

/** stats.json, as the dashboard (and the party and industry pages) cache it. */
export const DASHBOARD_STATS_KEY = 'dashboard-stats';

export const dashboardStatsFetch = () => [DASHBOARD_STATS_KEY, API_ENDPOINTS.stats];

export const mergersListFetch = () => [MERGERS_LIST_KEY, API_ENDPOINTS.mergersList];

/** A merger's detail file. Ids are upper-case in the data, whatever the URL says. */
export function mergerDetailFetch(id) {
  const normalized = id.toUpperCase();
  return [`merger-${normalized}`, API_ENDPOINTS.mergerDetail(normalized)];
}

/** The ANZSIC division file holding an industry node. */
export function industryDivisionFetch(code) {
  return [industryDivisionCacheKey(code), API_ENDPOINTS.industryDivision(code)];
}

/** The shard bucket holding a party's record. */
export function partyShardFetch(id) {
  const url = API_ENDPOINTS.partyShard(id);
  return [`party-shard-${url}`, url];
}
