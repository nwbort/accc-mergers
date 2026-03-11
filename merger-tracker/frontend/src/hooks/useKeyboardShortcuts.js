import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

/**
 * Keyboard shortcuts for power users.
 *
 * Global shortcuts (work from any page):
 *   /        Focus the search input on the current page (if one exists)
 *   g then d Go to Dashboard
 *   g then m Go to Mergers
 *   g then t Go to Timeline
 *   g then i Go to Industries
 *   g then c Go to Commentary
 *   g then a Go to Analysis
 *   ?        Show/hide keyboard shortcut help overlay
 *
 * List shortcuts (Mergers list):
 *   j        Move selection down
 *   k        Move selection up
 *   Enter    Open selected merger
 */
export function useKeyboardShortcuts({ onToggleHelp } = {}) {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    let pendingG = false;
    let gTimer = null;

    const handleKeyDown = (e) => {
      // Don't capture shortcuts when typing in inputs, textareas, or contenteditable
      const tag = e.target.tagName;
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable;

      // Allow Escape to blur the current input
      if (e.key === 'Escape' && isInput) {
        e.target.blur();
        return;
      }

      if (isInput) return;

      // Don't capture shortcuts with modifier keys (except shift for ?)
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      // "g" prefix for navigation (vim-style "go to")
      if (pendingG) {
        pendingG = false;
        clearTimeout(gTimer);

        const routes = {
          d: '/',
          m: '/mergers',
          t: '/timeline',
          i: '/industries',
          c: '/commentary',
          a: '/analysis',
        };

        const route = routes[e.key];
        if (route && location.pathname !== route) {
          e.preventDefault();
          navigate(route);
        }
        return;
      }

      if (e.key === 'g') {
        pendingG = true;
        gTimer = setTimeout(() => { pendingG = false; }, 1000);
        return;
      }

      // "/" to focus search
      if (e.key === '/') {
        const searchInput = document.getElementById('search');
        if (searchInput) {
          e.preventDefault();
          searchInput.focus();
        }
        return;
      }

      // "?" to toggle help overlay
      if (e.key === '?' && e.shiftKey !== false) {
        e.preventDefault();
        onToggleHelp?.();
        return;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      clearTimeout(gTimer);
    };
  }, [navigate, location.pathname, onToggleHelp]);
}
