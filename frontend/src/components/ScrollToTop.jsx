import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router';

export default function ScrollToTop() {
  const { pathname, hash } = useLocation();
  // The path the reader was last scrolled for. It starts as the page the app
  // loaded on, so nothing scrolls on mount: the browser has already placed a
  // fresh page (at the top, or where Back left it), and on a prerendered page
  // React mounts only once its code and data are in (main.jsx), by which time
  // a reader may have scrolled the static page. Comparing paths, not counting
  // runs, also holds under StrictMode's doubled effects.
  const lastPathname = useRef(pathname);

  useEffect(() => {
    if (pathname === lastPathname.current) return;
    lastPathname.current = pathname;
    // A link with a hash targets a point on the page, which the page scrolls
    // to itself once its content has loaded (see MergerDetail).
    if (hash) return;
    window.scrollTo(0, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return null;
}
