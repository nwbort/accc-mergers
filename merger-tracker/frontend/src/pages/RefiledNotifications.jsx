import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { mergerPath } from '../utils/slug';
import { formatDateMedium, calculateDuration } from '../utils/dates';

function RefiledTable({ pairs, showOutcome }) {
  if (pairs.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
        <p className="text-gray-500 text-sm">
          {showOutcome
            ? 'No re-filed notifications have been determined yet.'
            : 'No waivers are currently awaiting a re-filed notification outcome.'}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-100 shadow-card rounded-2xl overflow-hidden overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-100">
        <caption className="sr-only">
          Mergers originally filed as a waiver application, declined, then re-filed as a notification
        </caption>
        <thead>
          <tr className="bg-gray-50/80">
            <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Merger</th>
            <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Waiver filed</th>
            <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Waiver declined</th>
            <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Notification filed</th>
            <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Days to re-file</th>
            <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              {showOutcome ? 'Outcome' : 'Status'}
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {pairs.map((pair) => {
            const daysToRefile = calculateDuration(pair.waiver_declined_date, pair.notification_filed_date);
            return (
              <tr key={pair.notification_id} className="hover:bg-gray-50/50 transition-colors">
                <td className="px-6 py-4 text-sm text-gray-900">
                  <Link
                    to={mergerPath(pair.notification_id, pair.notification_name)}
                    className="font-medium hover:text-primary transition-colors"
                  >
                    {pair.notification_name}
                  </Link>
                  <div className="text-xs text-gray-500 mt-0.5">
                    <Link to={mergerPath(pair.waiver_id, pair.waiver_name)} className="hover:text-primary transition-colors">
                      {pair.waiver_id}
                    </Link>
                    {' → '}
                    {pair.notification_id}
                  </div>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                  {formatDateMedium(pair.waiver_filed_date)}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                  {formatDateMedium(pair.waiver_declined_date)}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                  {formatDateMedium(pair.notification_filed_date)}
                </td>
                <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap tabular-nums">
                  {daysToRefile !== null ? `${daysToRefile} days` : 'N/A'}
                </td>
                <td className="px-6 py-4 text-sm">
                  {showOutcome ? (
                    <StatusBadge determination={pair.notification_determination} />
                  ) : (
                    <StatusBadge status={pair.notification_status} />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RefiledNotifications() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.refiledNotifications, { cacheKey: 'refiled-notifications' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div role="alert" className="text-red-600 p-8 text-center">Error: {error}</div>;

  const current = data?.current || [];
  const completed = data?.completed || [];

  return (
    <>
      <SEO
        title="Refiled notifications"
        description="Mergers originally filed with the ACCC as a waiver application, declined, and then re-filed as a formal notification."
        url="/refiled-notifications"
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Waivers re-filed as notifications
          </h1>
          <p className="mt-2 text-sm text-gray-500 max-w-3xl">
            Some mergers are first filed as a waiver application asking the ACCC to waive the need
            for formal review. When a waiver is declined, the parties sometimes re-file the same
            deal as a formal notification instead. This page tracks those pairs.
          </p>
        </header>

        <section aria-labelledby="refiled-current-heading" className="mb-8">
          <h2 id="refiled-current-heading" className="text-lg font-semibold text-gray-900 mb-4">
            Awaiting a determination
          </h2>
          <RefiledTable pairs={current} showOutcome={false} />
        </section>

        <section aria-labelledby="refiled-completed-heading">
          <h2 id="refiled-completed-heading" className="text-lg font-semibold text-gray-900 mb-4">
            Determined
          </h2>
          <RefiledTable pairs={completed} showOutcome />
        </section>
      </div>
    </>
  );
}

export default RefiledNotifications;
