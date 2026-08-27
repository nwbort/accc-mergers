import { useState, useMemo } from 'react';
import { Link } from 'react-router';
import { FaArrowRightLong } from 'react-icons/fa6';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import Treemap from '../components/Treemap';
import SearchInput from '../components/SearchInput';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { useDebounce } from '../hooks/useDebounce';
import { partyPath } from '../utils/slug';
import { CARD, SECTION_HEADING } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/parties'];

// How many search results to render at once. The full index runs to well over a
// thousand parties (mostly one-deal entities), so we never render the whole
// list — the treemap surfaces the frequent acquirers and the search finds the
// long tail on demand.
const MAX_RESULTS = 60;

function Parties() {
  const { data: partiesData, loading, error } = useFetchData(
    API_ENDPOINTS.parties,
    { cacheKey: 'parties-list' }
  );
  const parties = useMemo(() => partiesData?.parties || [], [partiesData]);
  const totalParties = partiesData?.total_parties ?? parties.length;

  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearch = useDebounce(searchTerm, 200);

  const results = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    if (!term) return [];
    return parties
      .filter((party) => party.name.toLowerCase().includes(term))
      .sort((a, b) => b.merger_count - a.merger_count || a.name.localeCompare(b.name))
      .slice(0, MAX_RESULTS);
  }, [parties, debouncedSearch]);

  const totalMatches = useMemo(() => {
    const term = debouncedSearch.trim().toLowerCase();
    if (!term) return 0;
    return parties.reduce(
      (count, party) => (party.name.toLowerCase().includes(term) ? count + 1 : count),
      0
    );
  }, [parties, debouncedSearch]);

  const isSearching = debouncedSearch.trim().length > 0;

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/parties"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Header: title + compact summary stat */}
        <header className="mb-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
              Merger parties
            </h1>
            <p className="mt-1 text-sm text-gray-500 max-w-xl">
              The companies and investors that turn up most often in ACCC merger reviews.
            </p>
          </div>
          <div className="flex gap-6 shrink-0">
            <div>
              <div className="text-2xl font-bold tracking-tight text-gray-900 tabular-nums">{totalParties}</div>
              <div className="text-xs text-gray-500">parties</div>
            </div>
          </div>
        </header>

        {/* Party heatmap */}
        <div className={`${CARD} p-5 mb-6`}>
          <Treemap
            items={parties}
            getKey={(party) => party.id}
            getPath={(party) => partyPath(party.id, party.name)}
          />
        </div>

        {/* Search */}
        <div className={`${CARD} p-5`}>
          <div className="flex items-baseline justify-between gap-3 mb-2">
            <label
              htmlFor="search"
              className={SECTION_HEADING}
            >
              Search parties
            </label>
            {isSearching && (
              <p className={`${SECTION_HEADING} shrink-0`}>
                {totalMatches > MAX_RESULTS
                  ? `Showing ${MAX_RESULTS} of ${totalMatches}`
                  : `${totalMatches} match${totalMatches === 1 ? '' : 'es'}`}
              </p>
            )}
          </div>
          <SearchInput
            id="search"
            placeholder="Search by party name..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            autoComplete="off"
          />

          {/* Results appear only while searching — the full list is never shown */}
          {isSearching && (
            <div className="mt-4">
              {results.length === 0 ? (
                <p className="text-sm text-gray-500 py-6 text-center">
                  No parties match &ldquo;{debouncedSearch.trim()}&rdquo;
                </p>
              ) : (
                <ul className="divide-y divide-gray-50">
                  {results.map((party) => (
                    <li key={party.id}>
                      <Link
                        to={partyPath(party.id, party.name)}
                        className="group flex items-center justify-between gap-3 py-3 px-2 -mx-2 rounded-lg hover:bg-gray-50/80 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      >
                        <span className="text-sm font-medium text-gray-900 group-hover:text-primary transition-colors truncate">
                          {party.name}
                        </span>
                        <span className="flex items-center gap-2 shrink-0">
                          <span className="inline-flex items-center justify-center min-w-[2.25rem] px-2.5 py-1 rounded-lg text-xs font-semibold bg-primary/10 text-primary tabular-nums">
                            {party.merger_count}
                          </span>
                          <FaArrowRightLong className="h-3 w-3 text-gray-300 group-hover:text-primary transition-colors" />
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default Parties;
