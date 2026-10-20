import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router';
import { FaSearch } from 'react-icons/fa';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';
import { buildSearchIndex, searchMergers } from '../utils/searchIndex';
import { fetchAllMergers } from '../utils/fetchAllMergers';
import { industryPath, mergerPath, partyPath } from '../utils/slug';
import { NAV_PAGES } from '../constants/navPages';

const PAGES = NAV_PAGES.filter((p) => p.inPalette)
  .sort((a, b) => a.paletteOrder - b.paletteOrder)
  .map(({ path, label }) => ({ path, label }));

// Mergers, parties and industries share one combined budget of rows. Each
// group is guaranteed an even share, and the rest is handed round-robin to
// whichever groups still have matches — so two party matches and no industry
// matches leaves room for four mergers, and vice versa.
const MAX_ENTITY_RESULTS = 6;

function shareBudget(matchCounts) {
  const guaranteed = Math.floor(MAX_ENTITY_RESULTS / matchCounts.length);
  const limits = matchCounts.map((n) => Math.min(n, guaranteed));
  let spare = MAX_ENTITY_RESULTS - limits.reduce((a, b) => a + b, 0);
  let grew = true;
  while (spare > 0 && grew) {
    grew = false;
    for (let i = 0; i < limits.length && spare > 0; i++) {
      if (limits[i] < matchCounts[i]) {
        limits[i] += 1;
        spare -= 1;
        grew = true;
      }
    }
  }
  return limits;
}

// The parties and industries lists are cached as their whole payloads
// (`parties.json`'s { parties, total_parties }, `industries.json`'s
// { industries }) under the same keys their pages use, so the two share one
// fetch.
const PARTIES_SOURCE = {
  cacheKey: 'parties-list',
  url: API_ENDPOINTS.parties,
  field: 'parties',
};
const INDUSTRIES_SOURCE = {
  cacheKey: 'industries-list',
  url: API_ENDPOINTS.industries,
  field: 'industries',
};

function cachedList({ cacheKey, field }) {
  return dataCache.get(cacheKey)?.[field] || [];
}

