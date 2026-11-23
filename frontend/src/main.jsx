import { StrictMode, startTransition } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { preloadRoute } from './routes'
import { isAppKey } from './utils/appKeys'

// How long a prerendered page may wait for its own page before mounting
// anyway. The static HTML is readable meanwhile, but nothing on it is
// interactive (search, the command palette, the follow buttons) until then.
const MAX_PRELOAD_WAIT_MS = 3000

const root = document.getElementById('root')
const mount = () =>
  createRoot(root).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )

// createRoot replaces whatever is in #root on its first render. On a
// prerendered page that is the page itself (frontend/prerender.js), so mount
// only once its chunk and first-render data are in hand (routes.js): mounting
// sooner swaps it for a spinner, then the page. And mount in a transition: a
// plain first render is synchronous, and a synchronous render paints the
// Suspense fallback for a lazy page even when its chunk has already arrived,
// where a transition sees the chunk is there (routes.js tags its promise
// fulfilled) and renders the page outright.
// The static page's links work without React, but its keyboard shortcuts
// and anything typed need the app, so the first key that means "use the app"
// (utils/appKeys.js) ends the wait at once, taking a brief spinner over keys
// that do nothing. Pointer events don't: a touch scroll starts with one, and
// ending the wait there would flash the spinner mid-scroll; a tap on a link
// needs no app, and a mount landing between its pointerdown and click could
// swallow it.
// With nothing prerendered (the SPA fallback shell) there is nothing to keep,
// so the spinner shows at once.
// Resolves on the first app key; stop() removes the listener once the wait
// has ended some other way, so it doesn't outlive its purpose.
function firstAppKey() {
  let onKey
  const promise = new Promise((resolve) => {
    onKey = (event) => {
      if (isAppKey(event)) resolve()
    }
    window.addEventListener('keydown', onKey, true)
  })
  return { promise, stop: () => window.removeEventListener('keydown', onKey, true) }
}

if (root.hasChildNodes()) {
  const appKey = firstAppKey()
  Promise.race([
    preloadRoute(window.location.pathname),
    new Promise((resolve) => setTimeout(resolve, MAX_PRELOAD_WAIT_MS)),
    appKey.promise,
  ]).then(() => {
    appKey.stop()
    startTransition(mount)
  })
} else {
  mount()
}
