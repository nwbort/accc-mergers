import { createContext, useContext, useState, useEffect, useCallback } from 'react';

/**
 * Colour-theme state (light/dark) shared across the app.
 *
 * The actual `dark` class on <html> is first set by a tiny inline script in
 * index.html (before paint, to avoid a flash on reload). This provider mirrors
 * that logic for React: it reads the same localStorage key ('theme'), applies
 * the class on change, persists the choice, and — while the visitor hasn't made
 * an explicit choice — follows the OS `prefers-color-scheme`.
 *
 * Keep the storage key and default logic in sync with the inline script in
 * index.html.
 */

const STORAGE_KEY = 'theme';

const ThemeContext = createContext(null);

// Read the theme the inline script already resolved, so the provider's initial
// state matches what's painted (no first-render mismatch / flicker).
function getInitialTheme() {
  if (typeof document !== 'undefined' && document.documentElement.classList.contains('dark')) {
    return 'dark';
  }
  if (typeof window !== 'undefined' && window.matchMedia) {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'dark' || stored === 'light') return stored;
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } catch {
      /* fall through */
    }
  }
  return 'light';
}

// Browser chrome (address bar) colour, kept in step with the surface colour so
// mobile doesn't show a bright bar over a dark page.
const THEME_COLOR = { light: '#335145', dark: '#0f172a' };

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(getInitialTheme);
  // Whether the visitor has made an explicit choice yet. Once true, we stop
  // following the OS preference.
  const [hasExplicitChoice, setHasExplicitChoice] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored === 'dark' || stored === 'light';
    } catch {
      return false;
    }
  });

  // Apply the class to <html> and update the browser theme-color whenever the
  // theme changes.
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', theme === 'dark');
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', THEME_COLOR[theme]);
  }, [theme]);

  // Follow the OS preference until the visitor picks a theme themselves.
  useEffect(() => {
    if (hasExplicitChoice || !window.matchMedia) return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => setTheme(e.matches ? 'dark' : 'light');
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [hasExplicitChoice]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* ignore persistence failures (e.g. private mode) */
      }
      return next;
    });
    setHasExplicitChoice(true);
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, isDark: theme === 'dark', toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return ctx;
}
