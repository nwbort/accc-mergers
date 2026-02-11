import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from '../components/StatusBadge';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { formatDate } from '../utils/dates';
import { dataCache } from '../utils/dataCache';

function Digest() {
  const [digest, setDigest] = useState(() => dataCache.get('digest') || null);
  const [loading, setLoading] = useState(() => !dataCache.has('digest'));
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDigest();
  }, []);

  const fetchDigest = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.digest);
      if (!response.ok) throw new Error('Failed to fetch digest');
      const data = await response.json();
      dataCache.set('digest', data);
      setDigest(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatParties = (parties) => {
    if (!parties || parties.length === 0) return 'N/A';
    return parties.map(p => p.name).join(', ');
  };

  const renderMergerRow = (merger) => (
    <tr key={merger.merger_id} className="border-b border-gray-200 hover:bg-gray-50">
      <td className="px-4 py-3">
        <Link
          to={`/mergers/${merger.merger_id}`}
          className="text-blue-600 hover:text-blue-800 font-medium"
        >
          {merger.merger_id}
        </Link>
      </td>
      <td className="px-4 py-3">
        <Link
          to={`/mergers/${merger.merger_id}`}
          className="text-gray-900 hover:text-blue-600"
        >
          {merger.merger_name}
        </Link>
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {formatParties(merger.acquirers)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {formatParties(merger.targets)}
      </td>
      <td className="px-4 py-3 text-sm">
        <StatusBadge
          status={merger.status}
          determination={merger.accc_determination}
        />
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {merger.effective_notification_datetime
          ? formatDate(merger.effective_notification_datetime)
          : 'N/A'}
      </td>
    </tr>
  );

  const renderMergerRowWithDetermination = (merger) => (
    <tr key={merger.merger_id} className="border-b border-gray-200 hover:bg-gray-50">
      <td className="px-4 py-3">
        <Link
          to={`/mergers/${merger.merger_id}`}
          className="text-blue-600 hover:text-blue-800 font-medium"
        >
          {merger.merger_id}
        </Link>
      </td>
      <td className="px-4 py-3">
        <Link
          to={`/mergers/${merger.merger_id}`}
          className="text-gray-900 hover:text-blue-600"
        >
          {merger.merger_name}
        </Link>
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {formatParties(merger.acquirers)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {formatParties(merger.targets)}
      </td>
      <td className="px-4 py-3 text-sm">
        <StatusBadge
          status={merger.status}
          determination={merger.accc_determination}
        />
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        {merger.determination_publication_date
          ? formatDate(merger.determination_publication_date)
          : 'N/A'}
      </td>
    </tr>
  );

  const renderSection = (title, description, mergers, showDeterminationDate = false) => {
    if (mergers.length === 0) {
      return (
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-2">{title}</h2>
          <p className="text-gray-600 mb-4">{description}</p>
          <p className="text-gray-500 italic">No deals in this category</p>
        </div>
      );
    }

    return (
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-2">{title}</h2>
        <p className="text-gray-600 mb-4">{description}</p>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Deal
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Acquirer(s)
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Target(s)
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {showDeterminationDate ? 'Determination Date' : 'Notification Date'}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white">
              {showDeterminationDate
                ? mergers.map(renderMergerRowWithDetermination)
                : mergers.map(renderMergerRow)}
            </tbody>
          </table>
        </div>
        <p className="text-sm text-gray-500 mt-4">
          {mergers.length} {mergers.length === 1 ? 'deal' : 'deals'}
        </p>
      </div>
    );
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;
  if (!digest) return null;

  const periodStart = digest.period_start ? formatDate(digest.period_start) : 'N/A';
  const periodEnd = digest.period_end ? formatDate(digest.period_end) : 'N/A';

  return (
    <div className="min-h-screen bg-gray-50">
      <SEO
        title="Catch me up - ACCC Merger Tracker"
        description="Weekly digest of ACCC merger activity including new deals, cleared deals, declined deals, and ongoing assessments"
      />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Catch me up</h1>
          <p className="text-gray-600">
            Weekly digest of ACCC merger activity from {periodStart} to {periodEnd}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            Last updated: {digest.generated_at ? formatDate(digest.generated_at) : 'N/A'}
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-blue-600">
              {digest.new_deals_notified.length}
            </div>
            <div className="text-sm text-gray-600">New Deals Notified</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-green-600">
              {digest.deals_cleared.length}
            </div>
            <div className="text-sm text-gray-600">Deals Cleared</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-red-600">
              {digest.deals_declined.length}
            </div>
            <div className="text-sm text-gray-600">Deals Declined</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-yellow-600">
              {digest.ongoing_phase_1.length}
            </div>
            <div className="text-sm text-gray-600">Ongoing Phase 1</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-2xl font-bold text-orange-600">
              {digest.ongoing_phase_2.length}
            </div>
            <div className="text-sm text-gray-600">Ongoing Phase 2</div>
          </div>
        </div>

        {/* New Deals Notified */}
        {renderSection(
          'New Deals Notified',
          'Mergers notified to the ACCC in the last week that have not yet been determined',
          digest.new_deals_notified,
          false
        )}

        {/* Deals Cleared */}
        {renderSection(
          'Deals Cleared',
          'Mergers approved by the ACCC in the last week',
          digest.deals_cleared,
          true
        )}

        {/* Deals Declined */}
        {renderSection(
          'Deals Declined',
          'Mergers not approved by the ACCC in the last week',
          digest.deals_declined,
          true
        )}

        {/* Ongoing Phase 1 */}
        {renderSection(
          'Ongoing Phase 1 Deals',
          'Mergers currently under Phase 1 initial assessment',
          digest.ongoing_phase_1,
          false
        )}

        {/* Ongoing Phase 2 */}
        {renderSection(
          'Ongoing Phase 2 Deals',
          'Mergers currently under Phase 2 detailed assessment',
          digest.ongoing_phase_2,
          false
        )}
      </div>
    </div>
  );
}

export default Digest;
