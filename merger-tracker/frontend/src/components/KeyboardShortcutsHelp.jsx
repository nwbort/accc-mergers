import { useEffect } from 'react';

const shortcuts = [
  { keys: ['/'], description: 'Focus search' },
  { keys: ['g', 'd'], description: 'Go to Dashboard' },
  { keys: ['g', 'm'], description: 'Go to Mergers' },
  { keys: ['g', 't'], description: 'Go to Timeline' },
  { keys: ['g', 'i'], description: 'Go to Industries' },
  { keys: ['g', 'c'], description: 'Go to Commentary' },
  { keys: ['g', 'a'], description: 'Go to Analysis' },
  { keys: ['?'], description: 'Toggle this help' },
  { keys: ['Esc'], description: 'Close / unfocus' },
];

function Kbd({ children }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[1.5rem] h-6 px-1.5 rounded bg-gray-100 border border-gray-200 text-xs font-mono font-medium text-gray-600 shadow-sm">
      {children}
    </kbd>
  );
}

export default function KeyboardShortcutsHelp({ isOpen, onClose }) {
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

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div
        className="relative bg-white rounded-2xl shadow-xl border border-gray-100 max-w-sm w-full p-6 animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-gray-900">Keyboard shortcuts</h2>
          <button
            onClick={onClose}
            className="p-1 text-gray-400 hover:text-gray-600 transition-colors rounded-lg"
            aria-label="Close shortcuts help"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <ul className="space-y-3">
          {shortcuts.map(({ keys, description }) => (
            <li key={description} className="flex items-center justify-between">
              <span className="text-sm text-gray-600">{description}</span>
              <span className="flex items-center gap-1">
                {keys.map((key, i) => (
                  <span key={i} className="flex items-center gap-1">
                    {i > 0 && <span className="text-xs text-gray-400">then</span>}
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
