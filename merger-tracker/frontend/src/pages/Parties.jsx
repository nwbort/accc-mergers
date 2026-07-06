import { useState } from 'react';
import { Link } from 'react-router-dom';
import LoadingSpinner from '../components/LoadingSpinner';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { partyPath } from '../utils/slug';

function Parties() {
  const { data, loading, error } = useFetchData(
    API_ENDPOINTS.parties,
    { cacheKey: 'parties-list' }
  );
  const allParties = data?.parties || [];

  const [searchTerm, setSearchTerm] = useState('');

  const filteredParties = allParties.filter((party) => {
    if (!searchTerm) return true;
    return party.name.toLowerCase().includes(searchTerm.toLowerCase());
  });

  const maxCount = filteredParties.length
    ? Math.max(...filteredParties.map((p) => p.merger_count))
    : 0;

  if (loading) return <LoadingSpinner />;
  if (error) return <div role="alert" className="text-red-600 p-8 text-center">Error: {error}</div>;

  return (
    <>
      <SEO
        title="Parties"
        description="Browse every party involved in an ACCC merger review — acquirers, targets and other parties — with the number of notifications each has been part of."
        url="/parties"
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <header className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-gray-900">
            Parties
          </h1>
          <p className="mt-1 text-sm text-gray-500 max-w-xl">
            Every acquirer, target and other party named in an ACCC merger notification, grouped by entity.
          </p>
        </header>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-5 mb-6">
          <div className="flex items-baseline justify-between gap-3 mb-2">
            <label
              htmlFor="party-search"
              className="text-xs font-medium text-gray-500 uppercase tracking-wider"
            >
              Search parties
            </label>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider shrink-0">
              Showing {filteredParties.length} of {allParties.length}
            </p>
          </div>
          <div className="relative">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="text"
              id="party-search"
              className="w-full pl-10 pr-3 py-2.5 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary focus:bg-white transition-all"
              placeholder="Search by party name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="bg-white border border-gray-100 shadow-card rounded-2xl overflow-hidden">
          <table className="min-w-full divide-y divide-gray-100">
            <caption className="sr-only">
              Parties named in ACCC merger reviews, with the number of mergers each has been part of
            </caption>
            <thead>
              <tr className="bg-gray-50/80">
                <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Party
                </th>
                <th className="px-6 py-3.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Mergers
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filteredParties.map((party) => (
                <tr key={party.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-4 text-sm text-gray-900">
                    <Link
                      to={partyPath(party.id, party.name)}
                      className="font-medium hover:text-primary transition-colors"
                    >
                      {party.name}
                    </Link>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 w-2/3">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex items-center justify-center min-w-[2.25rem] px-2.5 py-1 rounded-lg text-xs font-semibold bg-primary/10 text-primary tabular-nums">
                        {party.merger_count}
                      </span>
                      <div className="flex-1 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-primary h-1.5 rounded-full transition-all duration-300"
                          style={{ width: `${maxCount > 0 ? (party.merger_count / maxCount) * 100 : 0}%` }}
                        />
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredParties.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 font-medium">No parties found</p>
            <p className="text-gray-500 text-sm mt-1">Try adjusting your search</p>
          </div>
        )}
      </div>
    </>
  );
}

export default Parties;
