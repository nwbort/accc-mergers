import { useParams, Link } from 'react-router-dom';
import { FaChevronRight } from 'react-icons/fa';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorCard from '../components/ErrorCard';
import IndustryMergerGroups from '../components/IndustryMergerGroups';
import PhaseDurationComparison from '../components/PhaseDurationComparison';
import SEO from '../components/SEO';
import { API_ENDPOINTS } from '../config';
import { useFetchData } from '../hooks/useFetchData';
import { partyPath } from '../utils/slug';

const ROLE_LABELS = {
  acquirer: 'As acquirer',
  target: 'As target',
  other: 'As other party',
};

function PartyDetail() {
  const { id } = useParams();
  let decodedId;
  try {
    decodedId = decodeURIComponent(id);
  } catch {
    decodedId = id;
  }

  const { data, loading, error } = useFetchData(
    API_ENDPOINTS.partyDetail(decodedId),
    { cacheKey: `party-${decodedId}` }
  );

  // Overall all-mergers figures, for comparing this party's Phase 1 duration
  // against the market as a whole. Non-fatal if it fails to load.
  const { data: statsData } = useFetchData(
    data ? API_ENDPOINTS.stats : null,
    data ? { cacheKey: 'dashboard-stats' } : {}
  );

  const isNotFound = error === 'HTTP 404';

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <ErrorCard
        title={isNotFound ? 'Party not found' : 'Error loading party'}
        message={isNotFound
          ? `We couldn't find a party with id "${decodedId}".`
          : error
        }
        backTo="/parties"
        backLabel="Back to parties"
      />
    );
  }

  if (!data) return null;

  const partyName = data.canonical_name || decodedId;
  const members = data.members || [];
  const mergersByRole = data.mergers || {};
  const mergerCount = data.merger_count ?? 0;

  const statCards = [
    { label: 'Total reviews', value: mergerCount },
    { label: 'Phase 2 reviews', value: data.phase_2_count ?? 0 },
    { label: 'Waivers', value: data.waiver_count ?? 0 },
    { label: 'Under assessment', value: data.active_count ?? 0 },
  ];

  const duration = data.phase_duration;
  const comparisons = [];
  if (statsData?.phase_duration) {
    comparisons.push({ name: 'All mergers', duration: statsData.phase_duration });
  }

  const roles = ['acquirer', 'target', 'other'].filter((role) => (mergersByRole[role] || []).length > 0);

  return (
    <>
      <SEO
        title={partyName}
        description={`${partyName} has been involved in ${mergerCount} ACCC merger review${mergerCount !== 1 ? 's' : ''}${data.phase_2_count ? `, including ${data.phase_2_count} Phase 2 review${data.phase_2_count !== 1 ? 's' : ''}` : ''}.`}
        url={partyPath(decodedId, partyName)}
      />
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
        <nav aria-label="Party breadcrumb" className="mb-5">
          <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-gray-500">
            <li>
              <Link to="/parties" className="hover:text-primary transition-colors">
                Parties
              </Link>
            </li>
            <li className="flex items-center gap-x-1.5" aria-current="page">
              <FaChevronRight className="w-3 h-3 text-gray-300" aria-hidden="true" />
              <span className="font-medium text-gray-700">{partyName}</span>
            </li>
          </ol>
        </nav>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-card p-6 mb-6 card-accent">
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{partyName}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {mergerCount} merger{mergerCount !== 1 ? 's' : ''}
          </p>

          {members.length > 1 && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Also registered as
              </h2>
              <ul className="space-y-1">
                {members.map((member) => (
                  <li key={`${member.name}-${member.identifier || ''}`} className="text-sm text-gray-700">
                    {member.name}
                    {member.identifier && (
                      <span className="text-gray-500">
                        {' '}&middot; {member.identifier_type ? `${member.identifier_type}: ` : ''}{member.identifier}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {members.length === 1 && members[0].identifier && (
            <p className="text-sm text-gray-500 mt-2">
              {members[0].identifier_type ? `${members[0].identifier_type}: ` : ''}{members[0].identifier}
            </p>
          )}
        </div>

        {mergerCount > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
            {statCards.map(({ label, value }) => (
              <div key={label} className="bg-white p-5 rounded-2xl border border-gray-100 shadow-card">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1.5 tracking-tight tabular-nums">
                  {value}
                </p>
              </div>
            ))}
          </div>
        )}

        {mergerCount > 0 && duration?.average_business_days != null && (
          <div className="mb-6">
            <PhaseDurationComparison duration={duration} comparisons={comparisons} />
          </div>
        )}

        {roles.map((role) => (
          <div key={role} className="mb-8">
            <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3">
              {ROLE_LABELS[role]}
            </h2>
            <IndustryMergerGroups mergers={mergersByRole[role]} variant="full" />
          </div>
        ))}

        {mergerCount === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 font-medium">No mergers found for this party</p>
          </div>
        )}
      </div>
    </>
  );
}

export default PartyDetail;
