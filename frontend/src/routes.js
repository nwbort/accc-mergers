// Every route the app renders, with the page that draws it.
//
// Pages are code-split: each loads its own chunk on demand, so the initial
// bundle carries only the app shell. That chunk is also why a prerendered page
// used to flash: createRoot replaces the static HTML on mount, Suspense shows
// a spinner while the page's chunk loads, then the page shows a spinner of its
// own while its data loads. preloadRoute fetches both first, so main.jsx can
// keep the prerendered HTML on screen until the page can render in full.
import { lazy } from 'react';
import { matchPath } from 'react-router';
import { API_ENDPOINTS } from './config';
import { dataCache } from './utils/dataCache';
import { DASHBOARD_STATS_KEY } from './utils/dashboardStats';

// A page's chunk, loaded once whether main.jsx or React asks first. The
// promise is tagged fulfilled, as React tags the promises it tracks, so that
// when main.jsx mounts (in a transition) React sees the chunk has already
// arrived and renders the page on the first pass, rather than suspending and
// painting the spinner first.
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

// `data` is what the page's first render waits on, as [cacheKey, url] pairs
// in its useFetchData calls; preloadRoute puts it in dataCache beforehand.
export const ROUTES = [
  { path: '/', page: Dashboard, data: [[DASHBOARD_STATS_KEY, API_ENDPOINTS.stats]] },
  { path: '/mergers', page: Mergers },
  { path: '/mergers/:id', page: MergerDetail },
  { path: '/mergers/:id/:slug', page: MergerDetail },
  { path: '/industries', page: Industries },
  { path: '/industries/:code', page: IndustryDetail },
  { path: '/industries/:code/:slug', page: IndustryDetail },
  { path: '/parties', page: Parties },
  { path: '/parties/:id', page: PartyDetail },
  { path: '/parties/:id/:slug', page: PartyDetail },
  { path: '/commentary', page: Commentary },
  { path: '/digest', page: Digest },
  { path: '/analysis', page: Analysis },
  { path: '/phase-2', page: Phase2 },
  { path: '/refiled-notifications', page: RefiledNotifications },
  { path: '/current-status', page: CurrentStatus },
  { path: '/quarterly', page: Quarterly },
  { path: '/quarterly/:quarter', page: Quarterly },
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

async function preloadData(cacheKey, url) {
  if (dataCache.has(cacheKey)) return;
  const res = await fetch(url);
  if (res.ok) dataCache.set(cacheKey, await res.json());
}

/**
 * Load the chunk and first-render data of the page at `pathname`. Never
 * rejects: whatever fails to load here, the page loads (and reports) itself.
 */
export function preloadRoute(pathname) {
  const route = routeFor(pathname);
  return Promise.allSettled([
    route.page.load(),
    ...(route.data ?? []).map(([cacheKey, url]) => preloadData(cacheKey, url)),
  ]);
}
