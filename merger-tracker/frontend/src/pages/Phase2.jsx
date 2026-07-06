import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import Phase2Timeline from '../components/Phase2Timeline';
import StatusBadge from '../components/StatusBadge';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { mergerPath } from '../utils/slug';
import { formatDateMedium, calculateDuration } from '../utils/dates';

function Phase2() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.phase2, { cacheKey: 'phase2' });

  if (loading) return <LoadingSpinner />;
  if (error) return <div role="alert" className="text-red-600 p-8 text-center">Error: {error}</div>;

  const current = data?.current || [];
  const completed = data?.completed || [];

  return (
    <>
      <SEO
        title="Phase 2 tracker"
        description="Track Australian mergers under ACCC Phase 2 (detailed) assessment, with referral dates, notice-of-competition-concerns milestones and determination deadlines."
        url="/phase-2"
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Phase 2 tracker
          </h1>
        </header>

        <section aria-labelledby="phase2-current-heading" className="mb-8">
          <h2 id="phase2-current-heading" className="text-lg font-semibold text-gray-900 mb-4">
            Current Phase 2 matters
          </h2>
          <Phase2Timeline matters={current} />
        </section>

        <section aria-labelledby="phase2-completed-heading">
          <h2 id="phase2-completed-heading" className="text-lg font-semibold text-gray-900 mb-4">
            Completed Phase 2 matters
          </h2>
          {completed.length === 0 ? (
            <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6">
              <p className="text-gray-500 text-sm">No Phase 2 matters have been completed yet.</p>
            </div>
          ) : (
            <div className="bg-white border border-gray-100 shadow-card rounded-2xl overflow-hidden overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-100">
                <caption className="sr-only">
                  Completed Phase 2 mergers with referral date, determination and duration
                </caption>
                <thead>
                  <tr className="bg-gray-50/80">
                    <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Merger</th>
                    <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Referred</th>
                    <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Determined</th>
                    <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                    <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Outcome</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {completed.map((matter) => {
                    const duration = calculateDuration(matter.referral_date, matter.determination_date);
                    return (
                      <tr key={matter.merger_id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-6 py-4 text-sm text-gray-900">
                          <Link
                            to={mergerPath(matter.merger_id, matter.merger_name)}
                            className="font-medium hover:text-primary transition-colors"
                          >
                            {matter.merger_name}
                          </Link>
                          <div className="text-xs text-gray-500 mt-0.5">{matter.merger_id}</div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                          {formatDateMedium(matter.referral_date)}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                          {formatDateMedium(matter.determination_date)}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap tabular-nums">
                          {duration !== null ? `${duration} days` : 'N/A'}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          <StatusBadge determination={matter.determination} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

export default Phase2;
