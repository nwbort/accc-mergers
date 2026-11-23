/**
 * `stats.json`, as the dashboard (and the party and industry pages, which read
 * its medians) cache it, under this key. main.jsx also fills this entry before
 * the app mounts on the homepage (see routes.js), so the dashboard's first
 * render has its data.
 */
export const DASHBOARD_STATS_KEY = 'dashboard-stats';
