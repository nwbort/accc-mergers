import { useParams, Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorCard from '../components/ErrorCard';
import WaiverBadge from '../components/WaiverBadge';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';

function IndustryDetail() {
  const { code } = useParams();
  let decodedCode;
  try {
    decodedCode = decodeURIComponent(code);
  } catch {
    decodedCode = code;
  }

  const { data, loading, error } = useFetchData(
    API_ENDPOINTS.industryDetail(decodedCode),
    { cacheKey: `industry-${decodedCode}` }
  );
  // The industries list is used solely to resolve the display name. A failure
  // there shouldn't block the page — we fall back to the code.
  const { data: industriesData } = useFetchData(API_ENDPOINTS.industries, {
    cacheKey: 'industries-list',
  });
  const industries = industriesData?.industries || null;

  const isNotFound = error === 'HTTP 404';

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <ErrorCard
        title={isNotFound ? 'Industry not found' : 'Error loading industry'}
        message={isNotFound
          ? `We couldn't find an industry with code "${decodedCode}".`
          : error
        }
        backTo="/industries"
        backLabel="Back to industries"
      />
    );
  }

  if (!data) return null;

  const industryName = industries
    ? industries.find((i) => i.code === decodedCode)?.name || decodedCode
    : decodedCode;

  const mergers = data.mergers || [];

  return (
    <>
      <SEO
        title={industryName}
        description={`${mergers.length} merger${mergers.length !== 1 ? 's' : ''} in the ${industryName} industry reviewed by the ACCC.`}
        url={`/industries/${encodeURIComponent(decodedCode)}`}
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <Link
          to="/industries"
          className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary mb-5 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
          Back to industries
        </Link>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 mb-6 card-accent">
          <div className="pt-1">
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
              {industryName}
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              ANZSIC code: {decodedCode} · {mergers.length} merger{mergers.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {mergers.map((merger) => (
            <Link
              key={merger.merger_id}
              to={`/mergers/${merger.merger_id}`}
              className="block bg-white rounded-2xl border border-gray-100 shadow-card hover:shadow-card-hover hover:border-gray-200 transition-all duration-200 p-5"
            >
              <div className="flex items-center gap-2 min-w-0">
                <h3 className="text-base font-semibold text-gray-900 truncate hover:text-primary transition-colors">
                  {merger.merger_name}
                </h3>
                {merger.is_waiver && <WaiverBadge className="flex-shrink-0" />}
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {merger.status}
              </p>
            </Link>
          ))}
        </div>

        {mergers.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 font-medium">No mergers found for this industry</p>
          </div>
        )}
      </div>
    </>
  );
}

export default IndustryDetail;