// One cached list, loaded lazily the first time the palette opens on a cold
// cache, and re-read from the cache on every later open.
function useCachedList(isOpen, source) {
  const [list, setList] = useState(() => cachedList(source));
  const [loading, setLoading] = useState(false);

  const [prevIsOpen, setPrevIsOpen] = useState(false);
  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (isOpen) {
      if (dataCache.has(source.cacheKey)) {
        setList(cachedList(source));
      } else {
        setLoading(true);
      }
    }
  }

  const { cacheKey, url, field } = source;
  useEffect(() => {
    if (!isOpen || dataCache.has(cacheKey)) return;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch ${field}`);
        return res.json();
      })
      .then((json) => {
        dataCache.set(cacheKey, json);
        setList(json?.[field] || []);
      })
      .catch((err) => console.error(`Command palette failed to load ${field}:`, err))
      .finally(() => setLoading(false));
  }, [isOpen, cacheKey, url, field]);

  return { list, loading };
}

// Name-substring matches (plus, optionally, a code prefix), busiest first.
function matchByName(list, q, codeOf) {
  return list
    .filter((x) => x.name.toLowerCase().includes(q) || (codeOf && String(codeOf(x)).startsWith(q)))
    .sort((a, b) => b.merger_count - a.merger_count || a.name.localeCompare(b.name))
    .slice(0, MAX_ENTITY_RESULTS);
}

function ResultGroup({ group, first, selectedKey, onHover, onSelect }) {
  return (
    <>
      <li
        className={`px-4 ${first ? 'pt-1' : 'pt-3'} pb-1 text-xs font-semibold text-gray-500 uppercase tracking-wide`}
        role="presentation"
      >
        {group.heading}
      </li>
      {group.loading && group.rows.length === 0 && (
        <li className="px-4 py-2 text-sm text-gray-500" role="presentation">
          Loading {group.heading.toLowerCase()}…
        </li>
      )}
      {group.rows.map((row) => {
        const selected = row.key === selectedKey;
        return (
          <li
            key={row.key}
            id={row.key}
            role="option"
            aria-selected={selected}
            data-selected={selected}
            onMouseEnter={() => onHover(row.key)}
            onClick={() => onSelect(row.path)}
            className={`px-4 py-2 text-sm cursor-pointer ${group.truncate ? 'truncate ' : ''}${
              selected ? 'bg-primary/10 text-primary' : 'text-gray-700'
            }`}
          >
            {row.label}
          </li>
        );
      })}
    </>
  );
}

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
  const { list: parties, loading: partiesLoading } = useCachedList(isOpen, PARTIES_SOURCE);
  const { list: industries, loading: industriesLoading } = useCachedList(
    isOpen,
    INDUSTRIES_SOURCE
  );

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

  // Full match sets, each capped at the combined budget (no single group can
  // ever show more than that). The final per-group slice happens below once
  // both counts are known, so they can share the budget.
  const mergerMatches = useMemo(() => {
    if (!trimmedQuery || !searchIndex) return [];
    return searchMergers(mergers, trimmedQuery, searchIndex).slice(0, MAX_ENTITY_RESULTS);
  }, [trimmedQuery, mergers, searchIndex]);

  const partyMatches = useMemo(
    () => (trimmedQuery ? matchByName(parties, trimmedQuery.toLowerCase()) : []),
    [trimmedQuery, parties]
  );

  const industryMatches = useMemo(
    () =>
      trimmedQuery ? matchByName(industries, trimmedQuery.toLowerCase(), (i) => i.code) : [],
    [trimmedQuery, industries]
  );

  // Every group in display order, each row already resolved to the key, path
  // and label it renders with. Pages sit outside the shared entity budget.
  const groups = useMemo(() => {
    const entityGroups = [
      {
        heading: 'Mergers',
        loading: mergersLoading,
        matches: mergerMatches,
        toRow: (m) => ({
          key: `merger:${m.merger_id}`,
          path: mergerPath(m.merger_id, m.merger_name),
          label: m.merger_name,
        }),
      },
      {
        heading: 'Parties',
        loading: partiesLoading,
        matches: partyMatches,
        toRow: (p) => ({ key: `party:${p.id}`, path: partyPath(p.id, p.name), label: p.name }),
      },
      {
        heading: 'Industries',
        loading: industriesLoading,
        matches: industryMatches,
        toRow: (i) => ({
          key: `industry:${i.code}`,
          path: industryPath(i.code, i.name),
          label: i.name,
        }),
      },
    ];
    const limits = shareBudget(entityGroups.map((g) => g.matches.length));
    return [
      {
        heading: 'Pages',
        loading: false,
        rows: pageResults.map((p) => ({ key: `page:${p.path}`, path: p.path, label: p.label })),
      },
      ...entityGroups.map(({ heading, loading, matches, toRow }, i) => ({
        heading,
        loading: Boolean(trimmedQuery) && loading,
        truncate: true,
        rows: matches.slice(0, limits[i]).map(toRow),
      })),
    ];
  }, [
    trimmedQuery,
    pageResults,
    mergersLoading,
    mergerMatches,
    partiesLoading,
    partyMatches,
    industriesLoading,
    industryMatches,
  ]);

  const visibleGroups = groups.filter((g) => g.loading || g.rows.length > 0);
  const noResults = trimmedQuery && visibleGroups.length === 0;

  // Flattened list of selectable rows, in display order, so arrow keys can
  // move through every group without caring which one an index belongs to.
  const items = useMemo(() => groups.flatMap((g) => g.rows), [groups]);

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
  // focused before the palette opened. Tab is also kept inside the dialog:
  // aria-modal hides the page behind from assistive tech, so letting focus
  // walk out into it would leave a keyboard user on invisible controls.
  useEffect(() => {
    if (!isOpen) return;
    previouslyFocusedRef.current = document.activeElement;
    inputRef.current?.focus();

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleTab = (e) => {
      if (e.key !== 'Tab') return;
      const dialog = dialogRef.current;
      if (!dialog) return;
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
            placeholder="Search…"
            className="flex-1 bg-transparent text-sm text-gray-900 placeholder-gray-500 focus:outline-none"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-palette-listbox"
            aria-activedescendant={selectedKey}
            autoComplete="off"
          />
          <kbd className="hidden sm:inline-flex items-center justify-center px-1.5 h-5 rounded bg-gray-100 border border-gray-200 text-[10px] font-mono font-medium text-gray-600">
            Esc
          </kbd>
        </div>

        <ul
          ref={listRef}
          id="command-palette-listbox"
          role="listbox"
          aria-label="Command palette results"
          className="max-h-[356px] overflow-y-auto py-2"
        >
          {noResults && (
            <li className="px-4 py-6 text-sm text-gray-500 text-center" role="presentation">
              No results for &ldquo;{trimmedQuery}&rdquo;
            </li>
          )}

          {visibleGroups.map((group, i) => (
            <ResultGroup
              key={group.heading}
              group={group}
              first={i === 0}
              selectedKey={selectedKey}
              onHover={(key) => setSelectedIndex(items.findIndex((it) => it.key === key))}
              onSelect={goTo}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}
