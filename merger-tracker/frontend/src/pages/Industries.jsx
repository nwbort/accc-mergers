import { useState, useEffect, Fragment } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import WaiverBadge from '../components/WaiverBadge';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { dataCache } from '../utils/dataCache';

function Industries() {
  const [industries, setIndustries] = useState(() => dataCache.get('industries-list') || []);
  const [mergers, setMergers] = useState(() => dataCache.get('industries-mergers') || []);
  const [loading, setLoading] = useState(() => !dataCache.has('industries-list'));
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedIndustry, setExpandedIndustry] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      // Fetch industries data
      const industriesRes = await fetch(API_ENDPOINTS.industries);
      if (!industriesRes.ok) throw new Error('Failed to fetch industries');
      const industriesData = await industriesRes.json();

      // Fetch mergers list using pagination
      let allMergers = [];
      const metaResponse = await fetch(API_ENDPOINTS.mergersListMeta);

      if (!metaResponse.ok) {
        // Fallback to legacy endpoint if pagination not available
        console.log('Pagination not available, falling back to legacy endpoint');
        const mergersRes = await fetch(API_ENDPOINTS.mergersList);
        if (!mergersRes.ok) throw new Error('Failed to fetch mergers');
        const mergersData = await mergersRes.json();
        allMergers = mergersData.mergers;
      } else {
        const meta = await metaResponse.json();
        const totalPages = meta.total_pages;

        // Fetch all pages in parallel
        const pagePromises = [];
        for (let i = 1; i <= totalPages; i++) {
          pagePromises.push(fetch(API_ENDPOINTS.mergersListPage(i)));
        }

        const pageResponses = await Promise.all(pagePromises);
        const pageDataPromises = pageResponses.map(r => {
          if (!r.ok) throw new Error('Failed to fetch merger page');
          return r.json();
        });
        const pagesData = await Promise.all(pageDataPromises);

        // Combine all pages
        allMergers = pagesData.flatMap(page => page.mergers);
      }

      dataCache.set('industries-list', industriesData.industries);
      dataCache.set('industries-mergers', allMergers);
      setIndustries(industriesData.industries);
      setMergers(allMergers);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getMergersForIndustry = (code, name) => {
    const filtered = mergers.filter((merger) =>
      merger.anzsic_codes.some(
        (anzsic) => anzsic.code === code && anzsic.name === name
      )
    );

    // Sort by most recent date (comparing determination and notification dates)
    return filtered.sort((a, b) => {
      const getLatestDate = (merger) => {
        const dates = [
          merger.determination_publication_date,
          merger.effective_notification_datetime
        ].filter(Boolean);

        if (dates.length === 0) return new Date(0);
        return new Date(Math.max(...dates.map(d => new Date(d).getTime())));
      };

      return getLatestDate(b) - getLatestDate(a); // Most recent first
    });
  };

  const filteredIndustries = industries
    .filter((industry) => {
      if (!searchTerm) return true;
      const term = searchTerm.toLowerCase();
      return (
        industry.name.toLowerCase().includes(term) ||
        industry.code.toLowerCase().includes(term)
      );
    })
    .sort((a, b) => b.merger_count - a.merger_count);

  const toggleIndustry = (code, name) => {
    const key = `${code}-${name}`;
    setExpandedIndustry(expandedIndustry === key ? null : key);
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-red-600 p-8 text-center">Error: {error}</div>;

  return (
    <>
      <SEO
        title="Industries"
        description="Browse mergers by industry (ANZSIC codes). See which Australian industries have the most merger activity monitored by the ACCC."
        url="/industries"
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {[
          { label: 'Total industries', value: industries.length },
          { label: 'Total merger reviews', value: mergers.length },
          { label: 'Avg mergers per industry', value: industries.length > 0 ? (industries.reduce((sum, i) => sum + i.merger_count, 0) / industries.length).toFixed(1) : 0 },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white p-5 rounded-2xl border border-gray-100 shadow-card">
            <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">{label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight">
              {value}
            </p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 mb-6">
        <label
          htmlFor="search"
          className="block text-xs font-medium text-gray-500 uppercase tracking-wider mb-2"
        >
          Search industries
        </label>
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <input
            type="text"
            id="search"
            className="w-full pl-10 pr-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all"
            placeholder="Search by industry name or code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {/* Results count */}
      <div className="mb-4">
        <p className="text-sm text-gray-400">
          Showing {filteredIndustries.length} of {industries.length} industries
        </p>
      </div>

      {/* Industries Table */}
      <div className="bg-white border border-gray-100 shadow-card rounded-2xl overflow-hidden">
        <table className="min-w-full divide-y divide-gray-100">
          <caption className="sr-only">
            Industry breakdown of Australian merger reviews by ANZSIC code, showing merger counts and percentage of total reviews
          </caption>
          <thead>
            <tr className="bg-gray-50/80">
              <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Industry name
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Mergers
              </th>
              <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Share
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {filteredIndustries.map((industry) => {
              const totalMergers = mergers.length;
              const percentage = (
                (industry.merger_count / totalMergers) *
                100
              ).toFixed(1);
              const key = `${industry.code}-${industry.name}`;
              const isExpanded = expandedIndustry === key;
              const industryMergers = getMergersForIndustry(
                industry.code,
                industry.name
              );

              return (
                <Fragment key={industry.code}>
                  <tr
                    className="hover:bg-gray-50/50 cursor-pointer transition-colors"
                    onClick={() => toggleIndustry(industry.code, industry.name)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        toggleIndustry(industry.code, industry.name);
                      }
                    }}
                    tabIndex={0}
                    role="button"
                    aria-expanded={isExpanded}
                    aria-controls={`industry-details-${industry.code}`}
                  >
                    <td className="px-6 py-4 text-sm text-gray-900">
                      <div className="flex items-center">
                        <svg
                          className={`w-4 h-4 mr-2.5 text-gray-400 transition-transform duration-200 ${
                            isExpanded ? 'transform rotate-90' : ''
                          }`}
                          fill="currentColor"
                          viewBox="0 0 20 20"
                          role="img"
                          aria-label={isExpanded ? 'Collapse industry details' : 'Expand industry details'}
                        >
                          <path
                            fillRule="evenodd"
                            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                        <span className="font-medium">{industry.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-semibold bg-primary/10 text-primary">
                        {industry.merger_count}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center gap-3">
                        <div
                          className="flex-1 bg-gray-100 rounded-full h-1.5 max-w-[8rem] overflow-hidden"
                          role="progressbar"
                          aria-valuenow={parseFloat(percentage)}
                          aria-valuemin={0}
                          aria-valuemax={100}
                          aria-label={`${percentage}% of total mergers`}
                        >
                          <div
                            className="bg-primary h-1.5 rounded-full transition-all duration-300"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                        <span className="text-xs tabular-nums font-medium text-gray-600 w-12">{percentage}%</span>
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr id={`industry-details-${industry.code}`}>
                      <td colSpan="3" className="px-6 py-4 bg-gray-50/50">
                        <div className="space-y-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
                            Mergers in this industry
                          </p>
                          <div className={`space-y-2 ${industryMergers.length > 6 ? 'max-h-[400px] overflow-y-auto pr-2' : ''}`}>
                            {industryMergers.map((merger) => (
                              <Link
                                key={merger.merger_id}
                                to={`/mergers/${merger.merger_id}`}
                                className="block p-3 bg-white rounded-xl border border-gray-100 hover:border-primary/30 hover:shadow-sm transition-all"
                                aria-label={`View merger details for ${merger.merger_name}`}
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <span className="text-sm font-medium text-gray-900 truncate">
                                    {merger.merger_name}
                                  </span>
                                  {merger.is_waiver && <WaiverBadge className="flex-shrink-0" />}
                                </div>
                                <span className="text-xs text-gray-400 mt-1 block">
                                  {merger.status}
                                </span>
                              </Link>
                            ))}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {filteredIndustries.length === 0 && (
        <div className="text-center py-16">
          <p className="text-gray-500 font-medium">No industries found</p>
          <p className="text-gray-400 text-sm mt-1">Try adjusting your search</p>
        </div>
      )}
    </div>
    </>
  );
}

export default Industries;
