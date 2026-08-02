import LoadingSpinner from '../components/LoadingSpinner';
import ErrorMessage from '../components/ErrorMessage';
import Phase2Timeline from '../components/Phase2Timeline';
import Phase2CompletedCards from '../components/Phase2CompletedCards';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { useTracking } from '../context/TrackingContext';
import { CARD } from '../utils/classNames';
import { STATIC_PAGE_META } from '../utils/pageMeta';

// Title and description live in the shared table so this page and the
// build-time prerenderer emit the same <head>.
const PAGE_META = STATIC_PAGE_META['/phase-2'];

function Phase2() {
  const { data, loading, error } = useFetchData(API_ENDPOINTS.phase2, { cacheKey: 'phase2' });
  const { autoTrackPhase2, toggleAutoTrackPhase2 } = useTracking();

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage error={error} />;

  const current = data?.current || [];
  const completed = data?.completed || [];

  return (
    <>
      <SEO
        title={PAGE_META.title}
        description={PAGE_META.description}
        url="/phase-2"
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6 flex items-center justify-between gap-4">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Phase 2 tracker
          </h1>
          <button
            type="button"
            role="switch"
            aria-checked={autoTrackPhase2}
            onClick={toggleAutoTrackPhase2}
            title="When on, every merger that proceeds to Phase 2 is added to your tracked mergers, so its milestones show up in your notifications."
            className="flex items-center gap-2 flex-shrink-0"
          >
            <span className="text-sm font-medium text-gray-600 whitespace-nowrap">
              Auto track
            </span>
            <span
              className={`relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors ${
                autoTrackPhase2 ? 'bg-primary' : 'bg-gray-300'
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transform transition-transform ${
                  autoTrackPhase2 ? 'translate-x-4' : 'translate-x-0.5'
                }`}
              />
            </span>
          </button>
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
            <div className={`${CARD} p-6`}>
              <p className="text-gray-500 text-sm">No Phase 2 matters have been completed yet.</p>
            </div>
          ) : (
            <Phase2CompletedCards matters={completed} />
          )}
        </section>
      </div>
    </>
  );
}

export default Phase2;
