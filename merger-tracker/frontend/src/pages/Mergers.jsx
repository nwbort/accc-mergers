import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

function Mergers() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [mergers, setMergers] = useState([]);
  const [filteredMergers, setFilteredMergers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [phaseFilter, setPhaseFilter] = useState('all');

  // Initialize search term from URL query parameter
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
      setMergers(data.mergers);
      setFilteredMergers(data.mergers);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filterMergers = () => {
    let filtered = [...mergers];

    // Filter by phase
    if (phaseFilter === 'phase1') {
      filtered = filtered.filter((m) => m.stage && m.stage.includes('Phase 1'));
    } else if (phaseFilter === 'phase2') {
      filtered = filtered.filter((m) => m.stage && m.stage.includes('Phase 2'));
    } else if (phaseFilter === 'waivers') {
      filtered = filtered.filter((m) => m.is_waiver);
    }

    // Filter by status (match against displayed outcome: determination || status)
    if (statusFilter !== 'all') {
      filtered = filtered.filter((m) => {
        const displayedOutcome = m.accc_determination || m.status;
        return displayedOutcome === statusFilter;
      });
    }

    // Search filter (note: merger_description not included in list view for performance)
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

    // Sort by notification date (newest first)
    filtered.sort((a, b) => {
      const dateA = a.effective_notification_datetime || '';
      const dateB = b.effective_notification_datetime || '';
      return dateB.localeCompare(dateA);
    });

    setFilteredMergers(filtered);
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  // Get all unique outcomes (what's actually displayed in the badge: determination || status)
  const outcomes = ['all', ...new Set(mergers.map((m) => m.accc_determination || m.status))];

  return (
    <>
      <SEO
        title="All Mergers"
        description="Browse all Australian mergers and acquisitions being reviewed by the ACCC. Search, filter, and track merger statuses and determinations."
        url="/mergers"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Filters */}
        <div className="bg-white p-4 rounded-lg shadow mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label
                htmlFor="search"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Search
              </label>
              <input
                type="text"
                id="search"
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
                placeholder="Search mergers, companies, or industries..."
                aria-label="Search mergers, companies, or industries"
                value={searchTerm}
                onChange={(e) => {
                  const value = e.target.value;
                  setSearchTerm(value);
                  // Update URL to reflect search term
                  if (value) {
                    setSearchParams({ q: value });
                  } else {
                    setSearchParams({});
                  }
                }}
              />
            </div>
            <div>
              <label
                htmlFor="phase"
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Phase
              </label>
              <select
                id="phase"
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
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
                className="block text-sm font-medium text-gray-700 mb-1"
              >
                Status
              </label>
              <select
                id="status"
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
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
          <p className="text-sm text-gray-600">
            Showing {filteredMergers.length} of {mergers.length} mergers
          </p>
        </div>

        {/* Mergers List */}
        <div className="space-y-4">
          {filteredMergers.map((merger) => (
            <Link
              key={merger.merger_id}
              to={`/mergers/${merger.merger_id}`}
              className="block bg-white rounded-lg shadow hover:shadow-md transition-shadow duration-200"
              aria-label={`View merger details for ${merger.merger_name}`}
            >
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold text-gray-900">
                        {merger.merger_name}
                      </h3>
                      {merger.is_waiver && (
                        <span
                          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800"
                          role="status"
                          aria-label="Merger type: Waiver application"
                        >
                          Waiver
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">
                      {merger.merger_id} • {merger.stage || 'N/A'}
                    </p>
                  </div>
                  <StatusBadge
                    status={merger.status}
                    determination={merger.accc_determination}
                  />
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">Acquirers</p>
                    <p className="text-sm font-medium text-gray-900">
                      {merger.acquirers.map((a) => a.name).join(', ')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Targets</p>
                    <p className="text-sm font-medium text-gray-900">
                      {merger.targets.map((t) => t.name).join(', ')}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">
                      {merger.is_waiver ? 'Application date' : 'Notification date'}
                    </p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDate(merger.effective_notification_datetime)}
                    </p>
                  </div>
                </div>

                {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {merger.anzsic_codes.map((code, idx) => (
                      <span
                        key={`${merger.merger_id}-anzsic-${code.code || code.name}`}
                        className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700"
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
          <div className="text-center py-12">
            <p className="text-gray-500">No mergers found matching your criteria</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Mergers;
