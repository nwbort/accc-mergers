import { useEffect, useRef } from 'react';
import { FaTimes } from 'react-icons/fa';
import { SHORTCUT_PAGES } from '../constants/navPages';

// The `g` chords are read from the same table useKeyboardShortcuts handles them
// from, so this overlay documents what the app actually does rather than a copy
// someone has to remember to update. The rest have no such table to read — each
// is a one-off handled where it applies (⌘K and `/` in the hook, j/k/Enter in
// the mergers list) — so they stay written out here.
const shortcuts = [
  { keys: ['⌘K'], description: 'Open command palette' },
  { keys: ['/'], description: 'Focus search' },
  ...SHORTCUT_PAGES.map(({ shortcut, label }) => ({
    keys: ['g', shortcut],
    description: `Go to ${label}`,
  })),
  { keys: ['j'], description: 'Next item (mergers list)' },
  { keys: ['k'], description: 'Previous item (mergers list)' },
  { keys: ['Enter'], description: 'Open selected item' },
  { keys: ['?'], description: 'Toggle this help' },
  { keys: ['Esc'], description: 'Close / unfocus' },
];

function Kbd({ children }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[1.75rem] h-7 px-2 rounded-lg bg-white text-xs font-mono font-semibold text-gray-700">
      {children}
    </kbd>
  );
}

export default function KeyboardShortcutsHelp({ isOpen, onClose }) {
  const dialogRef = useRef(null);
  const previouslyFocusedRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => {
      if (e.key === 'Escape' || e.key === '?') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  // Focus trap + focus restoration
  useEffect(() => {
    if (!isOpen) return;
    previouslyFocusedRef.current = document.activeElement;

    const dialog = dialogRef.current;
    const focusables = dialog?.querySelectorAll(
      'button, [href], input, [tabindex]:not([tabindex="-1"])'
    );
    focusables?.[0]?.focus();

    const handleTab = (e) => {
      if (e.key !== 'Tab' || !dialog) return;
      const items = dialog.querySelectorAll(
        'button, [href], input, [tabindex]:not([tabindex="-1"])'
      );
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleTab);
    return () => {
      document.removeEventListener('keydown', handleTab);
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div className="absolute inset-0 bg-gray-950/40" />
      <div
        ref={dialogRef}
        className="relative bg-surface-container-high rounded-3xl shadow-elevated max-w-sm w-full p-6 animate-pop-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-2xl font-semibold tracking-tight text-gray-900">Keyboard shortcuts</h2>
          <button
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center -mr-2 text-gray-600 hover:bg-gray-900/[0.08] transition-colors rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            aria-label="Close shortcuts help"
          >
            <FaTimes className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>
        <ul className="space-y-3">
          {shortcuts.map(({ keys, description }) => (
            <li key={description} className="flex items-center justify-between">
              <span className="text-sm text-gray-600">{description}</span>
              <span className="flex items-center gap-1">
                {keys.map((key, i) => (
                  <span key={i} className="flex items-center gap-1">
                    {i > 0 && <span className="text-xs text-gray-500">then</span>}
                    <Kbd>{key}</Kbd>
                  </span>
                ))}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
