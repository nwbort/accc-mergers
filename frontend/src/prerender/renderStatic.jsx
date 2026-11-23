// Build-time rendering of real page components to static HTML.
//
// prerender.js is a plain Node module and can't import JSX, so it loads this
// file through Vite's SSR module loader (see renderComponentPages there) and
// calls renderStaticRoute for each route below. The markup is exactly what
// the page renders once React mounts, so the raw HTML crawlers read is the
// page itself rather than a hand-written approximation that can drift.
//
// Only pages whose content is fully known at build time belong here: either
// they fetch nothing (the author, privacy and copyright pages), or the data
// they would fetch is a file the prerenderer can hand over (commentary).

import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import Footer from '../components/Footer';
import NickTwort from '../pages/NickTwort';
import PrivacyPolicy from '../pages/PrivacyPolicy';
import Copyright from '../pages/Copyright';
import { CommentaryList } from '../pages/Commentary';

/**
 * Route → element factory. Each receives the parsed data the prerenderer
 * read for it (only commentary uses any).
 */
const ROUTES = {
  '/nick-twort': () => <NickTwort />,
  '/privacy': () => <PrivacyPolicy />,
  '/copyright': () => <Copyright />,
  '/commentary': ({ commentary }) => <CommentaryList items={commentary?.items || []} />,
};

/** The routes this module can render. */
export const COMPONENT_ROUTES = Object.keys(ROUTES);

/**
 * The site footer as static HTML, for the prerendered chrome around every
 * page. It is the real component, so its links (privacy, copyright, the author
 * page) are in the raw HTML exactly as they are once React mounts.
 *
 * @returns {string}
 */
export function renderFooter() {
  return renderToStaticMarkup(
    <MemoryRouter>
      <Footer />
    </MemoryRouter>,
  );
}

/**
 * Render one route's page body to HTML, or null if the route isn't one of
 * COMPONENT_ROUTES. <SEO> renders into Helmet's context, not the markup, so
 * the head is left to prerender.js's renderPage like every other page.
 *
 * @param {string} path
 * @param {object} [data] - e.g. { commentary } for /commentary
 * @returns {string|null}
 */
export function renderStaticRoute(path, data = {}) {
  const route = ROUTES[path];
  if (!route) return null;
  return renderToStaticMarkup(
    <HelmetProvider context={{}}>
      <MemoryRouter initialEntries={[path]}>{route(data)}</MemoryRouter>
    </HelmetProvider>,
  );
}
