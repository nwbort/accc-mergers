import { useState } from 'react';
import { hasAppSettled } from '../utils/appMount';

/**
 * ' animate-fade-in' for a page reached by navigating, '' for a page rendered
 * as part of the app's first render. A page whose prerendered HTML is drawn by
 * its own components (the dashboard top, the author, privacy, copyright and
 * commentary pages) is replacing that same content on first load, where a fade
 * from transparent would only blink it. Read once, when the page mounts.
 */
export function useFadeIn() {
  const [fade] = useState(hasAppSettled);
  return fade ? ' animate-fade-in' : '';
}
