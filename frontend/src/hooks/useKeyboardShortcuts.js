import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router';
import { SHORTCUT_ROUTES } from '../constants/navPages';

/**
 * Keyboard shortcuts for power users.
 *
 * Global shortcuts (work from any page):
 *   ⌘K/Ctrl-K Open the command palette (works even while typing in an input)
 *   /        Focus the search input on the current page if one exists,
 *            otherwise open the command palette
 *   g then ‹key› Go to a page — the chords are declared in
 *            constants/navPages.js, not here, so this hook and the help
 *            overlay cannot drift apart
 *   ?        Show/hide keyboard shortcut help overlay
 *
 * List shortcuts (Mergers list):
 *   j        Move selection down
 *   k        Move selection up
 *   Enter    Open selected merger
 */
export function useKeyboardShortcuts({ onToggleHelp, onTogglePalette } = {}) {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    let pendingG = false;
    let gTimer = null;

    const handleKeyDown = (e) => {
      // ⌘K/Ctrl-K opens the command palette from anywhere, including inputs.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onTogglePalette?.();
        return;
      }

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

        const route = SHORTCUT_ROUTES[e.key];
        if (route && location.pathname !== route) {
          e.preventDefault();
          navigate(route);
        }
        return;
      }

      if (e.key === 'g') {
        pendingG = true;
        gTimer = setTimeout(() => { pendingG = false; }, 2500);
        return;
      }

      // "/" to focus search — prefer an in-page search input if the page has
      // one (Mergers, Industries); otherwise open the command palette.
      if (e.key === '/') {
        e.preventDefault();
        const searchInput = document.getElementById('search');
        if (searchInput) {
          searchInput.focus();
        } else {
          onTogglePalette?.();
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
  }, [navigate, location.pathname, onToggleHelp, onTogglePalette]);
}
