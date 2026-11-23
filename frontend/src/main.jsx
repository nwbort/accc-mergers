import { StrictMode, startTransition } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { preloadRoute } from './routes'

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
// where a transition sees the chunk is there and renders the page outright.
// With nothing prerendered (the SPA fallback shell) there is nothing to keep,
// so the spinner shows at once.
if (root.hasChildNodes()) {
  Promise.race([
    preloadRoute(window.location.pathname),
    new Promise((resolve) => setTimeout(resolve, MAX_PRELOAD_WAIT_MS)),
  ]).then(() => startTransition(mount))
} else {
  mount()
}
