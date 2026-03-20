import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import WaiverBadge from '../components/WaiverBadge';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';

function IndustryDetail() {
  const { code } = useParams();
  let decodedCode;
  try {
    decodedCode = decodeURIComponent(code);
  } catch {
    decodedCode = code;
  }
  const [data, setData] = useState(() => dataCache.get(`industry-${decodedCode}`) || null);
  const [industries, setIndustries] = useState(() => dataCache.get('industries-list') || null);
  const [loading, setLoading] = useState(() => !dataCache.has(`industry-${decodedCode}`));
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [decodedCode]);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [detailRes, industriesRes] = await Promise.all([
        fetch(API_ENDPOINTS.industryDetail(decodedCode)),
        industries ? Promise.resolve(null) : fetch(API_ENDPOINTS.industries),
      ]);

      if (!detailRes.ok) {
        if (detailRes.status === 404) throw new Error('not_found');
        throw new Error('Failed to fetch industry data');
      }

      const detailData = await detailRes.json();
      dataCache.set(`industry-${decodedCode}`, detailData);
      setData(detailData);

      if (industriesRes) {
        const industriesData = await industriesRes.json();
        dataCache.set('industries-list', industriesData.industries);
        setIndustries(industriesData.industries);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-10 text-center">
          <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gray-100 flex items-center justify-center">
            <svg className="w-8 h-8 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-gray-900 mb-3">
            {error === 'not_found' ? 'Industry not found' : 'Error loading industry'}
          </h1>
          <p className="text-gray-500 mb-6">
            {error === 'not_found'
              ? `We couldn't find an industry with code "${decodedCode}".`
              : error}
          </p>
          <Link
            to="/industries"
            className="inline-flex items-center px-5 py-2.5 text-sm font-medium rounded-xl text-white bg-primary hover:bg-primary-dark transition-colors shadow-sm"
          >
            Back to industries
          </Link>
        </div>
      </div>
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
