import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import { formatDate } from '../utils/dates';
import { API_ENDPOINTS } from '../config';

function Mergers() {
  const [mergers, setMergers] = useState([]);
  const [filteredMergers, setFilteredMergers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    fetchMergers();
  }, []);

  useEffect(() => {
    filterMergers();
  }, [searchTerm, statusFilter, mergers]);

  const fetchMergers = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.mergers);
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

    // Filter by status
    if (statusFilter !== 'all') {
      filtered = filtered.filter((m) => m.status === statusFilter);
    }

    // Search filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (m) =>
          m.merger_name.toLowerCase().includes(term) ||
          m.merger_description?.toLowerCase().includes(term) ||
          m.acquirers.some((a) => a.name.toLowerCase().includes(term)) ||
          m.targets.some((t) => t.name.toLowerCase().includes(term))
      );
    }

    setFilteredMergers(filtered);
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600">Error: {error}</div>;

  const statuses = ['all', ...new Set(mergers.map((m) => m.status))];

  return (
    <>
      <SEO
        title="All Mergers"
        description="Browse all Australian mergers and acquisitions being reviewed by the ACCC. Search, filter, and track merger statuses and determinations."
        url="/mergers"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">All mergers</h1>
        </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
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
            >
              {statuses.map((status) => (
                <option key={status} value={status}>
                  {status === 'all'
                    ? 'All statuses'
                    : status}
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
          >
            <div className="p-6">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900">
                    {merger.merger_name}
                  </h3>
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
                  <p className="text-xs text-gray-500">Notification date</p>
                  <p className="text-sm font-medium text-gray-900">
                    {formatDate(merger.effective_notification_datetime)}
                  </p>
                </div>
              </div>

              {merger.anzsic_codes && merger.anzsic_codes.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {merger.anzsic_codes.map((code, idx) => (
                    <span
                      key={idx}
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
