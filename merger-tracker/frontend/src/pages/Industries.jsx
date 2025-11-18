import { useState, useEffect, Fragment } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import { API_ENDPOINTS } from '../config';

function Industries() {
  const [industries, setIndustries] = useState([]);
  const [mergers, setMergers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedIndustry, setExpandedIndustry] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [industriesRes, mergersRes] = await Promise.all([
        fetch(API_ENDPOINTS.industries),
        fetch(API_ENDPOINTS.mergers),
      ]);

      if (!industriesRes.ok || !mergersRes.ok) {
        throw new Error('Failed to fetch data');
      }

      const industriesData = await industriesRes.json();
      const mergersData = await mergersRes.json();

      setIndustries(industriesData.industries);
      setMergers(mergersData.mergers);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const getMergersForIndustry = (code, name) => {
    return mergers.filter((merger) =>
      merger.anzsic_codes.some(
        (anzsic) => anzsic.code === code && anzsic.name === name
      )
    );
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
  if (error) return <div className="text-red-600">Error: {error}</div>;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Industries</h1>
        <p className="mt-2 text-sm text-gray-600">
          ANZSIC industry classifications for merger reviews
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-sm text-gray-500">Total industries</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {industries.length}
          </p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-sm text-gray-500">Total merger reviews</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {mergers.length}
          </p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-sm text-gray-500">Avg mergers per industry</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {industries.length > 0
              ? (
                  industries.reduce((sum, i) => sum + i.merger_count, 0) /
                  industries.length
                ).toFixed(1)
              : 0}
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white p-4 rounded-lg shadow mb-6">
        <label
          htmlFor="search"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          Search industries
        </label>
        <input
          type="text"
          id="search"
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-primary focus:border-primary"
          placeholder="Search by industry name or code..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      {/* Results count */}
      <div className="mb-4">
        <p className="text-sm text-gray-600">
          Showing {filteredIndustries.length} of {industries.length} industries
        </p>
      </div>

      {/* Industries Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Code
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Industry name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Merger count
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Percentage
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredIndustries.map((industry, idx) => {
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
                <Fragment key={idx}>
                  <tr
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => toggleIndustry(industry.code, industry.name)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      <div className="flex items-center">
                        <svg
                          className={`w-4 h-4 mr-2 transition-transform ${
                            isExpanded ? 'transform rotate-90' : ''
                          }`}
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                            clipRule="evenodd"
                          />
                        </svg>
                        {industry.code}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {industry.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary text-white">
                        {industry.merger_count}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      <div className="flex items-center">
                        <span className="mr-2">{percentage}%</span>
                        <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-xs">
                          <div
                            className="bg-primary h-2 rounded-full"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr>
                      <td colSpan="4" className="px-6 py-4 bg-gray-50">
                        <div className="space-y-2">
                          <p className="text-sm font-medium text-gray-700 mb-3">
                            Mergers in this industry:
                          </p>
                          {industryMergers.map((merger) => (
                            <Link
                              key={merger.merger_id}
                              to={`/mergers/${merger.merger_id}`}
                              className="block p-3 bg-white rounded border border-gray-200 hover:border-primary hover:bg-gray-50 transition-colors"
                            >
                              <div className="flex items-center justify-between">
                                <span className="text-sm font-medium text-primary">
                                  {merger.merger_name}
                                </span>
                                <span className="text-xs text-gray-500">
                                  {merger.merger_id}
                                </span>
                              </div>
                              <span className="text-xs text-gray-500 mt-1 block">
                                {merger.status}
                              </span>
                            </Link>
                          ))}
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
        <div className="text-center py-12">
          <p className="text-gray-500">No industries found matching your search</p>
        </div>
      )}
    </div>
  );
}

export default Industries;
