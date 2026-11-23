// Every route the app renders, with the page that draws it.
//
// Pages are code-split: each loads its own chunk on demand, so the initial
// bundle carries only the app shell. That chunk is also why a prerendered page
// used to flash: createRoot replaces the static HTML on mount, Suspense shows
// a spinner while the page's chunk loads, then the page shows a spinner of its
// own while its data loads. preloadRoute fetches both first — the chunk for
// every route, and the data for each route that declares the fetch its first
// render waits on (`data`) — so main.jsx can keep the prerendered HTML on
// screen until the page can render in full. A route without `data` still
// shows its own loading state once mounted.
import { lazy } from 'react';
import { matchPath } from 'react-router';
import { dataCache } from './utils/dataCache';
import {
  analysisFetch,
  commentaryFetch,
  dashboardStatsFetch,
  digestFetch,
  industriesListFetch,
  industryDivisionFetch,
  mergerDetailFetch,
  mergersListFetch,
  partiesListFetch,
  partyShardFetch,
  phase2Fetch,
  quarterlyFetch,
  refiledNotificationsFetch,
} from './utils/pageData';

// A page's chunk, loaded once whether main.jsx or React asks first. The
// promise is tagged fulfilled as it settles, the way React tags the promises
// it tracks: React reads that tag when main.jsx mounts (in a transition), so a
// page whose chunk has already arrived renders on the first pass. Untagged,
// React only learns of it a tick later and, in a real browser, paints the
// Suspense fallback in between (a jsdom test doesn't show this; the tag's own
// test in routes.test.jsx guards it, and it was checked in Chromium).
function page(load) {
  let promise = null;
  const loadOnce = () => {
    if (!promise) {
      const loading = load();
      promise = loading;
      loading.then(
        (mod) => {
          loading.status = 'fulfilled';
          loading.value = mod;
        },
        () => {
          promise = null; // let a later attempt retry a failed download
        },
      );
    }
    return promise;
  };
  return { Component: lazy(loadOnce), load: loadOnce };
}

const Dashboard = page(() => import('./pages/Dashboard'));
const Mergers = page(() => import('./pages/Mergers'));
const MergerDetail = page(() => import('./pages/MergerDetail'));
const Industries = page(() => import('./pages/Industries'));
const IndustryDetail = page(() => import('./pages/IndustryDetail'));
const Parties = page(() => import('./pages/Parties'));
const PartyDetail = page(() => import('./pages/PartyDetail'));
const Commentary = page(() => import('./pages/Commentary'));
const Digest = page(() => import('./pages/Digest'));
const NickTwort = page(() => import('./pages/NickTwort'));
const Analysis = page(() => import('./pages/Analysis'));
const Phase2 = page(() => import('./pages/Phase2'));
const RefiledNotifications = page(() => import('./pages/RefiledNotifications'));
const CurrentStatus = page(() => import('./pages/CurrentStatus'));
const Quarterly = page(() => import('./pages/Quarterly'));
const PrivacyPolicy = page(() => import('./pages/PrivacyPolicy'));
const Copyright = page(() => import('./pages/Copyright'));
const Feedback = page(() => import('./pages/Feedback'));
const NotFound = page(() => import('./pages/NotFound'));

// `data(params)` lists what the page's first render waits on, as the
// [cacheKey, url] pairs its useFetchData calls use (utils/pageData.js, shared
// with the pages); preloadRoute puts them in dataCache beforehand. Params
// arrive decoded as useDecodedParam decodes them.
const merger = ({ id }) => [mergerDetailFetch(id)];
const industry = ({ code }) => [industryDivisionFetch(code)];
const party = ({ id }) => [partyShardFetch(id)];

export const ROUTES = [
  { path: '/', page: Dashboard, data: () => [dashboardStatsFetch()] },
  { path: '/mergers', page: Mergers, data: () => [mergersListFetch()] },
  { path: '/mergers/:id', page: MergerDetail, data: merger },
  { path: '/mergers/:id/:slug', page: MergerDetail, data: merger },
  { path: '/industries', page: Industries, data: () => [industriesListFetch()] },
  { path: '/industries/:code', page: IndustryDetail, data: industry },
  { path: '/industries/:code/:slug', page: IndustryDetail, data: industry },
  { path: '/parties', page: Parties, data: () => [partiesListFetch()] },
  { path: '/parties/:id', page: PartyDetail, data: party },
  { path: '/parties/:id/:slug', page: PartyDetail, data: party },
  { path: '/commentary', page: Commentary, data: () => [commentaryFetch()] },
  { path: '/digest', page: Digest, data: () => [digestFetch()] },
  { path: '/analysis', page: Analysis, data: () => [analysisFetch()] },
  { path: '/phase-2', page: Phase2, data: () => [phase2Fetch()] },
  { path: '/refiled-notifications', page: RefiledNotifications, data: () => [refiledNotificationsFetch()] },
  { path: '/current-status', page: CurrentStatus, data: () => [analysisFetch()] },
  { path: '/quarterly', page: Quarterly, data: () => [quarterlyFetch()] },
  { path: '/quarterly/:quarter', page: Quarterly, data: () => [quarterlyFetch()] },
  { path: '/nick-twort', page: NickTwort },
  { path: '/privacy', page: PrivacyPolicy },
  { path: '/copyright', page: Copyright },
  { path: '/feedback', page: Feedback },
  { path: '*', page: NotFound },
];

/** The route that renders `pathname`, as <Routes> would pick it. */
export function routeFor(pathname) {
  return (
    ROUTES.find(({ path }) => path !== '*' && matchPath(path, pathname)) ??
    ROUTES.find(({ path }) => path === '*')
  );
}

function decode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** The [cacheKey, url] pairs `pathname`'s page waits on for its first render. */
export function routeData(pathname) {
  const route = routeFor(pathname);
  if (!route.data) return [];
  const params = matchPath(route.path, pathname)?.params ?? {};
  return route.data(Object.fromEntries(Object.entries(params).map(([k, v]) => [k, decode(v)])));
}


/**
 * Load the chunk and first-render data of the page at `pathname`. Never
 * rejects: whatever fails to load here, the page loads (and reports) itself.
 */
export function preloadRoute(pathname) {
  return Promise.allSettled([
    routeFor(pathname).page.load(),
    ...routeData(pathname)
      .filter(([cacheKey]) => !dataCache.has(cacheKey))
      .map(([cacheKey, url]) => dataCache.load(cacheKey, url)),
  ]);
}
