import { useState, useEffect } from 'react';
import LoadingSpinner from '../components/LoadingSpinner';
import { API_ENDPOINTS } from '../config';

function Industries() {
  const [industries, setIndustries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState('count');

  useEffect(() => {
    fetchIndustries();
  }, []);

  const fetchIndustries = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.industries);
      if (!response.ok) throw new Error('Failed to fetch industries');
      const data = await response.json();
      setIndustries(data.industries);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const sortedIndustries = [...industries].sort((a, b) => {
    if (sortBy === 'count') {
      return b.merger_count - a.merger_count;
    } else if (sortBy === 'name') {
      return a.name.localeCompare(b.name);
    } else if (sortBy === 'code') {
      return a.code.localeCompare(b.code);
    }
    return 0;
  });

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
          <p className="text-sm text-gray-500">Total Industries</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {industries.length}
          </p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-sm text-gray-500">Total Merger Reviews</p>
          <p className="text-3xl font-bold text-primary mt-2">
            {industries.reduce((sum, i) => sum + i.merger_count, 0)}
          </p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-sm text-gray-500">Avg Mergers per Industry</p>
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

      {/* Sort Controls */}
      <div className="bg-white p-4 rounded-lg shadow mb-6">
        <div className="flex items-center space-x-4">
          <label className="text-sm font-medium text-gray-700">Sort by:</label>
          <div className="flex space-x-2">
            <button
              onClick={() => setSortBy('count')}
              className={`px-3 py-1 rounded-md text-sm font-medium ${
                sortBy === 'count'
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Merger Count
            </button>
            <button
              onClick={() => setSortBy('name')}
              className={`px-3 py-1 rounded-md text-sm font-medium ${
                sortBy === 'name'
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Name
            </button>
            <button
              onClick={() => setSortBy('code')}
              className={`px-3 py-1 rounded-md text-sm font-medium ${
                sortBy === 'code'
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              Code
            </button>
          </div>
        </div>
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
                Industry Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Merger Count
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Percentage
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sortedIndustries.map((industry, idx) => {
              const totalMergers = industries.reduce(
                (sum, i) => sum + i.merger_count,
                0
              );
              const percentage = (
                (industry.merger_count / totalMergers) *
                100
              ).toFixed(1);

              return (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {industry.code}
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
              );
            })}
          </tbody>
        </table>
      </div>

      {industries.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">No industry data available</p>
        </div>
      )}
    </div>
  );
}

export default Industries;
