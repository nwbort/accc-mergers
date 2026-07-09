import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { FaSearch } from 'react-icons/fa';
import { dataCache } from '../utils/dataCache';
import { buildSearchIndex, searchMergers } from '../utils/searchIndex';
import { fetchAllMergers } from '../utils/fetchAllMergers';
import { mergerPath } from '../utils/slug';

const PAGES = [
  { label: 'Dashboard', path: '/' },
  { label: 'Mergers', path: '/mergers' },
  { label: 'Timeline', path: '/timeline' },
  { label: 'Industries', path: '/industries' },
  { label: 'Parties', path: '/parties' },
  { label: 'Analysis', path: '/analysis' },
  { label: 'Commentary', path: '/commentary' },
  { label: 'Digest', path: '/digest' },
];

const MAX_MERGER_RESULTS = 8;

export default function CommandPalette({ isOpen, onClose }) {
  const navigate = useNavigate();
  const inputRef = useRef(null);
  const dialogRef = useRef(null);
  const listRef = useRef(null);
  const previouslyFocusedRef = useRef(null);

  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [mergers, setMergers] = useState(() => dataCache.get('mergers-list') || []);
  const [searchIndex, setSearchIndex] = useState(() => {
    const cached = dataCache.get('mergers-list');
    return cached?.length ? buildSearchIndex(cached) : null;
  });
  const [mergersLoading, setMergersLoading] = useState(false);

  // Reset state on open (adjusting state during render rather than in an
  // effect, per https://react.dev/learn/you-might-not-need-an-effect).
  const [prevIsOpen, setPrevIsOpen] = useState(false);
  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      const cached = dataCache.get('mergers-list');
      if (cached?.length) {
        setMergers(cached);
        setSearchIndex(buildSearchIndex(cached));
      } else {
        setMergersLoading(true);
      }
    }
  }

  // Lazily fetch the full merger list if it isn't cached yet (e.g. a cold
  // visit that opened the palette before Mergers ever loaded).
  useEffect(() => {
    if (!isOpen || dataCache.has('mergers-list')) return;
    fetchAllMergers()
      .then(({ mergers: allMergers, searchIndex: index }) => {
        setMergers(allMergers);
        setSearchIndex(index);
      })
      .catch((err) => console.error('Command palette failed to load mergers:', err))
      .finally(() => setMergersLoading(false));
  }, [isOpen]);

  const trimmedQuery = query.trim();

  const pageResults = useMemo(() => {
    if (!trimmedQuery) return PAGES;
    const q = trimmedQuery.toLowerCase();
    return PAGES.filter((p) => p.label.toLowerCase().includes(q));
  }, [trimmedQuery]);

  const mergerResults = useMemo(() => {
    if (!trimmedQuery || !searchIndex) return [];
    return searchMergers(mergers, trimmedQuery, searchIndex).slice(0, MAX_MERGER_RESULTS);
  }, [trimmedQuery, mergers, searchIndex]);

  const showMergersGroup = trimmedQuery && (mergersLoading || mergerResults.length > 0);
  const noResults = trimmedQuery && !mergersLoading && pageResults.length === 0 && mergerResults.length === 0;

  // Flattened list of selectable rows, in display order, so arrow keys can
  // move through both groups without caring which one an index belongs to.
  const items = useMemo(() => {
    const list = pageResults.map((p) => ({ type: 'page', path: p.path, key: `page:${p.path}` }));
    mergerResults.forEach((m) => {
      list.push({
        type: 'merger',
        path: mergerPath(m.merger_id, m.merger_name),
        key: `merger:${m.merger_id}`,
      });
    });
    return list;
  }, [pageResults, mergerResults]);

  // Clamp selection when the result set shrinks (e.g. typing narrows results).
  const [prevItemsLength, setPrevItemsLength] = useState(items.length);
  if (items.length !== prevItemsLength) {
    setPrevItemsLength(items.length);
    setSelectedIndex((i) => Math.min(i, Math.max(items.length - 1, 0)));
  }

  const goTo = useCallback(
    (path) => {
      onClose();
      navigate(path);
    },
    [navigate, onClose]
  );

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (items.length) setSelectedIndex((i) => (i + 1) % items.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (items.length) setSelectedIndex((i) => (i - 1 + items.length) % items.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const item = items[selectedIndex];
      if (item) goTo(item.path);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  // Focus the input, lock body scroll, and restore focus to whatever was
  // focused before the palette opened.
  useEffect(() => {
    if (!isOpen) return;
    previouslyFocusedRef.current = document.activeElement;
    inputRef.current?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen]);

  // Keep the highlighted row scrolled into view when navigating by keyboard.
  useEffect(() => {
    const selected = listRef.current?.querySelector('[data-selected="true"]');
    selected?.scrollIntoView?.({ block: 'nearest' });
  }, [selectedIndex]);

  if (!isOpen) return null;

  const selectedKey = items[selectedIndex]?.key;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[12vh] p-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="relative bg-white rounded-2xl shadow-xl border border-gray-100 max-w-lg w-full overflow-hidden animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <FaSearch className="w-4 h-4 text-gray-400 shrink-0" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search pages and mergers…"
            className="flex-1 bg-transparent text-sm text-gray-900 placeholder-gray-400 focus:outline-none"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-palette-listbox"
            aria-activedescendant={selectedKey}
            autoComplete="off"
          />
          <kbd className="hidden sm:inline-flex items-center justify-center px-1.5 h-5 rounded bg-gray-100 border border-gray-200 text-[10px] font-mono font-medium text-gray-500">
            Esc
          </kbd>
        </div>

        <ul
          ref={listRef}
          id="command-palette-listbox"
          role="listbox"
          aria-label="Command palette results"
          className="max-h-80 overflow-y-auto py-2"
        >
          {noResults && (
            <li className="px-4 py-6 text-sm text-gray-400 text-center" role="presentation">
              No results for &ldquo;{trimmedQuery}&rdquo;
            </li>
          )}

          {pageResults.length > 0 && (
            <>
              <li
                className="px-4 pt-1 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide"
                role="presentation"
              >
                Pages
              </li>
              {pageResults.map((p) => {
                const key = `page:${p.path}`;
                const selected = key === selectedKey;
                return (
                  <li
                    key={key}
                    id={key}
                    role="option"
                    aria-selected={selected}
                    data-selected={selected}
                    onMouseEnter={() => setSelectedIndex(items.findIndex((i) => i.key === key))}
                    onClick={() => goTo(p.path)}
                    className={`px-4 py-2 text-sm cursor-pointer ${
                      selected ? 'bg-primary/10 text-primary' : 'text-gray-700'
                    }`}
                  >
                    {p.label}
                  </li>
                );
              })}
            </>
          )}

          {showMergersGroup && (
            <>
              <li
                className="px-4 pt-3 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wide"
                role="presentation"
              >
                Mergers
              </li>
              {mergersLoading && mergerResults.length === 0 && (
                <li className="px-4 py-2 text-sm text-gray-400" role="presentation">
                  Loading mergers…
                </li>
              )}
              {mergerResults.map((m) => {
                const key = `merger:${m.merger_id}`;
                const selected = key === selectedKey;
                const path = mergerPath(m.merger_id, m.merger_name);
                return (
                  <li
                    key={key}
                    id={key}
                    role="option"
                    aria-selected={selected}
                    data-selected={selected}
                    onMouseEnter={() => setSelectedIndex(items.findIndex((i) => i.key === key))}
                    onClick={() => goTo(path)}
                    className={`px-4 py-2 text-sm cursor-pointer truncate ${
                      selected ? 'bg-primary/10 text-primary' : 'text-gray-700'
                    }`}
                  >
                    {m.merger_name}
                  </li>
                );
              })}
            </>
          )}
        </ul>
      </div>
    </div>
  );
}
