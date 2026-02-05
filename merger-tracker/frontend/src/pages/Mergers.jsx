import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';

const sortMergers = (list) => {
  return [...list].sort((a, b) => {
    const dateA = a.effective_notification_datetime || '';
    const dateB = b.effective_notification_datetime || '';
    return dateB.localeCompare(dateA);
  });
};

function Mergers() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mergers, setMergers] = useState(() => dataCache.get('mergers-list') || []);
  const [filteredMergers, setFilteredMergers] = useState(() => sortMergers(dataCache.get('mergers-list') || []));
  const [loading, setLoading] = useState(() => !dataCache.has('mergers-list'));
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [phaseFilter, setPhaseFilter] = useState('all');

  useEffect(() => {
    const queryParam = searchParams.get('q');
    if (queryParam) {
      setSearchTerm(queryParam);
    }
  }, [searchParams]);

  useEffect(() => {
    fetchMergers();
  }, []);

  useEffect(() => {
    filterMergers();
  }, [searchTerm, statusFilter, phaseFilter, mergers]);

  const fetchMergers = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.mergersList);
      if (!response.ok) throw new Error('Failed to fetch mergers');
      const data = await response.json();
      dataCache.set('mergers-list', data.mergers);
      setMergers(data.mergers);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filterMergers = () => {
    let filtered = [...mergers];

    if (phaseFilter === 'phase1') {
      filtered = filtered.filter((m) => m.stage && m.stage.includes('Phase 1'));
    } else if (phaseFilter === 'phase2') {
      filtered = filtered.filter((m) => m.stage && m.stage.includes('Phase 2'));
    } else if (phaseFilter === 'waivers') {
      filtered = filtered.filter((m) => m.is_waiver);
    }

    if (statusFilter !== 'all') {
      filtered = filtered.filter((m) => {
        const displayedOutcome = m.accc_determination || m.status;
        return displayedOutcome === statusFilter;
      });
    }

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (m) =>
          m.merger_name?.toLowerCase().includes(term) ||
          m.merger_id?.toLowerCase().includes(term) ||
          m.acquirers?.some((a) => a?.name?.toLowerCase().includes(term)) ||
          m.targets?.some((t) => t?.name?.toLowerCase().includes(term)) ||
          m.anzsic_codes?.some((c) => c?.name?.toLowerCase().includes(term))
      );
    }

    setFilteredMergers(sortMergers(filtered));
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;

  const outcomes = ['all', ...new Set(mergers.map((m) => m.accc_determination || m.status))];

  return (
    <>
      <SEO
        title="All Mergers"
        description="Browse all Australian mergers and acquisitions being reviewed by the ACCC. Search, filter, and track merger statuses and determinations."
        url="/mergers"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        {/* Filters */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label
                htmlFor="search"
                className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
              >
                Search
              </label>
              <div className="relative">
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
                </svg>
                <input
                  type="text"
                  id="search"
                  className="w-full pl-10 pr-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all"
                  placeholder="Search mergers, companies, or industries..."
                  aria-label="Search mergers, companies, or industries"
                  value={searchTerm}
                  onChange={(e) => {
                    const value = e.target.value;
                    setSearchTerm(value);
                    if (value) {
                      setSearchParams({ q: value });
                    } else {
                      setSearchParams({});
                    }
                  }}
                />
              </div>
            </div>
            <div>
              <label
                htmlFor="phase"
                className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
              >
                Phase
              </label>
              <select
                id="phase"
                className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all appearance-none"
                value={phaseFilter}
                onChange={(e) => setPhaseFilter(e.target.value)}
                aria-label="Filter by merger phase"
              >
                <option value="all">All phases</option>
                <option value="phase1">Phase 1</option>
                <option value="phase2">Phase 2</option>
                <option value="waivers">Waiver</option>
              </select>
            </div>
            <div>
              <label
                htmlFor="status"
                className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
              >
                Status
              </label>
              <select
                id="status"
                className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all appearance-none"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter by merger status"
              >
                {outcomes.map((outcome) => (
                  <option key={outcome} value={outcome}>
                  {outcome === 'all'
                    ? 'All statuses'
                    : outcome}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Results count */}
        <div className="mb-4">
          <p className="text-sm text-gray-400">
            Showing {filteredMergers.length} of {mergers.length} mergers
          </p>
        </div>

        {/* Mergers List */}
        <div className="space-y-3">
          {filteredMergers.map((merger) => (
            <Link
              key={merger.merger_id}
              to={`/mergers/${merger.merger_id}`}
              className="block bg-white rounded-2xl border border-gray-100 shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200"
              aria-label={`View merger details for ${merger.merger_name}`}
            >
              <div className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold text-gray-900 truncate">
                        {merger.merger_name}
                      </h3>
                      {merger.is_waiver && (
                        <span
                          className="flex-shrink-0 inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200/60"
                          role="status"
                          aria-label="Merger type: Waiver application"
                        >
                          Waiver
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      {merger.merger_id} · {merger.stage || 'N/A'}
                    </p>
                  </div>
                  <StatusBadge
                    status={merger.status}
                    determination={merger.accc_determination}
                  />
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">Acquirers</p>
                    <p className="text-sm font-medium text-gray-700">
                      {merger.acquirers.map((a) => a.name).join(', ')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">Targets</p>
                    <p className="text-sm font-medium text-gray-700">
                      {merger.targets.map((t) => t.name).join(', ')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400 mb-0.5">
                      {merger.is_waiver ? 'Application date' : 'Notification date'}
                    </p>
                    <p className="text-sm font-medium text-gray-700">
                      {formatDate(merger.effective_notification_datetime)}
                    </p>
                  </div>
                </div>

                {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {merger.anzsic_codes.map((code, idx) => (
                      <span
                        key={`${merger.merger_id}-anzsic-${code.code || code.name}`}
                        className="inline-flex items-center px-2 py-0.5 rounded-md text-xs bg-gray-50 text-gray-500 border border-gray-100"
                      >
                        {code.name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>

        {filteredMergers.length === 0 && (
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gray-100 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </div>
            <p className="text-gray-500 font-medium">No mergers found</p>
            <p className="text-gray-400 text-sm mt-1">Try adjusting your search or filters</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Mergers;
